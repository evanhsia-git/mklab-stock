/*
 * screener-dcf.js — Screener「DCF 估值」分頁（估值指標表 + DCF 計算機）
 * 依賴：mklab-core.js（MKLAB.data、MKLAB.DataTable、MKLAB.exportCSV、MKLAB.registerExport）、valuation.js（MKLAB_VAL）
 * 所有使用者可控的文字一律以 textContent 寫入，不使用 innerHTML 拼接。
 */
(function () {
  'use strict';
  const V = window.MKLAB_VAL;
  if (!V || !window.MKLAB) return;

  const PER = 10;
  const PREF_KEY = 'mklab.screener.dcf.params';
  const DEFAULTS = { g1: 8, g2: 4, gT: 2, wacc: 9, yield: 5 };
  const VAL_COLS = ['sym', 'name', 'price', 'val_graham', 'val_pe', 'val_pb', 'val_yield', 'val_ref', 'val_upside'];
  const cache = {};          // market -> normalized rows
  let market = 'tw';
  let valTable = null;
  let activated = false;
  let selected = null;       // 目前在計算機選取的標的
  let lastValRows = [];      // 目前估值表的篩選結果（供 CSV 匯出）

  function fmtNum(x, d) {
    if (x == null || !isFinite(x)) return '-';
    return Number(x).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d });
  }
  function el(id) { return document.getElementById(id); }
  function setText(id, txt) { const n = el(id); if (n) n.textContent = txt; }

  // ---------- 參數記憶（僅記住假設參數，不記住個股資料） ----------
  function storage() {
    try { return window.localStorage || null; } catch (e) { return null; }
  }
  function loadPrefs() {
    const st = storage();
    if (!st) return;
    let p = null;
    try { p = JSON.parse(st.getItem(PREF_KEY) || 'null'); } catch (e) { p = null; }
    if (!p || typeof p !== 'object') return;
    const map = { g1: 'dcf_g1', g2: 'dcf_g2', gT: 'dcf_gT', wacc: 'dcf_wacc', yield: 'dcfYield' };
    Object.keys(map).forEach(k => {
      const v = Number(p[k]);
      if (isFinite(v)) setInput(map[k], v);
    });
  }
  function savePrefs() {
    const st = storage();
    if (!st) return;
    const p = { g1: num('dcf_g1'), g2: num('dcf_g2'), gT: num('dcf_gT'), wacc: num('dcf_wacc'), yield: num('dcfYield') };
    try { st.setItem(PREF_KEY, JSON.stringify(p)); } catch (e) { /* 配額或隱私模式：忽略 */ }
  }

  // ---------- 資料正規化 ----------
  function normTw(doc) {
    const rows = (doc && doc.stocks) || [];
    return rows
      .filter(s => s.security_type === 'stock' && s.price > 0)
      .map(s => {
        const sharesMln = s.shares ? s.shares / 1e6 : null;
        // 基期自由現金流估算：以稅後淨利（EPS × 股數）近似，僅供參考（未扣資本支出）
        const fcf = (s.eps != null && sharesMln != null) ? Number((s.eps * sharesMln).toFixed(2)) : null;
        return {
          sym: s.sym, name: s.name, price: s.price, pe: s.pe, pb: s.pb, eps: s.eps,
          group: s.ind || null,
          cashDividend: s.div_cash_latest,           // 每股現金股利（NT$）
          sharesMln, netDebt: null, currency: 'NT$',
          fcf,
        };
      });
  }
  function normUs(doc) {
    return ((doc && doc.stocks) || [])
      .filter(s => s.price > 0)
      .map(s => ({
        sym: s.sym, name: s.name, price: s.price, pe: s.pe, pb: s.pb, eps: s.eps,
        group: s.industry || s.sector || null,
        cashDividend: (s.div != null) ? s.price * s.div / 100 : null,
        sharesMln: s.shares_mln,
        fcf: s.fcf_musd,
        netDebt: (s.debt_musd != null && s.cash_musd != null) ? s.debt_musd - s.cash_musd : null,
        currency: 'US$',
      }));
  }
  function loadMarket(m) {
    if (cache[m]) return Promise.resolve(cache[m]);
    const p = (m === 'tw')
      ? MKLAB.data.json('stocks').then(normTw)
      : MKLAB.data.json('us/us-stocks').then(normUs);
    return p.then(rows => (cache[m] = rows));
  }

  // ---------- 估值指標表 ----------
  function targetYield() {
    const v = parseFloat((el('dcfYield') || {}).value);
    return (isFinite(v) && v > 0) ? v : DEFAULTS.yield;
  }
  function buildValRows(rows) {
    const med = {
      pe: V.industryMedian(rows, 'group', 'pe', [0, 100], 3),
      pb: V.industryMedian(rows, 'group', 'pb', [0, 50], 3),
    };
    return rows.map(r => {
      const v = V.valuationRow(r, med, { targetYieldPct: targetYield() });
      return Object.assign({}, r, {
        val_graham: v.graham, val_pe: v.pe, val_pb: v.pb, val_yield: v.yield,
        val_ref: v.ref, val_upside: v.upside,
      });
    });
  }
  // 「綜合參考價上漲空間 ≥ X%」：注意這是估值指標的參考價，不是 DCF 內在價值
  function minUpside() {
    const raw = (el('dcfMinUpside') || {}).value;
    if (raw === undefined || raw === null || String(raw).trim() === '') return null;
    const v = parseFloat(raw);
    return isFinite(v) ? v : null;
  }
  function applyVal() {
    const rows0 = cache[market];
    if (!rows0) return;
    const q = ((el('dcfSearch') || {}).value || '').trim().toUpperCase();
    const min = minUpside();
    let rows = buildValRows(rows0);
    if (q) rows = rows.filter(r => (r.sym || '').toUpperCase().includes(q) || (r.name || '').toUpperCase().includes(q));
    if (min !== null) rows = rows.filter(r => r.val_upside != null && r.val_upside >= min);
    lastValRows = rows;
    const tail = min !== null ? `；上漲空間 ≥ ${min}%` : '';
    setText('dcfValCount', `符合：${rows.length} / ${rows0.length} 檔（${market === 'tw' ? '台股' : '美股'}，缺 EPS 或 PB 者不計入${tail}）`);
    if (!valTable) {
      valTable = MKLAB.DataTable('dcfValTable', {
        cols: VAL_COLS, rows, pageSize: PER, pagerId: 'dcfValPager', defaultSort: 'val_upside',
      });
    } else {
      valTable.setRows(rows);
    }
  }
  function exportValCSV() {
    if (!lastValRows.length) { alert('目前沒有可匯出的估值資料'); return; }
    MKLAB.exportCSV(lastValRows, VAL_COLS, {
      filename: 'mklab-dcf-valuation-' + new Date().toISOString().slice(0, 10),
      source: 'mklab-stock 估值指標（同產業中位數）',
      method: '綜合參考價為 Graham、PE、PB、殖利率合理價的中位數；僅供研究參考，不構成投資建議',
    });
  }
  if (typeof MKLAB.registerExport === 'function') {
    MKLAB.registerExport('匯出 DCF 估值表 CSV（目前分頁）', exportValCSV);
  }

  // ---------- DCF 計算機 ----------
  function num(id) {
    const v = parseFloat((el(id) || {}).value);
    return isFinite(v) ? v : null;
  }
  function setInput(id, v) { const n = el(id); if (n) n.value = (v == null || !isFinite(v)) ? '' : String(v); }

  function selectStock(sym) {
    const rows = cache[market] || [];
    selected = rows.find(r => r.sym === String(sym).trim()) || null;
    if (!selected) { setText('dcfNote', '找不到此代號，請從清單選取。'); return; }
    const s = selected;
    setText('dcfNote', `${s.sym} ${s.name}｜單位：${s.currency} 百萬、百萬股`);
    setInput('dcf_price', s.price);
    setInput('dcf_shares', s.sharesMln != null ? Number(s.sharesMln.toFixed(4)) : null);
    setInput('dcf_fcf', s.fcf != null ? Number(s.fcf.toFixed(2)) : null);
    setInput('dcf_netdebt', s.netDebt != null ? Number(s.netDebt.toFixed(2)) : 0);
    if (market === 'tw') {
      setText('dcfFcfHint', '台股：已以稅後淨利（EPS × 股數）估算基期 FCF，僅供參考（未扣資本支出）；可依財報手動調整。');
    } else {
      setText('dcfFcfHint', s.fcf == null ? '此股票缺少自由現金流資料，請手動輸入。' : '已由 yfinance 預填（TTM 自由現金流，USD 百萬）。');
    }
    calc();
  }

  // opts.save === false 時不寫入記憶（用於程式內部的重設與切換，避免覆蓋使用者設定）
  function calc(opts) {
    const base = {
      fcf0: num('dcf_fcf'), g1: num('dcf_g1'), g2: num('dcf_g2'), gT: num('dcf_gT'),
      wacc: num('dcf_wacc'), shares: num('dcf_shares'), netDebt: num('dcf_netdebt') || 0,
    };
    if (!(opts && opts.save === false)) savePrefs();
    const out = el('dcfOut'), sens = el('dcfSens');
    if (!out || !sens) return;
    out.textContent = '';
    sens.textContent = '';
    const r = V.dcf(base);
    if (!r.ok) {
      const p = document.createElement('p');
      p.className = 'muted-small-top';
      p.textContent = '無法計算：' + r.reason;
      out.appendChild(p);
      return;
    }
    const price = selected ? selected.price : null;
    const cur = selected ? selected.currency : '';
    const upside = (price && price > 0) ? (r.perShare / price - 1) * 100 : null;
    const mos = (price && price > 0) ? (r.perShare - price) / r.perShare * 100 : null; // vs intrinsic
    const vd = verdictOf(mos);

    // --- 結論卡 ---
    out.appendChild(heroCards(r.perShare, cur, price, upside, mos, vd));

    // --- 簡易儀表（如低估/公允/高估） ---
    out.appendChild(buildGauge(price, r.perShare));

    // --- 文字解讀 ---
    const readout = document.createElement('p');
    readout.className = 'dcf-readout';
    readout.textContent = readoutText(base, r, price, mos, vd);
    out.appendChild(readout);

    // --- 估值拆解表（未來10年FCF現值／終值／EV／淨負債／Equity） ---
    out.appendChild(breakdownTable(r, base, base.shares));

    // --- 5-年 FCF 現值柱狀圖（簡易條圖） ---
    out.appendChild(fcfBars(r.fcfs));

    // --- 敏感度表 ---
    const waccs = [-2, -1, 0, 1, 2].map(d => base.wacc + d).filter(w => w > base.gT);
    const gTs = [-1, -0.5, 0, 0.5, 1].map(d => base.gT + d);
    const grid = V.sensitivity(base, waccs, gTs);
    const title = document.createElement('h3');
    title.textContent = '敏感度：每股內在價值（列＝折現率 WACC，欄＝永續成長率）';
    sens.appendChild(title);
    const table = document.createElement('table');
    table.className = 'dcf-sens';
    const thead = document.createElement('tr');
    thead.appendChild(document.createElement('th'));
    gTs.forEach(g => { const th = document.createElement('th'); th.textContent = g.toFixed(1) + '%'; thead.appendChild(th); });
    table.appendChild(thead);
    waccs.forEach((w, i) => {
      const tr = document.createElement('tr');
      const th = document.createElement('th'); th.textContent = w.toFixed(1) + '%'; tr.appendChild(th);
      gTs.forEach((g, j) => {
        const td = document.createElement('td');
        const v = grid[i][j];
        td.textContent = v == null ? '-' : fmtNum(v, 2);
        if (i === 2 && j === 2) td.className = 'dcf-center';
        if (v != null && price) td.title = (v / price * 100 - 100).toFixed(1) + '% vs 股價';
        tr.appendChild(td);
      });
      table.appendChild(tr);
    });
    sens.appendChild(table);
  }

  function verdictOf(mos) {
    if (mos == null || !isFinite(mos)) return { cls: 'v-na', label: '資料不足' };
    if (mos >= 40) return { cls: 'v-deep', label: '深度低估' };
    if (mos >= 15) return { cls: 'v-under', label: '低估' };
    if (mos >= -15) return { cls: 'v-fair', label: '合理' };
    if (mos >= -40) return { cls: 'v-over', label: '高估' };
    return { cls: 'v-deep-over', label: '嚴重高估' };
  }
  function pctFmt(x, dec) {
    if (x == null || !isFinite(x)) return '-';
    return (x >= 0 ? '+' : '') + Number(x).toFixed(dec || 1) + '%';
  }
  function heroCards(intrinsic, cur, price, upside, mos, vd) {
    const wrap = document.createElement('div'); wrap.className = 'dcf-hero';
    const card = document.createElement('div'); card.className = 'dcf-card';
    card.innerHTML =
      '<div class="k">每股內在價值</div>' +
      '<div class="v ' + vd.cls + '">' + fmtNum(intrinsic, 2) + ' ' + cur + '</div>' +
      '<div class="s">' + vd.label + '</div>';
    const card2 = document.createElement('div'); card2.className = 'dcf-card';
    card2.innerHTML =
      '<div class="k">目前股價（' + cur + '）</div>' +
      '<div class="v">' + fmtNum(price, 2) + '</div>' +
      '<div class="s">安全邊際 <span class="dcf-verdict">' + pctFmt(mos) + '</span>' +
      '（上漲空間 ' + pctFmt(upside) + '）</div>';
    wrap.appendChild(card); wrap.appendChild(card2);
    return wrap;
  }
  function buildGauge(price, intrinsic) {
    const wrap = document.createElement('div');
    wrap.className = 'dcf-gauge';
    const track = document.createElement('div');
    track.className = 'dcf-scale-track';
    ['s1', 's2', 's3', 's4', 's5'].forEach(c => {
      const seg = document.createElement('span'); seg.className = 'seg ' + c; track.appendChild(seg);
    });
    const needle = document.createElement('i');
    needle.className = 'dcf-needle';
    track.appendChild(needle);
    wrap.appendChild(track);
    const legend = document.createElement('div');
    legend.className = 'dcf-scale-legend';
    ['深度低估', '公允價值', '嚴重高估'].forEach(t => {
      const s = document.createElement('span'); s.textContent = t; legend.appendChild(s);
    });
    wrap.appendChild(legend);
    let p = 0.5;
    if (intrinsic > 0 && price > 0) {
      const ratio = price / intrinsic;  // 1.0 = 公允，<1 低估，>1 高估
      p = Math.min(1, Math.max(0, (ratio - 0.5) / 1.0)); // 0.5→左(低估)  1→右(高估)
    }
    needle.style.left = Math.round(p * 100) + '%';
    return wrap;
  }
  function readoutText(base, r, price, mos, vd) {
    const g1 = base.g1, g2 = base.g2, gT = base.gT, wacc = base.wacc;
    const tvShare = (r.tvShare == null) ? '-' : Number(r.tvShare.toFixed(0)) + '%';
    let text = '';
    if (price && price > 0 && intrinsicNum(r.perShare)) {
      text += `在 g1 ${g1}%、g2 ${g2}、永續成長 ${gT}、WACC ${wacc}% 的假設下，每股內在價值約 NT$${fmtNum(r.perShare,2)}，較目前股價 NT$${fmtNum(price,2)} ${vd.label}（安全邊際 ${pctFmt(mos)}，上漲空間 ${pctFmt(upsideOf(r.perShare,price))}）。`;
    } else {
      text += `在 g1 ${g1}%、g2 ${g2}、永續成長 ${gT}、WACC ${wacc}% 的假設下，計算每股內在價值 ${fmtNum(r.perShare,2)}；${vd.label}。`;
    }
    text += ` 未來10年FCF現值佔 EV ${tvShare}，結果對 WACC 與永續成長率敏感，僅供研究參考，不構成投資建議。`;
    return text;
  }
  function intrinsicNum(v){return v!=null&&isFinite(v);}
  function upsideOf(intrinsic,price){return intrinsic>0&&price>0?(intrinsic/price-1)*100:null;}
  function breakdownTable(r, base, sharesMln) {
    const tbl = document.createElement('table'); tbl.className = 'dcf-table';
    const rows = [
      ['未來 10 年 FCF 現值', fmtNum(r.pvFcf, 0)],
      ['終值現值', fmtNum(r.pvTv, 0)],
      ['企業價值 EV', fmtNum(r.ev, 0)],
      ['減：淨負債', fmtNum(base.netDebt, 0)],
      ['股東權益值', fmtNum((r.ev - base.netDebt), 0)],
      ['每股內在價值', fmtNum(r.perShare, 2)],
    ];
    rows.forEach(([k,v])=>{
      const tr=document.createElement('tr');
      const td=document.createElement('td'); td.textContent=k; tr.appendChild(td);
      const td2=document.createElement('td'); td2.textContent=v; tr.appendChild(td2);
      tbl.appendChild(tr);
    });
    const tr=document.createElement('tr'); tr.className='tot';
    const td=document.createElement('td'); td.textContent='計算基期 FCF（稅後淨利估算）'; tr.appendChild(td);
    const td2=document.createElement('td'); td2.textContent=fmtNum(base.fcf0,0)+' 百萬'; tr.appendChild(td2);
    tbl.appendChild(tr);
    return tbl;
  }
  function fcfBars(fcfs) {
    const wrap = document.createElement('div');
    wrap.className = 'dcf-bars';
    const h = document.createElement('div');
    h.className = 'k';
    h.textContent = '未來 10 年 FCF 現值（條圖，百萬）';
    wrap.appendChild(h);
    const bars = document.createElement('div');
    bars.className = 'dcf-bars-inner';
    const maxPv = Math.max(...fcfs.map(f => f.pv)) || 1;
    fcfs.forEach(f => {
      const bar = document.createElement('div'); bar.className = 'bar';
      const i = document.createElement('i'); i.style.height = (f.pv / maxPv * 100) + '%';
      i.title = '第' + f.year + '年 FCF ' + fmtNum(f.fcf, 0) + '／現值 ' + fmtNum(f.pv, 0);
      bar.appendChild(i);
      const b = document.createElement('b'); b.textContent = 'Y' + f.year; bar.appendChild(b);
      bars.appendChild(bar);
    });
    wrap.appendChild(bars);
    return wrap;
  }

  // 清除個股選取與個股欄位，保留假設參數
  function clearSelection() {
    selected = null;
    ['dcf_price', 'dcf_fcf', 'dcf_shares'].forEach(id => setInput(id, null));
    setInput('dcf_netdebt', 0);
    setText('dcfNote', '請選擇股票，或直接輸入參數。');
    setText('dcfFcfHint', '');
  }

  // 「重設」：假設參數回到預設值，並寫入記憶
  function resetCalc() {
    clearSelection();
    setInput('dcf_g1', DEFAULTS.g1); setInput('dcf_g2', DEFAULTS.g2);
    setInput('dcf_gT', DEFAULTS.gT); setInput('dcf_wacc', DEFAULTS.wacc);
    setInput('dcfYield', DEFAULTS.yield);
    calc();
  }

  function buildPicker() {
    const dl = el('dcfList');
    if (!dl) return;
    dl.textContent = '';
    (cache[market] || []).forEach(r => {
      const o = document.createElement('option');
      o.value = r.sym;
      o.label = r.name || '';
      dl.appendChild(o);
    });
  }

  // 切換市場：只清除個股選取，保留使用者目前的假設參數
  function setMarket(m, btn) {
    market = m;
    document.querySelectorAll('#dcfMarket button').forEach(b => b.classList.toggle('on', b === btn));
    clearSelection();
    loadMarket(m).then(() => { buildPicker(); applyVal(); calc({ save: false }); }).catch(() => setText('dcfValCount', '資料載入失敗'));
  }

  function activate() {
    if (activated) return;
    activated = true;
    setInput('dcf_g1', DEFAULTS.g1); setInput('dcf_g2', DEFAULTS.g2);
    setInput('dcf_gT', DEFAULTS.gT); setInput('dcf_wacc', DEFAULTS.wacc);
    setInput('dcfYield', DEFAULTS.yield);
    loadPrefs();                       // 若有記憶則覆蓋預設值
    clearSelection();
    calc({ save: false });
    loadMarket('tw').then(() => { buildPicker(); applyVal(); }).catch(() => setText('dcfValCount', '資料載入失敗'));
  }

  window.MKLAB_DCF = { activate, setMarket, applyVal, selectStock, calc, resetCalc, exportValCSV };
})();
