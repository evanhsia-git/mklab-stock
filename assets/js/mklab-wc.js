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


  /* ============ 全域註冊與匯出 ============ */
  if (!global.customElements.get('mklab-kline')) global.customElements.define('mklab-kline', MklabKline);

  // 匯出供參考
  global.MKLAB_WC = global.MKLAB_WC || {};
  global.MKLAB_WC.MklabKline = MklabKline;

})(window);
