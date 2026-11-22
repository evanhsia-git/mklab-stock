/*
 * screener-dcf.js — Screener「DCF 估值」分頁（估值參考表 + 個股細節 + 5 年 DCF 試算）
 * 依賴：mklab-core.js（MKLAB.data、MKLAB.DataTable、MKLAB.exportCSV、MKLAB.registerExport）、valuation.js（MKLAB_VAL）
 * 安全：所有使用者可控或資料來源的文字一律以 textContent 寫入，不使用 innerHTML 拼接。
 */
(function () {
  'use strict';
  const V = window.MKLAB_VAL;
  if (!V || !window.MKLAB) return;

  const PER = 10;
  const PREF_KEY = 'mklab.screener.dcf.params';
  const DEFAULTS = { g: 8, gT: 2, wacc: 9, yield: 5 };
  const VAL_COLS = ['sym', 'name', 'price', 'val_graham', 'val_pe', 'val_pb', 'val_yield', 'val_ref', 'val_upside', 'val_note'];
  const cache = {};        // market -> normalized rows
  const valCache = {};     // market -> valuation rows（依目前參數）
  let market = 'tw';
  let valTable = null;
  let activated = false;
  let selected = null;     // 目前選取的估值列
  let lastValRows = [];    // 估值表目前篩選結果（供 CSV）

  function el(id) { return document.getElementById(id); }
  function setText(id, txt) { const n = el(id); if (n) n.textContent = txt; }
  function fmt(x, d) {
    if (x == null || !isFinite(x)) return '—';
    return Number(x).toLocaleString('zh-TW', { maximumFractionDigits: d, minimumFractionDigits: d });
  }
  function fmtPct(x) { return x == null || !isFinite(x) ? '—' : (x >= 0 ? '+' : '') + fmt(x, 1) + '%'; }
function num(id) {
  const el = document.getElementById(id);
  if (!el || el.value === '' || el.value === null) return null;
  const v = parseFloat(el.value);
  return isFinite(v) ? v : null;
}
  function setInput(id, v) { const n = el(id); if (n) n.value = (v == null || !isFinite(v)) ? '' : String(v); }
  function el2(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  // ---------- 參數記憶（只記假設參數，不記個股資料） ----------
  function storage() { try { return window.localStorage || null; } catch (e) { return null; } }
  function loadPrefs() {
    const st = storage(); if (!st) return;
    let p = null;
    try { p = JSON.parse(st.getItem(PREF_KEY) || 'null'); } catch (e) { p = null; }
    if (!p || typeof p !== 'object') return;
    const map = { g: 'dvG', gT: 'dvGT', wacc: 'dvWacc', yield: 'dvYield' };
    Object.keys(map).forEach(k => { const v = Number(p[k]); if (isFinite(v)) setInput(map[k], v); });
  }
  function savePrefs() {
    const st = storage(); if (!st) return;
    try {
      st.setItem(PREF_KEY, JSON.stringify({
        g: num('dvG'), gT: num('dvGT'), wacc: num('dvWacc'), yield: num('dvYield'),
      }));
    } catch (e) { /* 配額或隱私模式：略過 */ }
  }

  // ---------- 資料正規化 ----------
  function normTw(doc) {
    return ((doc && doc.stocks) || [])
      .filter(s => s.security_type === 'stock' && s.price > 0)
      .map(s => ({
        sym: s.sym, name: s.name, price: s.price, pe: s.pe, pb: s.pb,
        divPct: s.div, group: s.ind || null,
        sharesMln: s.shares ? s.shares / 1e6 : null,
        fcf: null,                                   // 台股目前沒有現金流資料
        netDebt: null,
        isBank: /金融|金控|銀行|保險|證券|金融保險/i.test(s.ind || ''),
        currency: 'NT$',
        security_type: s.security_type,
      }));
  }
  function normUs(doc) {
    return ((doc && doc.stocks) || [])
      .filter(s => s.price > 0)
      .map(s => ({
        sym: s.sym, name: s.name, price: s.price, pe: s.pe, pb: s.pb,
        divPct: s.div, group: s.industry || s.sector || null,
        security_type: s.security_type,
        isBank: /bank|bancorp|financial services/i.test(s.industry || s.sector || ''),
        sharesMln: (s.shares_mln != null) ? s.shares_mln : ((s.market_cap != null && s.market_cap > 0 && s.price > 0) ? s.market_cap / s.price / 1e6 : null),
        fcf: (s.fcf_musd != null) ? s.fcf_musd : null,
        netDebt: (s.debt_musd != null && s.cash_musd != null) ? (s.debt_musd - s.cash_musd) : null,
        currency: 'US$',
      }));
  }
  function loadMarket(m) {
    if (cache[m]) return Promise.resolve(cache[m]);
    const p = (m === 'tw') ? MKLAB.data.json('stocks').then(normTw) : MKLAB.data.json('us/us-stocks').then(normUs);
    return p.then(rows => (cache[m] = rows));
  }

  // ---------- 估值參考表 ----------
  function targetYield() {
    const v = parseFloat((el('dvYield') || {}).value);
    return (isFinite(v) && v > 0) ? v : DEFAULTS.yield;
  }
  function noteFor(v) {
    if (v.ref == null) return '方法不足';
    if (v.upside != null && v.upside > 100) return '差異大';
    if (v.upside != null && v.upside < -50) return '偏高';
    return '';
  }
  function buildValRows(rows) {
    const med = {
      pe: V.industryMedian(rows, 'group', 'pe', V.BOUNDS.pe, 5),
      pb: V.industryMedian(rows, 'group', 'pb', V.BOUNDS.pb, 5),
    };
    return rows.map(r => {
      const v = V.valuationRow(r, med, { targetYieldPct: targetYield() });
      return Object.assign({}, r, {
        val_graham: v.graham, val_pe: v.pe, val_pb: v.pb, val_yield: v.yield,
        val_ref: v.ref, val_upside: v.upside, val_note: noteFor(v), _v: v,
      });
    });
  }
  function minUpside() {
    const raw = (el('dvMinUpside') || {}).value;
    if (raw === undefined || raw === null || String(raw).trim() === '') return null;
    const v = parseFloat(raw);
    return isFinite(v) ? v : null;
  }
  function applyVal() {
    const rows0 = cache[market];
    if (!rows0) return;
    const all = buildValRows(rows0);
    valCache[market] = all;
    const q = ((el('dvSearch') || {}).value || '').trim().toUpperCase();
    const min = minUpside();
    let rows = all;
    if (q) rows = rows.filter(r => (r.sym || '').toUpperCase().includes(q) || (r.name || '').toUpperCase().includes(q));
    if (min !== null) rows = rows.filter(r => r.val_upside != null && r.val_upside >= min);
    lastValRows = rows;
    const tail = min !== null ? `；參考價上漲 ≥ ${min}%` : '';
    setText('dvCount', `符合 ${rows.length} / ${rows0.length} 檔（${market === 'tw' ? '台股' : '美股'}${tail}）`);
    if (!valTable) {
      // 不使用共用的頁碼列（1000+ 筆會產生 100+ 個按鈕），改用本頁的精簡翻頁
      valTable = MKLAB.DataTable('dvTable', {
        cols: VAL_COLS, rows, pageSize: PER, defaultSort: 'val_upside',
      });
    } else {
      valTable.setRows(rows);
    }
    renderPager();
  }

  // 精簡翻頁：‹ 上一頁｜第 x / y 頁｜下一頁 ›
  function renderPager() {
    const box = el('dvPager');
    if (!box || !valTable) return;
    box.textContent = '';
    const total = Math.max(1, Math.ceil(valTable.rows.length / PER));
    const cur = Math.min(Math.max(1, valTable.page || 1), total);
    const go = (p) => { valTable.page = p; valTable.render(); renderPager(); };
    const prev = el2('button', 'dv-btn', '‹ 上一頁');
    prev.type = 'button'; prev.disabled = cur <= 1;
    prev.addEventListener('click', () => go(cur - 1));
    const info = el2('span', 'dv-count', `第 ${cur} / ${total} 頁`);
    const next = el2('button', 'dv-btn', '下一頁 ›');
    next.type = 'button'; next.disabled = cur >= total;
    next.addEventListener('click', () => go(cur + 1));
    box.appendChild(prev); box.appendChild(info); box.appendChild(next);
  }
  function exportValCSV() {
    if (!lastValRows.length) { alert('目前沒有可匯出的估值資料'); return; }
    MKLAB.exportCSV(lastValRows, VAL_COLS, {
      filename: 'mklab-dcf-valuation-' + new Date().toISOString().slice(0, 10),
      source: 'mklab-stock 估值參考（同產業中位數）',
      method: '參考價為 Graham、PE、PB、殖利率合理價的中位數；僅供研究參考，不構成投資建議',
    });
  }
  if (typeof MKLAB.registerExport === 'function') {
    MKLAB.registerExport('匯出 DCF 估值表 CSV（目前分頁）', exportValCSV);
  }

  // ---------- 個股細節 ----------
  function findRow(sym) {
    const rows = valCache[market] || [];
    return rows.find(r => r.sym === String(sym).trim()) || null;
  }

  function renderStock(r) {
    const v = r._v;
    setText('dvName', `${r.sym}　${r.name || ''}`);
    setText('dvMeta', `股價 ${fmt(r.price, 2)} ${r.currency}｜${r.group || '未分類'}｜PE ${r.pe != null ? fmt(r.pe, 1) : '—'}｜PB ${r.pb != null ? fmt(r.pb, 2) : '—'}`);

    // 方法長條圖：以股價為 1 倍
    const bars = el('dvBars');
    bars.textContent = '';
    const items = [
      ['Graham', v.graham, false],
      ['PE 合理價', v.pe, false],
      ['PB 合理價', v.pb, false],
      ['殖利率合理價', v.yield, false],
      ['綜合參考價', v.ref, true],
    ];
    items.forEach(([label, val, isRef]) => {
      const row = el2('div', 'dv-bar-row');
      row.appendChild(el2('div', 'dv-bar-label', label));
      if (val == null) {
        row.appendChild(el2('div', 'dv-hint', '資料不足或超出合理範圍'));
        row.appendChild(el2('div', 'dv-bar-val', '—'));
      } else {
        const track = el2('div', 'dv-track');
        const fill = el2('div', 'dv-fill' + (isRef ? ' is-ref' : ''));
        const ratio = Math.max(0, Math.min(val / r.price, 3));
        fill.style.width = (ratio / 3 * 100).toFixed(1) + '%';
        track.appendChild(fill);
        const marker = el2('div', 'dv-marker');
        marker.style.left = (1 / 3 * 100).toFixed(1) + '%';
        track.appendChild(marker);
        row.appendChild(track);
        row.appendChild(el2('div', 'dv-bar-val', fmt(val, 2) + '（' + fmtPct(V.upsidePct(val, r.price)) + '）'));
      }
      bars.appendChild(row);
    });

    const flag = el('dvFlag');
    flag.textContent = '';
    if (v.ref == null) flag.textContent = '可用方法不足 2 種，未提供綜合參考價。';
    else if (v.upside > 100) flag.textContent = '參考價高於股價 2 倍以上，差異大，請先檢查資料與一次性獲利。';
    else if (v.upside < -50) flag.textContent = '參考價低於股價一半以下，請確認是否為高估或資料異常。';
  }

  function selectStock(sym) {
    const r = findRow(sym);
    if (!r) { setText('dvName', '找不到此代號，請從清單選取。'); return; }
    selected = r;
    renderStock(r);
    setInput('dvPrice', r.price);
    setInput('dvShares', r.sharesMln != null ? Number(r.sharesMln.toFixed(4)) : null);
    setInput('dvFcf', r.fcf != null ? Number(r.fcf.toFixed(2)) : null);
    setInput('dvNetDebt', r.netDebt != null ? Number(r.netDebt.toFixed(2)) : null);
    if (market === 'tw') {
      setText('dvFcfHint', '目前台股沒有自動取得完整現金流量表資料，請依財報自行估算並輸入 FCF 代理值（NT$ 百萬）。');
    } else {
      setText('dvFcfHint', r.fcf == null ? '此股票缺少自由現金流，請自行輸入。' : '已由 yfinance 過去 12 個月資料帶入（USD 百萬）。');
    }
    applyMarketText();
    calc();
  }

  // ---------- DCF 試算與圖表 ----------
  function millionsLabel(v) {
    if (v == null || !isFinite(v)) return '—';
    return fmt(v, 0) + ' 百萬';
  }

  function calc() {
    const base = {
      fcf0: num('dvFcf'), g: num('dvG'), gT: num('dvGT'), wacc: num('dvWacc'),
      shares: num('dvShares'), netDebt: num('dvNetDebt'),
    };
    savePrefs();
    const out = el('dvResult'), warnBox = el('dvWarn'), chart = el('dvChart'), sens = el('dvSens');
    [out, warnBox, chart, sens].forEach(n => { if (n) n.textContent = ''; });
    if (!out) return;

    const blocked = selected && (selected.security_type !== 'stock' || selected.isBank);
    if (blocked) {
      let msg = '';
      if (selected.security_type !== 'stock') {
        msg = '模型不適用：ETF 不建議使用一般企業 EV / Net Debt / WACC DCF 估值，請改用其他方法。';
      } else {
        msg = '模型不適用：金融業（銀行）不建議使用一般企業 EV / Net Debt / WACC DCF 估值，請改用其他方法。';
      }
      out.appendChild(el2('p', 'dv-hint is-error', msg));
      return;
    }

    const r = V.dcf(base);
    if (!r.ok) {
      out.appendChild(el2('p', 'dv-hint is-error', '無法計算：' + r.reason));
      return;
    }
    const price = selected ? selected.price : null;
    const cur = selected ? selected.currency : '';
    const up = (price && price > 0) ? (r.perShare / price - 1) * 100 : null;

    const head = el2('div', '');
    head.appendChild(el2('div', 'dv-sub', '每股內在價值（DCF）'));
    head.appendChild(el2('div', 'dv-big', (selected ? fmt(r.perShare, 2) + ' ' + cur : fmt(r.perShare, 2))));
    const upEl = el2('div', up == null ? 'dv-sub' : (up >= 0 ? 'dv-up' : 'dv-down'), up == null ? '選擇股票後顯示與股價的差距' : '相對目前股價 ' + fmtPct(up));
    head.appendChild(upEl);
    out.appendChild(head);

    const kpis = el2('div', 'dv-kpis');
    [
      ['企業價值 EV', millionsLabel(r.ev)],
      ['終值佔 EV', r.tvShare != null ? fmt(r.tvShare, 1) + '%' : '—'],
      ['5 年 FCF 現值', millionsLabel(r.pvFcf)],
      ['終值現值', millionsLabel(r.pvTv)],
    ].forEach(([k, v]) => {
      const cell = el2('div', 'dv-kpi');
      cell.appendChild(el2('span', '', k));
      cell.appendChild(el2('b', '', v));
      kpis.appendChild(cell);
    });
    out.appendChild(kpis);

    // EV 組成堆疊條
    const total = r.pvFcf + r.pvTv;
    const stackWrap = el2('div', '');
    stackWrap.appendChild(el2('div', 'dv-sub', '企業價值組成'));
    const stack = el2('div', 'dv-stack');
    const a = el2('div', 's-fcf'); a.style.width = (r.pvFcf / total * 100).toFixed(1) + '%';
    const b = el2('div', 's-tv'); b.style.width = (r.pvTv / total * 100).toFixed(1) + '%';
    stack.appendChild(a); stack.appendChild(b);
    stackWrap.appendChild(stack);
    const lg = el2('div', 'dv-stack-legend');
    const l1 = el2('span', ''); l1.appendChild(el2('i', 'dv-dot')); l1.childNodes[0].style.background = 'var(--chart-1)';
    l1.appendChild(document.createTextNode('5 年 FCF 現值 ' + fmt(r.pvFcf / total * 100, 1) + '%'));
    const l2 = el2('span', ''); l2.appendChild(el2('i', 'dv-dot')); l2.childNodes[0].style.background = 'var(--chart-3)';
    l2.appendChild(document.createTextNode('終值現值 ' + fmt(r.pvTv / total * 100, 1) + '%'));
    lg.appendChild(l1); lg.appendChild(l2);
    stackWrap.appendChild(lg);
    out.appendChild(stackWrap);

    // 警告
    if (r.warnings.length) {
      const box = el2('div', 'dv-warn');
      r.warnings.forEach(w => box.appendChild(el2('p', '', w)));
      warnBox.appendChild(box);
    }

    // 5 年 FCF 與現值長條圖
    chart.appendChild(el2('div', 'dv-sub', '未來 5 年自由現金流與現值（百萬）'));
    const legend = el2('div', 'dv-chart-legend');
    const k1 = el2('span', ''); const d1 = el2('i', ''); d1.style.background = 'var(--chart-1)';
    k1.appendChild(d1); k1.appendChild(document.createTextNode('自由現金流'));
    const k2 = el2('span', ''); const d2 = el2('i', ''); d2.style.background = 'var(--chart-3)';
    k2.appendChild(d2); k2.appendChild(document.createTextNode('現值（折現後）'));
    legend.appendChild(k1); legend.appendChild(k2);
    chart.appendChild(legend);
    chart.appendChild(buildBarChart(r.fcfs));

    // 敏感度
    const waccs = [-2, -1, 0, 1, 2].map(d => base.wacc + d).filter(w => w > base.gT);
    const gTs = [-1, -0.5, 0, 0.5, 1].map(d => base.gT + d);
    const grid = V.sensitivity(base, waccs, gTs);
    const table = el2('table', 'dv-sens');
    const thead = el2('tr', '');
    thead.appendChild(el2('th', '', 'WACC \\ 永續'));
    gTs.forEach(g => thead.appendChild(el2('th', '', g.toFixed(1) + '%')));
    table.appendChild(thead);
    waccs.forEach((w, i) => {
      const tr = el2('tr', '');
      tr.appendChild(el2('th', '', w.toFixed(1) + '%'));
      gTs.forEach((g, j) => {
        const v = grid[i][j];
        const td = el2('td', '', v == null ? '—' : fmt(v, 2));
        if (i === 2 && j === 2) td.classList.add('is-center');
        if (v != null && price) td.classList.add(v >= price ? 'is-up' : 'is-down');
        tr.appendChild(td);
      });
      table.appendChild(tr);
    });
    sens.appendChild(table);
  }

  // 軸標籤：百萬以上用「兆」，否則用「百萬」（單位與表格一致）
  function axisLabel(v) {
    if (!isFinite(v) || v <= 0) return '0';
    return v >= 1e6 ? fmt(v / 1e6, 1) + ' 兆' : fmt(v, 0) + ' 百萬';
  }

  // 純 SVG 長條圖：FCF（藍）與現值（黃），自動跟隨主題色
  function buildBarChart(years) {
    const W = 360, H = 200, pad = { l: 78, r: 10, t: 14, b: 28 };
    const innerW = W - pad.l - pad.r, innerH = H - pad.t - pad.b;
    const max = Math.max.apply(null, years.map(y => Math.max(y.fcf, y.pv)));
    const svgNS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('class', 'dv-chart');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', '未來 5 年自由現金流與現值長條圖');
    const add = (tag, attrs, text, style) => {
      const n = document.createElementNS(svgNS, tag);
      Object.keys(attrs || {}).forEach(k => n.setAttribute(k, attrs[k]));
      if (style) Object.keys(style).forEach(k => n.style.setProperty(k, style[k]));
      if (text != null) n.textContent = text;
      svg.appendChild(n);
      return n;
    };
    // 格線與刻度
    [0, 0.5, 1].forEach(f => {
      const y = pad.t + innerH * (1 - f);
      add('line', { x1: pad.l, x2: W - pad.r, y1: y, y2: y }, null, { stroke: 'var(--border)', 'stroke-width': '1' });
      add('text', { x: pad.l - 4, y: y + 4, 'text-anchor': 'end' }, axisLabel(max * f));
    });
    const slot = innerW / years.length;
    const bw = Math.min(22, slot * 0.34);
    years.forEach((y, i) => {
      const x0 = pad.l + slot * i + slot / 2;
      const hF = y.fcf / max * innerH, hP = y.pv / max * innerH;
      add('rect', { x: x0 - bw - 2, y: pad.t + innerH - hF, width: bw, height: hF, rx: 3 }, null, { fill: 'var(--chart-1)' });
      add('rect', { x: x0 + 2, y: pad.t + innerH - hP, width: bw, height: hP, rx: 3 }, null, { fill: 'var(--chart-3)' });
      add('text', { x: x0, y: H - 8, 'text-anchor': 'middle' }, '第 ' + y.year + ' 年');
    });
    return svg;
  }

  function resetCalc() {
    setInput('dvG', DEFAULTS.g); setInput('dvGT', DEFAULTS.gT);
    setInput('dvWacc', DEFAULTS.wacc); setInput('dvYield', DEFAULTS.yield);
    if (cache[market]) applyVal();
    calc();
  }

  function buildPicker() {
    const dl = el('dvList');
    if (!dl) return;
    dl.textContent = '';
    (cache[market] || []).forEach(r => {
      const o = document.createElement('option');
      o.value = r.sym;
      o.label = r.name || '';
      dl.appendChild(o);
    });
  }

  function clearDetail() {
    selected = null;
    setText('dvName', '請在上方表格點選一檔股票');
    setText('dvMeta', '');
    setText('dvFlag', '');
    setText('dvFcfHint', '');
    setText('dvHint', '');
    const bars = el('dvBars'); if (bars) bars.textContent = '';
    ['dvPrice', 'dvFcf', 'dvShares'].forEach(id => setInput(id, null));
    setInput('dvNetDebt', null);
    calc();
  }

  function setCur(sel, cur) { const n = el(sel); if (n) n.textContent = cur; }
  function applyMarketText() {
    const isTw = (market === 'tw');
    const cur = isTw ? 'NT$' : 'US$';
    setCur('dvFcfCur', cur);
    setCur('dvNetDebtCur', cur);
    setCur('dvIntro', isTw
      ? '以基期自由現金流預估未來 5 年，再以永續成長終值折現。台股目前沒有現金流資料，需自行輸入。'
      : '以基期自由現金流預估未來 5 年，再以永續成長終值折現。美股原始資料未提供自由現金流，請自行輸入。');
    // hint 由 selectStock 依檔次設定，這裡不主動清空
  }
  function setMarket(m, btn) {
    market = m;
    document.querySelectorAll('#dvMarket button').forEach(b => b.classList.toggle('on', b === btn));
    clearDetail();
    applyMarketText();
    loadMarket(m).then(() => { buildPicker(); applyVal(); })
      .catch(() => setText('dvCount', '資料載入失敗'));
  }

  function bindTableClick() {
    const t = el('dvTable');
    if (!t || t.dataset.bound) return;
    t.dataset.bound = '1';
    t.addEventListener('click', e => {
      const tr = e.target && e.target.closest ? e.target.closest('tbody tr') : null;
      if (!tr) return;
      const first = tr.querySelector('td');
      if (first) selectStock(first.textContent.trim());
    });
  }

  function activate() {
    if (activated) return;
    activated = true;
    setInput('dvG', DEFAULTS.g); setInput('dvGT', DEFAULTS.gT);
    setInput('dvWacc', DEFAULTS.wacc); setInput('dvYield', DEFAULTS.yield);
    loadPrefs();
    bindTableClick();
    clearDetail();
    loadMarket(market).then(() => { buildPicker(); applyVal(); })
      .catch(() => setText('dvCount', '資料載入失敗'));
  }

  window.MKLAB_DCF = { activate, setMarket, applyVal, selectStock, calc, resetCalc, exportValCSV };
})();
