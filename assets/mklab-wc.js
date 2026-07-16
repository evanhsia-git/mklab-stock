/*
 * mklab-wc.js — 原生 Web Components 元件庫（零依賴、plain <script>）
 * 2026-07-15 選 2 路線：不引入 React/npm/Vite，用瀏覽器原生 Custom Elements。
 * 設計：classic script 註冊（非 ES module）→ 仍可在 file:// 直接開，守零依賴原則。
 * 與既有 mklab-core.js（MKLAB.* IIFE）並行不衝突：本檔只新增 <mklab-*> 標籤，不動舊邏輯。
 *
 * 提供的元件：
 *   <mklab-kline>      封裝 LightweightCharts 蠟燭圖（解 vanilla DOM 白屏風險）
 *   <mklab-datatable>  （預留，待 #5 實作）
 *
 * 用法：
 *   <mklab-kline data-symbol="TWII" height="420"></mklab-kline>
 *   JS: el.setData([{time,open,high,low,close}])  // 程式化餵資料
 *   JS: el.loadGlobal('TWII_KDATA')                // 讀 window.TWII_KDATA 全域
 */
(function (global) {
  'use strict';

  /* ============ <mklab-kline> ============ */
  class MklabKline extends HTMLElement {
    constructor() {
      super();
      this._chart = null;
      this._series = null;
      this._data = [];
    }

    connectedCallback() {
      // 圖表庫未載入（vendor/lightweight-charts.min.js 需在前面）則靜默退出
      if (typeof global.LightweightCharts === 'undefined') {
        console.warn('[mklab-kline] LightweightCharts 未載入，跳過渲染');
        return;
      }
      const h = parseInt(this.getAttribute('height'), 10) || 360;
      // 圖表 container 掛在元素內（不進 Shadow DOM：LightweightCharts 對 shadowRoot 支援有限）
      this._container = document.createElement('div');
      this._container.style.width = '100%';
      this._container.style.height = h + 'px';
      this.appendChild(this._container);

      try {
        this._chart = global.LightweightCharts.createChart(this._container, {
          layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#94a3b8' },
          grid: { vertLines: { color: 'rgba(148,163,184,0.1)' }, horzLines: { color: 'rgba(148,163,184,0.1)' } },
          rightPriceScale: { borderColor: 'rgba(148,163,184,0.2)' },
          timeScale: { borderColor: 'rgba(148,163,184,0.2)', timeVisible: false },
          width: this._container.clientWidth || this.clientWidth || 800,
          height: h,
        });
        this._series = this._chart.addCandlestickSeries({
          upColor: '#ef4444', downColor: '#22c55e',
          borderUpColor: '#ef4444', borderDownColor: '#22c55e',
          wickUpColor: '#ef4444', wickDownColor: '#22c55e',
        });
      } catch (e) {
        console.warn('[mklab-kline] createChart 失敗', e);
        return;
      }

      // 屬性驅動：data-symbol 讀全域；或 data-src 標記（由外部呼叫 setData）
      const sym = this.getAttribute('data-symbol');
      if (sym && global[sym + '_KDATA']) {
        this.setData(global[sym + '_KDATA']);
      } else if (this._data.length) {
        this.setData(this._data);
      }

      // resize 自適應
      this._onResize = () => {
        if (this._chart && this._container) {
          this._chart.resize(this._container.clientWidth || this.clientWidth || 800, h);
        }
      };
      global.addEventListener('resize', this._onResize);
    }

    disconnectedCallback() {
      if (this._onResize) global.removeEventListener('resize', this._onResize);
      if (this._chart) { try { this._chart.remove(); } catch (e) {} this._chart = null; }
    }

    /** 程式化餵資料：[{time,open,high,low,close}] */
    setData(arr) {
      this._data = Array.isArray(arr) ? arr : [];
      if (this._series && this._data.length) {
        try { this._series.setData(this._data); } catch (e) { console.warn('[mklab-kline] setData', e); }
      }
      return this;
    }

    /** 讀取全域變數（如 window.TWII_KDATA） */
    loadGlobal(name) {
      if (global[name]) this.setData(global[name]);
      return this;
    }

    /** 疊加指標（MACD/KD 由外部算好傳入） */
    addLine(opts) {
      if (!this._chart) return null;
      try {
        const s = this._chart.addLineSeries(opts);
        return s;
      } catch (e) { console.warn('[mklab-kline] addLine', e); return null; }
    }
  }
  if (!global.customElements.get('mklab-kline')) {
    global.customElements.define('mklab-kline', MklabKline);
  }

  /* ============ <mklab-datatable> ============ */
  class MklabDatatable extends HTMLElement {
    connectedCallback() {
          if (!global.MKLAB || !global.MKLAB.DataTable) {
            console.warn('[mklab-datatable] MKLAB.DataTable 未載入（需先載 mklab-core.js）');
            return;
          }
          const cols = (this.getAttribute('cols') || 'sym,name,price,chg').split(',').map(s => s.trim());
          const src = this.getAttribute('src') || 'stocks.json';
          const pageSize = parseInt(this.getAttribute('page-size'), 10) || 0;
          const id = 'tbl_' + Math.random().toString(36).slice(2);
          // DataTable 需要完整 table 結構：<table id="..."><thead></thead><tbody></tbody></table>
          const table = document.createElement('table');
          table.id = id;
          table.innerHTML = '<thead></thead><tbody></tbody>';
          this.appendChild(table);
          const render = (data) => {
            // stocks.json 結構為 {meta: {...}, stocks: [...]}
            const rows = (data && data.stocks) ? data.stocks : (Array.isArray(data) ? data : []);
            try { new global.MKLAB.DataTable(id, { cols, rows, pageSize }); }
            catch (e) { console.warn('[mklab-datatable] render', e); }
          };
          if (global.MKLAB_DATA) {
            global.MKLAB_DATA.json(src).then(render).catch(e => console.warn('[mklab-datatable]', e));
          } else {
            fetch('data/' + src).then(r => r.json()).then(render).catch(e => console.warn(e));
          }
        }
  }
  if (!global.customElements.get('mklab-datatable')) {
    global.customElements.define('mklab-datatable', MklabDatatable);
  }

  /* ============ <mklab-drawer> ============ */
  class MklabDrawer extends HTMLElement {
    connectedCallback() {
      if (!global.MKLAB || !global.MKLAB.Drawer) {
        console.warn('[mklab-drawer] MKLAB.Drawer 未載入（需先載 mklab-core.js）');
        return;
      }
      const trigger = this.getAttribute('trigger') || '.mklab-drawer-trigger';
      const position = this.getAttribute('position') || 'right';
      const title = this.getAttribute('title') || '設定';
      const themeKey = this.getAttribute('theme-key') || 'mklab-theme';
      const langKey = this.getAttribute('lang-key') || 'mklab-lang';

      // 內容區塊（支援 slots）
      const content = this.innerHTML || '<p>無內容</p>';
      this.innerHTML = '';
      this._drawer = new global.MKLAB.Drawer({
        trigger: document.querySelector(trigger),
        position: position,
        title: title,
        content: content,
        themeKey: themeKey,
        langKey: langKey,
      });
    }
    disconnectedCallback() {
      if (this._drawer && this._drawer.destroy) this._drawer.destroy();
    }
    // 程式化開關
    open() { if (this._drawer) this._drawer.open(); }
    close() { if (this._drawer) this._drawer.close(); }
    toggle() { if (this._drawer) this._drawer.toggle(); }
  }
  if (!global.customElements.get('mklab-drawer')) {
    global.customElements.define('mklab-drawer', MklabDrawer);
  }

  /* ============ <mklab-router> + <mklab-route> ============ */
  class MklabRouter extends HTMLElement {
    constructor() {
      super();
      this.routes = [];
      this._bound = this._onPop.bind(this);
      this._clickBound = this._onClick.bind(this);
    }
    connectedCallback() {
      window.addEventListener('popstate', this._bound);
      document.body.addEventListener('click', this._clickBound);
      this._collectRoutes();
      this._nav(location.pathname);
    }
    disconnectedCallback() {
      window.removeEventListener('popstate', this._bound);
      document.body.removeEventListener('click', this._clickBound);
    }
    _collectRoutes() {
      this.routes = Array.from(this.querySelectorAll('mklab-route')).map(r => ({
        path: r.getAttribute('path') || '/',
        component: r.getAttribute('component'),
        show: r.getAttribute('show') || 'block',
      }));
    }
    _onClick(e) {
      const a = e.target.closest('a[href^="/"]');
      if (a && a.target !== '_blank' && !a.hasAttribute('data-no-router')) {
        e.preventDefault();
        const href = a.getAttribute('href');
        history.pushState({}, '', href);
        this._nav(href);
      }
    }
    _onPop() { this._nav(location.pathname); }
    _nav(path) {
      const route = this.routes.find(r => path === r.path || (r.path !== '/' && path.startsWith(r.path)));
      this.routes.forEach(r => {
        const el = r.component ? document.querySelector(r.component) : null;
        if (el) el.style.display = (route && route.path === r.path) ? r.show : 'none';
      });
      this.dispatchEvent(new CustomEvent('mklab:navigate', { detail: { path, route } }));
    }
    go(path) { history.pushState({}, '', path); this._nav(path); }
  }
  class MklabRoute extends HTMLElement { /* 只供 router 讀取屬性 */ }
  if (!global.customElements.get('mklab-router')) global.customElements.define('mklab-router', MklabRouter);
  if (!global.customElements.get('mklab-route')) global.customElements.define('mklab-route', MklabRoute);

  /* ============ 匯出（選用，供其他 script 參考） ============ */
  global.MKLAB_WC = { MklabKline, MklabDatatable, MklabDrawer, MklabRouter, MklabRoute };

})(window);
