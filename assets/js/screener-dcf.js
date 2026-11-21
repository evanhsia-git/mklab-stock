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
    return ((doc && doc.stocks) || [])
      .filter(s => s.security_type === 'stock' && s.price > 0)
      .map(s => ({
        sym: s.sym, name: s.name, price: s.price, pe: s.pe, pb: s.pb, eps: s.eps,
        group: s.ind || null,
        cashDividend: s.div_cash_latest,           // 每股現金股利（NT$）
        sharesMln: s.shares ? s.shares / 1e6 : null,
        fcf: null,                                 // 台股目前沒有現金流量資料，需手動輸入
        netDebt: null,
        currency: 'NT$',
      }));
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
      setText('dcfFcfHint', '台股目前沒有現金流量資料，請依財報或自行估算後手動輸入（NT$ 百萬）。');
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
    const upside = (price && price > 0) ? (r.perShare / price - 1) * 100 : null;
    const items = [
      ['每股內在價值', fmtNum(r.perShare, 2) + (selected ? ' ' + selected.currency : '')],
      ['目前股價', price != null ? fmtNum(price, 2) : '-'],
      ['上漲／下跌空間', upside != null ? (upside >= 0 ? '+' : '') + fmtNum(upside, 1) + '%' : '-'],
      ['企業價值 EV（百萬）', fmtNum(r.ev, 0)],
      ['未來 10 年 FCF 現值（百萬）', fmtNum(r.pvFcf, 0)],
      ['終值現值（百萬）', fmtNum(r.pvTv, 0)],
      ['終值佔 EV 比例', r.tvShare != null ? fmtNum(r.tvShare, 1) + '%' : '-'],
    ];
    const dl = document.createElement('dl');
    dl.className = 'dcf-summary';
    items.forEach(([k, v]) => {
      const dt = document.createElement('dt'); dt.textContent = k;
      const dd = document.createElement('dd'); dd.textContent = v;
      dl.appendChild(dt); dl.appendChild(dd);
    });
    out.appendChild(dl);
    if (r.tvShare != null && r.tvShare > 75) {
      const warn = document.createElement('p');
      warn.className = 'muted-small-top';
      warn.textContent = '提醒：終值佔比超過 75%，結果高度依賴永續成長率與折現率假設。';
      out.appendChild(warn);
    }

    // 敏感度表：WACC × 永續成長率
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
