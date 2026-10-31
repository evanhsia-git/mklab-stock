/*
 * mklab-chart.js — K 線圖元件（Apache ECharts，Candlestick Brush 框選範例的做法）
 * 功能：K 線、MA5/MA20/MA60、KD(9,3,3)、MACD(12,26,9) 副圖切換、框選區間統計、縮放拖曳。
 * 依賴：vendor/echarts.min.js（ECharts 5.5.1，Apache-2.0）。
 * 資料格式：[{time:'YYYY-MM-DD', open, high, low, close}, ...]（與 twii_kdata.js 相同）。
 */
(function (global) {
  'use strict';

  function ema(values, n) {
    const k = 2 / (n + 1), out = [values[0]];
    for (let i = 1; i < values.length; i++) out.push(values[i] * k + out[i - 1] * (1 - k));
    return out;
  }
  function sma(values, n) {
    const out = [];
    for (let i = 0; i < values.length; i++) {
      if (i + 1 < n) { out.push(null); continue; }
      let s = 0; for (let j = i - n + 1; j <= i; j++) s += values[j];
      out.push(+(s / n).toFixed(2));
    }
    return out;
  }
  function calcKD(d) {
    const K = [], D = []; let pk = 50, pd = 50;
    for (let i = 0; i < d.length; i++) {
      const lo = Math.min(...d.slice(Math.max(0, i - 8), i + 1).map(x => x.low));
      const hi = Math.max(...d.slice(Math.max(0, i - 8), i + 1).map(x => x.high));
      const rsv = hi === lo ? 50 : (d[i].close - lo) / (hi - lo) * 100;
      pk = pk * 2 / 3 + rsv / 3; pd = pd * 2 / 3 + pk / 3;
      K.push(+pk.toFixed(2)); D.push(+pd.toFixed(2));
    }
    return { K, D };
  }
  function calcMACD(d) {
    const c = d.map(x => x.close);
    const e12 = ema(c, 12), e26 = ema(c, 26);
    const dif = e12.map((v, i) => v - e26[i]);
    const dea = ema(dif, 9);
    const hist = dif.map((v, i) => +((v - dea[i]) * 1).toFixed(2));
    return { DIF: dif.map(v => +v.toFixed(2)), DEA: dea.map(v => +v.toFixed(2)), HIST: hist };
  }

  // 建立圖表。回傳 { setIndicator(name,on), dispose(), chart }
  function createKline(el, data, opts) {
    opts = opts || {};
    const chart = echarts.init(el, null, { renderer: 'canvas' });
    const dates = data.map(d => d.time);
    const ohlc = data.map(d => [d.open, d.close, d.low, d.high]); // ECharts candlestick: [open, close, low, high]
    const closes = data.map(d => d.close);
    const ma = { MA5: sma(closes, 5), MA20: sma(closes, 20), MA60: sma(closes, 60) };
    const kd = calcKD(data), macd = calcMACD(data);
    const state = { KD: !!(opts.indicators && opts.indicators.KD), MACD: !!(opts.indicators && opts.indicators.MACD) };

    function build() {
      const panels = [];
      if (state.KD) panels.push('KD');
      if (state.MACD) panels.push('MACD');
      const n = 1 + panels.length;
      const narrow = el.clientWidth && el.clientWidth < 520;
      const legendTop = narrow ? 30 : 0;
      // 版面高度（百分比）：上方留給圖例與工具列，下方留給縮放滑桿與時間軸
      const topStart = narrow ? 20 : 8;
      const avail = narrow ? 70 : 80;
      const sub = panels.length;
      const priceH = sub === 0 ? avail : (sub === 1 ? avail * 0.6 : avail * 0.46);
      const gap = 4;
      const subH = sub === 0 ? 0 : (avail - priceH - gap * sub) / sub;
      const grids = [], xAxes = [], yAxes = [], series = [];
      const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
      const txt = isDark ? '#9aa0a6' : '#6b7280';
      const split = isDark ? '#2a2f3a' : '#e5e7eb';
      let top = topStart;
      grids.push({ left: narrow ? 44 : 60, right: narrow ? 10 : 24, top: top + '%', height: priceH + '%' });
      top += priceH + gap;
      panels.forEach(() => { grids.push({ left: narrow ? 44 : 60, right: narrow ? 10 : 24, top: top + '%', height: subH + '%' }); top += subH + gap; });
      grids.forEach((g, gi) => {
        xAxes.push({ type: 'category', data: dates, gridIndex: gi, boundaryGap: true, axisLine: { lineStyle: { color: split } },
          axisLabel: { show: gi === n - 1, color: txt }, axisTick: { show: false }, splitLine: { show: false },
          axisPointer: { z: 100 }, min: 'dataMin', max: 'dataMax' });
        yAxes.push({ scale: true, gridIndex: gi, splitNumber: 3, axisLine: { show: false }, axisTick: { show: false },
          axisLabel: { color: txt }, splitLine: { lineStyle: { color: split } } });
      });
      series.push({ name: '大盤', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0, data: ohlc,
        itemStyle: { color: '#f87171', color0: '#4ade80', borderColor: '#f87171', borderColor0: '#4ade80' } });
      [['MA5', '#fbbf24'], ['MA20', '#60a5fa'], ['MA60', '#c084fc']].forEach(([k, col]) => {
        series.push({ name: k, type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: ma[k], showSymbol: false, smooth: false, lineStyle: { width: 1, color: col }, itemStyle: { color: col } });
      });
      panels.forEach((p, i) => {
        const gi = i + 1;
        if (p === 'KD') {
          series.push({ name: 'K', type: 'line', xAxisIndex: gi, yAxisIndex: gi, data: kd.K, showSymbol: false, lineStyle: { width: 1, color: '#a855f7' }, itemStyle: { color: '#a855f7' } });
          series.push({ name: 'D', type: 'line', xAxisIndex: gi, yAxisIndex: gi, data: kd.D, showSymbol: false, lineStyle: { width: 1, color: '#14b8a6' }, itemStyle: { color: '#14b8a6' } });
          yAxes[gi].min = 0; yAxes[gi].max = 100;
        } else {
          series.push({ name: 'DIF', type: 'line', xAxisIndex: gi, yAxisIndex: gi, data: macd.DIF, showSymbol: false, lineStyle: { width: 1, color: '#3b82f6' }, itemStyle: { color: '#3b82f6' } });
          series.push({ name: 'DEA', type: 'line', xAxisIndex: gi, yAxisIndex: gi, data: macd.DEA, showSymbol: false, lineStyle: { width: 1, color: '#f59e0b' }, itemStyle: { color: '#f59e0b' } });
          series.push({ name: 'MACD柱', type: 'bar', xAxisIndex: gi, yAxisIndex: gi, data: macd.HIST.map(v => ({ value: v, itemStyle: { color: v >= 0 ? '#ef4444' : '#22c55e' } })) });
        }
      });
      const all = Array.from({ length: n }, (_, i) => i);
      return {
        animation: false,
        tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
        axisPointer: { link: [{ xAxisIndex: 'all' }] },
        toolbox: { right: 4, top: 0, itemSize: narrow ? 14 : 16, itemGap: narrow ? 6 : 10, feature: { brush: { type: ['lineX', 'clear'] }, restore: {} } },
        brush: { xAxisIndex: all, brushLink: 'all', outOfBrush: { colorAlpha: 0.35 } },
        legend: { top: legendTop, left: narrow ? 4 : 60, right: narrow ? 4 : undefined, itemWidth: narrow ? 14 : 25, itemHeight: narrow ? 8 : 14, itemGap: narrow ? 8 : 10, textStyle: { color: txt, fontSize: narrow ? 11 : 12 }, data: ['大盤', 'MA5', 'MA20', 'MA60'].concat(panels.includes('KD') ? ['K', 'D'] : []).concat(panels.includes('MACD') ? ['DIF', 'DEA'] : []) },
        grid: grids, xAxis: xAxes, yAxis: yAxes,
        dataZoom: [
          { type: 'inside', xAxisIndex: all, start: 60, end: 100 },
          { type: 'slider', xAxisIndex: all, bottom: 4, height: 18, start: 60, end: 100, textStyle: { color: txt } },
        ],
        series: series,
      };
    }

    function render() { chart.setOption(build(), true); }

    // 框選區間統計（對應 Candlestick Brush 的 brushSelected 事件）
    chart.on('brushSelected', function (p) {
      const b = p.batch && p.batch[0];
      const idx = b && b.selected && b.selected[0] ? b.selected[0].dataIndex : [];
      if (!idx || !idx.length || !opts.onBrush) { if (opts.onBrush) opts.onBrush(null); return; }
      const rows = idx.map(i => data[i]);
      const first = rows[0].close, last = rows[rows.length - 1].close;
      opts.onBrush({
        from: rows[0].time, to: rows[rows.length - 1].time, days: rows.length,
        change: +((last / first - 1) * 100).toFixed(2),
        high: Math.max(...rows.map(r => r.high)), low: Math.min(...rows.map(r => r.low)),
      });
    });

    render();
    window.addEventListener('resize', () => chart.resize());
    return {
      chart: chart,
      setIndicator: function (name, on) { state[name] = !!on; render(); },
      clearIndicators: function () { state.KD = false; state.MACD = false; render(); },
      dispose: function () { chart.dispose(); },
    };
  }

  global.MKLAB = global.MKLAB || {};
  global.MKLAB.chart = { createKline: createKline, calcKD: calcKD, calcMACD: calcMACD };
})(window);
