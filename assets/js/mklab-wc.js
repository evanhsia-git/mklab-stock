/* mklab-wc.js — MKLAB Web Components Library (plain script, classic registration)
 * 零依賴、支援 file:// 直接開啟、非 ES module、classic script (IIFE)
 * 元件註冊使用 customElements.define，掛載到 window.MKLAB_WC 供參考
 */
(function (global) {
  'use strict';

  /* ============ 共用工具 ============ */
  function cellPct(v) {
    if (v == null) return '-';
    const n = Number(v);
    return (n > 0 ? '+' : '') + n.toFixed(2) + '%';
  }

  /* ============ 1. <mklab-kline> K 線圖元件 ============ */
  class MklabKline extends HTMLElement {
    static get observedAttributes() { return ['data-symbol', 'height']; }

    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this._chart = null;
      this._series = null;
      this._resizeHandler = null;
    }

    connectedCallback() {
      this._render();
      this._loadData();
      this._resizeHandler = () => { if (this._chart) this._chart.resize(this._container.clientWidth, this._height); };
      window.addEventListener('resize', this._resizeHandler);
    }

    disconnectedCallback() {
      if (this._resizeHandler) window.removeEventListener('resize', this._resizeHandler);
      if (this._chart) { try { this._chart.remove(); } catch (e) {} this._chart = null; this._series = null; }
    }

    attributeChangedCallback(name, oldVal, newVal) {
      if (oldVal === newVal) return;
      if (name === 'data-symbol') this._loadData();
      if (name === 'height') { this._height = parseInt(newVal, 10) || 400; this._applyHeight(); }
    }

    _render() {
      this._height = parseInt(this.getAttribute('height'), 10) || 400;
      this.shadowRoot.innerHTML = `
        <style>
          :host { display: block; width: 100%; }
          .kline-wrap { width: 100%; height: ${this._height}px; position: relative; }
        </style>
        <div class="kline-wrap" id="klineWrap"></div>
      `;
      this._container = this.shadowRoot.getElementById('klineWrap');
    }

    _applyHeight() {
      if (this._container) this._container.style.height = this._height + 'px';
      if (this._chart) this._chart.resize(this._container.clientWidth, this._height);
    }

    _loadData() {
      const sym = this.getAttribute('data-symbol') || 'TWII';
      const globalKey = sym + '_KDATA';
      let raw = window[globalKey];
      if (raw) { this._draw(raw); return; }
      // 後備：嘗試從 data-client 載入
      if (window.MKLAB && MKLAB.data && MKLAB.data.twiiKline) {
        MKLAB.data.twiiKline().then(d => { if (d && d.length) this._draw(d); });
      }
    }

    _draw(raw) {
      if (!window.LightweightCharts) { console.warn('[mklab-kline] LightweightCharts not loaded'); return; }
      if (!raw || !raw.length) return;

      if (this._chart) { try { this._chart.remove(); } catch (e) {} this._chart = null; this._series = null; }

      const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
      this._chart = LightweightCharts.createChart(this._container, {
        width: this._container.clientWidth,
        height: this._height,
        layout: { background: { type: 'solid', color: 'transparent' }, textColor: isDark ? '#9aa0a6' : '#6b7280' },
        rightPriceScale: { borderColor: isDark ? '#2a2f3a' : '#e5e7eb' },
        timeScale: { borderColor: isDark ? '#2a2f3a' : '#e5e7eb', timeVisible: true, secondsVisible: false },
        grid: { vertLines: { color: isDark ? '#2a2f3a20' : '#e5e7eb40' }, horzLines: { color: isDark ? '#2a2f3a20' : '#e5e7eb40' } },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      });
      this._series = this._chart.addCandlestickSeries({
        upColor: '#f87171', downColor: '#4ade80',
        borderUpColor: '#f87171', borderDownColor: '#4ade80',
        wickUpColor: '#f87171', wickDownColor: '#4ade80',
      });
      this._series.setData(raw);
      this._chart.timeScale().fitContent();

      window.addEventListener('resize', () => {
        if (this._chart) this._chart.resize(this._container.clientWidth, this._height);
      });
    }
  }

  /* ============ 2. <mklab-datatable> 表格元件 ============ */

  // 欄位定義表（同 mklab-core.js 的 COLUMNS）
  const COLUMNS = {
    sym:   { label: '股票代號', type: 'str', sortable: true,  fmt: r => r.sym != null ? String(r.sym) : '-' },
    name:  { label: '名稱', type: 'str', sortable: true,  fmt: r => (r.name || r.nm || '-') },
    close: { label: '收盤', type: 'num', sortable: true,  fmt: r => r.close != null ? Number(r.close).toLocaleString() : '-' },
    chg_pct: { label: '漲跌%', type: 'pct', sortable: true,  fmt: r => cellPct(r.chg_pct) },
    price: { label: '價格', type: 'num', sortable: true,  fmt: r => r.price != null ? Number(r.price).toLocaleString() : '-' },
    chg:   { label: '漲跌%', type: 'pct', sortable: true,  fmt: r => cellPct(r.chg) },
    score: { label: '綜合評分', type: 'num', sortable: true, defDir: -1, fmt: r => r.score != null ? r.score : '-' },
    pe:    { label: 'PE', type: 'num', sortable: true,  fmt: r => r.pe != null ? Number(r.pe).toFixed(2) : '-' },
    pb:    { label: 'PB', type: 'num', sortable: true,  fmt: r => r.pb != null ? Number(r.pb).toFixed(2) : '-' },
    eps:   { label: 'EPS', type: 'num', sortable: true,  fmt: r => r.eps != null ? Number(r.eps).toFixed(2) : '-' },
    roe:   { label: 'ROE', type: 'num', sortable: true,  fmt: r => (r.roe != null ? Number(r.roe).toFixed(2) : '-') },
    roa:   { label: 'ROA', type: 'num', sortable: true,  fmt: r => (r.roa != null ? Number(r.roa).toFixed(2) : '-') },
    trend: { label: '趨勢', type: 'str', sortable: true,  fmt: r => (r.trend != null ? r.trend : (r.spct != null ? (r.spct > 0 ? '+' : '') + r.spct + '%' : '-')) },
    spk:   { label: '趨勢', type: 'spark', sortable: false, fmt: r => { if (!r.spark || !r.spark.length) return '-'; const data = r.spark, min = Math.min(...data), max = Math.max(...data), rn = (max - min) || 1; const p = data.map((d, i) => `${(i / (data.length - 1) * 80).toFixed(1)},${(30 - ((d - min) / rn * 30)).toFixed(1)}`).join(' '); const col = data[data.length - 1] >= data[0] ? 'var(--up)' : 'var(--down)'; return `<div style="display:flex;justify-content:center"><svg viewBox="0 0 80 3N" style="width:80px;height:30px;display:block"><polyline points="${p}" fill="none" stroke="${col}" stroke-width="1.5"/></svg></div>`; } },
    ind:   { label: '產業', type: 'str', sortable: true, key: 'ind', fmt: r => (r.ind || r.nm || '-') },
    rsi:   { label: 'RSI', type: 'num', sortable: true, fmt: r => r.rsi != null ? r.rsi : '-' },
    cap:   { label: '市值(億)', type: 'num', sortable: true, fmt: r => { const v = r.market_cap != null ? r.market_cap / 1e8 : (r.cap != null ? r.cap : null); return v != null ? Number(v).toFixed(2) : '-'; } },
    w1:    { label: '1週', type: 'pct', sortable: true, fmt: r => cellPct(r.w1) },
    m1:    { label: '1月', type: 'pct', sortable: true, fmt: r => cellPct(r.m1) },
    m3:    { label: '3月', type: 'pct', sortable: true, fmt: r => cellPct(r.m3) },
    m6:    { label: '6月', type: 'pct', sortable: true, fmt: r => cellPct(r.m6) },
    ytd:   { label: 'YTD', type: 'pct', sortable: true, fmt: r => cellPct(r.ytd) },
    y1:    { label: '1年', type: 'pct', sortable: true, fmt: r => cellPct(r.y1) },
    cnt:   { label: '檔數', type: 'num', sortable: true, fmt: r => r.cnt != null ? r.cnt : '-' },
    alert: { label: '提醒', type: 'html', sortable: false, fmt: r => r.alert ? `<span class="alert">${r.alert}</span>` : '—' },
    del:   { label: '移除', type: 'act', sortable: false, fmt: (r, ctx) => `<span class="del" onclick="${ctx.__cb}('${r.sym}')">✕</span>` },
  };

  function getVal(col, row, fieldMap) {
    const key = (fieldMap && fieldMap[col.id]) || col.key || col.id;
    return row[key];
  }

  function compare(a, b, col, fieldMap) {
    let va = getVal(col, a, fieldMap);
    let vb = getVal(col, b, fieldMap);
    if (col.type === 'str') return String(va || '').localeCompare(String(vb || ''));
    va = (va == null) ? -Infinity : Number(va);
    vb = (vb == null) ? -Infinity : Number(vb);
    return va - vb;
  }

  // 實例註冊表（供分頁、排序的全域回呼查找）
  const _instances = {};
  const _byTable = {};
  let _seq = 0;

  class MklabDatatable extends HTMLElement {
    static get observedAttributes() {
      return ['cols', 'page-size', 'default-sort', 'pager-id', 'data-src', 'field-map', 'rows-json'];
    }

    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this._table = null;
      this._cols = [];
      this._rows = [];
      this._fieldMap = {};
      this._pageSize = 0;
      this._page = 1;
      this._sortKey = null;
      this._sortDir = -1;
      this._pagerId = null;
      this._dataSrc = null;
      this._inst = null;
    }

    connectedCallback() {
      this._parseAttributes();
      this._inst = 'dt' + (_seq++);
      this.opts = { _inst: this._inst };
      _instances[this._inst] = this;
      _byTable[this.id || this._inst] = this;

      this._render();
      this._loadData();
    }

    disconnectedCallback() {
      delete _instances[this._inst];
      delete _byTable[this.id || this._inst];
    }

    static get observedAttributes() {
      return ['cols', 'page-size', 'default-sort', 'pager-id', 'data-src', 'field-map', 'rows-json'];
    }

    attributeChangedCallback(name, oldVal, newVal) {
      if (oldVal === newVal) return;
      this._parseAttributes();
      if (name === 'rows-json') this._loadData();
      else this.render();
    }

    _parseAttributes() {
      // cols: "sym,name,price,chg,score"
      this._cols = (this.getAttribute('cols') || 'sym,name,price,chg').split(',').map(s => s.trim()).filter(Boolean);
      // page-size
      this._pageSize = parseInt(this.getAttribute('page-size'), 10) || 0;
      // default-sort
      this._sortKey = this.getAttribute('default-sort') || (this._cols.find(c => COLUMNS[c]?.sortable) || {}).id || null;
      this._sortDir = -1;
      if (this._sortKey && COLUMNS[this._sortKey] && COLUMNS[this._sortKey].defDir) this._sortDir = COLUMNS[this._sortKey].defDir;
      // pager-id
      this._pagerId = this.getAttribute('pager-id') || null;
      // data-src (JSON URL 或 'stocks' / 'indices' 等內建鍵)
      this._dataSrc = this.getAttribute('data-src') || null;
      // field-map JSON
      try { this._fieldMap = JSON.parse(this.getAttribute('field-map') || '{}'); } catch (e) { this._fieldMap = {}; }
      // rows-json (inline JSON)
      this._rowsJson = this.getAttribute('rows-json') || null;
    }

    _render() {
      this.shadowRoot.innerHTML = `
        <style>
          :host { display: block; width: 100%; overflow-x: auto; }
          table { width: 100%; border-collapse: collapse; font-size: 0.95rem; }
          th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--border, #e5e7eb); white-space: nowrap; }
          th { background: var(--bg-header, var(--bg-elevated)); color: var(--ink); cursor: pointer; user-select: none; position: sticky; top: 0; z-index: 1; }
          th[data-k]:hover { background: var(--bg-hover); }
          td { color: var(--ink); }
          tr:hover td { background: var(--bg-hover); }
          .up { color: var(--up, #dc2626); }
          .down { color: var(--down, #16a34a); }
          .warn { color: var(--warn, #f59e0b); font-weight: bold; }
          .alert { color: var(--warn, #f59e0b); }
          .del { cursor: pointer; color: var(--muted); }
          .del:hover { color: var(--danger, #ef4444); }
          .spark { display: flex; justify-content: center; }
          .pager { display: flex; gap: 4px; justify-content: center; margin-top: 8px; flex-wrap: wrap; }
          .pager button { padding: 4px 8px; border: 1px solid var(--border); background: var(--bg); color: var(--ink); border-radius: 4px; cursor: pointer; }
          .pager button.on { background: var(--accent); color: #fff; border-color: var(--accent); }
          .empty { text-align: center; color: var(--muted); padding: 20px; }
        </style>
        <table>
          <thead><tr></tr></thead>
          <tbody></tbody>
        </table>
        ${this._pagerId ? `<div class="pager" id="${this._pagerId}"></div>` : ''}
      `;

      this._table = this.shadowRoot.querySelector('table');
      this._thead = this.shadowRoot.querySelector('thead tr');
      this._tbody = this.shadowRoot.querySelector('tbody');
      this._buildHeader();
    }

    _buildHeader() {
      this._thead.innerHTML = '';
      this._cols.forEach(id => {
        const def = COLUMNS[id];
        if (!def) { console.warn('[mklab-datatable] 未知欄位:', id); return; }
        const th = document.createElement('th');
        th.textContent = def.label;
        th.setAttribute('data-k', id);
        if (def.sortable) { th.style.cursor = 'pointer'; th.title = '點擊排序'; }
        this._thead.appendChild(th);
      });

      // 委託排序點擊
      this.shadowRoot.querySelector('thead').addEventListener('click', e => {
        const th = e.target.closest('th[data-k]');
        if (!th) return;
        this._toggleSort(th.getAttribute('data-k'));
      });
    }

    _toggleSort(key) {
      const def = COLUMNS[key];
      if (!def || !def.sortable) return;
      if (this._sortKey === key) this._sortDir *= -1;
      else { this._sortKey = key; this._sortDir = (def.defDir != null) ? def.defDir : -1; }
      this._page = 1;
      this.render();
    }

    async _loadData() {
      // 1) inline rows-json
      if (this._rowsJson) {
        try { this._rows = JSON.parse(this._rowsJson); this.render(); return; } catch (e) { console.warn('[mklab-datatable] rows-json parse error:', e); }
      }
      // 2) data-src
      if (this._dataSrc) {
        if (window.MKLAB && MKLAB.data) {
          try {
            if (this._dataSrc === 'stocks') { const d = await MKLAB.data.stocks(); this._rows = d || []; }
            else if (this._dataSrc === 'indices') { const d = await MKLAB.data.indices(); this._rows = d?.indices || []; }
            else if (this._dataSrc === 'twiiKline') { const d = await MKLAB.data.twiiKline(); this._rows = d || []; }
            else { const d = await MKLAB.data.json(this._dataSrc); this._rows = d || []; }
          } catch (e) { console.warn('[mklab-datatable] data-src fetch error:', e); this._rows = []; }
        }
        this.render();
        return;
      }
      // 3) 預設：若有全域 window.TWII_KDATA 等可自行處理
      this.render();
    }

    setRows(rows) {
      this._rows = rows || [];
      this._page = 1;
      this.render();
    }

    _sorted() {
      if (!this._sortKey) return this._rows.slice();
      const def = COLUMNS[this._sortKey];
      if (!def) return this._rows.slice();
      let rows = this._rows.slice();
      // 過濾 ETF：cap10 表格排除 ETF
      // 優先 is_etf 欄位；否則用 name 關鍵字（涵蓋台股 ETF 命名慣例）
      if (this.id === 'cap10') {
        const ETF_RE = /ETF|基金|指數|正[0-9]|反[0-9]|槓桿|反向|期貨|配息|高息|優息|收益|台灣50|中型100|科技|電子|摩台|摩澤|寶滬深|上證|上証|S&P|MSCI|日經|歐洲|印度|陸股|龍耀|鑫收|動能|升級|優股息|兆豐|元大|富邦|國泰|中信|統一|聯博|第一金|凯基|凱基/;
        const looksETF = (r) => {
          if (r.is_etf) return true;
          const nm = String(r.name || r.nm || '');
          return ETF_RE.test(nm);
        };
        rows = rows.filter(r => !looksETF(r));
      }
      return rows.sort((a, b) => compare(a, b, def, this._fieldMap) * this._sortDir);
    }

    render() {
      // 表頭箭頭
      this.shadowRoot.querySelectorAll('thead th').forEach(th => {
        const k = th.getAttribute('data-k');
        let txt = th.textContent.replace(/\s*[▲▼]$/, '');
        if (k === this._sortKey) txt += (this._sortDir === -1 ? ' ▼' : ' ▲');
        th.textContent = txt;
      });

      // 分頁
      let view = this._sorted();
      let totalPages = 1;
      if (this._pageSize > 0) {
        totalPages = Math.max(1, Math.ceil(view.length / this._pageSize));
        if (this._page > totalPages) this._page = totalPages;
        view = view.slice((this._page - 1) * this._pageSize, this._page * this._pageSize);
      }

      // 內容
      const rowsHtml = view.map(r => {
        const tds = this._cols.map(id => {
          const def = COLUMNS[id];
          if (!def) return '<td>?</td>';
          const rawVal = getVal({ id, ...def }, r, this._fieldMap);
          const v = (typeof def.fmt === 'function') ? def.fmt(r, { __cb: '__dt_del_' + this.id }) : (rawVal != null ? rawVal : '-');
          let cls = (def.type === 'pct') ? ((rawVal >= 0) ? 'up' : 'down') : '';
          if (def.type === 'pct' && typeof rawVal === 'number' && Math.abs(rawVal) > 10) cls = 'warn';
          return `<td class="${cls}">${v}</td>`;
        }).join('');
        return `<tr>${tds}</tr>`;
      }).join('') || `<tr><td colspan="${this._cols.length}" class="empty">無資料</td></tr>`;

      this.shadowRoot.querySelector('tbody').innerHTML = rowsHtml;

      // 分頁條
      const pagerEl = this.shadowRoot.getElementById(this._pagerId);
      if (pagerEl && this._pageSize > 0) {
        let html = '';
        for (let i = 1; i <= totalPages; i++) {
          html += `<button class="${i === this._page ? 'on' : ''}" onclick="__dt_goto('${this._inst}',${i})">${i}</button>`;
        }
        pagerEl.innerHTML = html;
      }
    }
  }

  /* ============ 全域註冊與匯出 ============ */
  if (!global.customElements.get('mklab-kline')) global.customElements.define('mklab-kline', MklabKline);
  if (!global.customElements.get('mklab-datatable')) global.customElements.define('mklab-datatable', MklabDatatable);

  // 分頁跳轉全域函式
  global.__dt_goto = function(inst, p) { const t = _instances[inst]; if (t) { t._page = p; t.render(); } };

  // 匯出供參考
  global.MKLAB_WC = global.MKLAB_WC || {};
  global.MKLAB_WC.MklabKline = MklabKline;
  global.MKLAB_WC.MklabDatatable = MklabDatatable;

})(window);