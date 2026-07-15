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

  /* ============ 匯出（選用，供其他 script 參考） ============ */
  global.MKLAB_WC = { MklabKline };

})(window);
