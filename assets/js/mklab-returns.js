/*
 * mklab-returns.js — 多股區間報酬率比較（共用：compare / research 兩頁）
 * 資料來源：data/kline/{代號}.json（逐日收盤，rows = [日期, 開, 高, 低, 收]）
 * 計算方式：基準 = 區間起算日「前一個」交易日收盤（基準 = 0%），之後每日顯示相對基準的累積漲跌%。
 *   5日   ：以最近 5 個交易日為區間（基準為第 6 日前的收盤）
 *   1個月 / 3個月 / 6個月 / 1年：基準 = 目標日期（回推月數或年數）當日或之前最後一個交易日
 *   YTD   ：基準 = 上一年度 12/31 當日或之前最後一個交易日
 * 若個股歷史不足以涵蓋基準日，該檔標示「資料不足」，不畫線、不估算。
 * 用法：
 *   const st = MKLAB.returns.mount({ controls: el, chart: el2, summary: el3, getItems: () => [{sym, name}] });
 *   st.refresh();   // 清單變動後呼叫
 */
(function (global) {
  'use strict';
  const MK = global.MKLAB = global.MKLAB || {};

  const PERIODS = [
    { key: '5d',  label: '5日' },
    { key: '1m',  label: '1個月' },
    { key: '3m',  label: '3個月' },
    { key: '6m',  label: '6個月' },
    { key: 'ytd', label: 'YTD' },
    { key: '1y',  label: '1年' },
  ];
  const PERIOD_KEY = 'mklab-returns-period';
  const COLORS = ['#3b82f6', '#f59e0b', '#10b981', '#ef4444', '#a855f7', '#14b8a6'];
  const _klCache = {};

  function loadKline(sym) {
    if (sym in _klCache) return Promise.resolve(_klCache[sym]);
    // 兩個效率要點（與 assets/js/data-client.js 同一個坑）：
    //   ① 進行中的請求要立刻放進 _klCache，否則「下載完成前」對同一代號的第二次呼叫
    //      會再抓一次（原本 _klCache 只在 .then 內才寫）。
    //   ② cache 用 'no-cache'：每次跟伺服器驗證、沒變就回 304 少傳。
    //      不可用 'no-store'（等於關掉瀏覽器快取，每次換頁都重下）。
    const p = fetch('data/kline/' + encodeURIComponent(sym) + '.json', { cache: 'no-cache' })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (doc) {
        const rows = (doc.rows || [])
          .filter(function (x) { return x && x[0] && x[4] != null && isFinite(Number(x[4])); })
          .map(function (x) { return { d: String(x[0]), c: Number(x[4]) }; });
        _klCache[sym] = { rows: rows, asof: doc.asof || '' };
        return _klCache[sym];
      })
      .catch(function () { _klCache[sym] = null; return null; });
    if (!(sym in _klCache)) _klCache[sym] = p;  // 進行中先佔位（解析後會被上面的結果覆蓋）
    return p;
  }

  // 日期字串 YYYY-MM-DD 往前推 months 個月 / years 年（UTC 計算，避免時區飄移）
  function shiftDate(s, months, years) {
    const p = s.split('-').map(Number);
    const dt = new Date(Date.UTC(p[0], p[1] - 1, p[2]));
    dt.setUTCMonth(dt.getUTCMonth() - months - years * 12);
    return dt.toISOString().slice(0, 10);
  }

  // 回傳基準交易日的索引；-1 表示資料不足（沒有任何交易日早於或等於目標日）
  function baseIndex(rows, period) {
    const n = rows.length;
    if (period === '5d') return n >= 6 ? n - 6 : -1;
    const last = rows[n - 1].d;
    let target;
    if (period === 'ytd') target = (Number(last.slice(0, 4)) - 1) + '-12-31';
    else if (period === '1m') target = shiftDate(last, 1, 0);
    else if (period === '3m') target = shiftDate(last, 3, 0);
    else if (period === '6m') target = shiftDate(last, 6, 0);
    else target = shiftDate(last, 0, 1);
    let idx = -1;
    for (let i = 0; i < n; i++) { if (rows[i].d <= target) idx = i; else break; }
    return idx;
  }

  function computeSeries(rows, period) {
    const n = rows.length;
    if (n < 2) return null;
    const bi = baseIndex(rows, period);
    if (bi < 0 || bi >= n - 1) return null;
    const base = rows[bi].c;
    if (!base) return null;
    const pts = [];
    for (let i = bi; i < n; i++) pts.push([rows[i].d, +((rows[i].c / base - 1) * 100).toFixed(2)]);
    return {
      baseDate: rows[bi].d,
      endDate: rows[n - 1].d,
      baseClose: base,
      endClose: rows[n - 1].c,
      pts: pts,
      final: pts[pts.length - 1][1],
    };
  }

  function getPeriod() {
    try { const p = localStorage.getItem(PERIOD_KEY); if (PERIODS.some(x => x.key === p)) return p; } catch (e) {}
    return '3m';
  }
  function setPeriod(p) { try { localStorage.setItem(PERIOD_KEY, p); } catch (e) {} }

  function cssVar(name, fallback) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }

  function pctText(v) { return (v > 0 ? '+' : '') + Number(v).toFixed(2) + '%'; }

  function mount(opts) {
    const st = { opts: opts, period: getPeriod(), inst: null, token: 0 };
    opts.controls.innerHTML = PERIODS.map(function (p) {
      return '<button type="button" class="btn btn-secondary btn-sm" data-rp="' + p.key + '">' + p.label + '</button>';
    }).join('');
    opts.controls.addEventListener('click', function (e) {
      const b = e.target.closest && e.target.closest('[data-rp]');
      if (!b) return;
      st.period = b.dataset.rp;
      setPeriod(st.period);
      refresh(st);
    });
    global.addEventListener('resize', function () { if (st.inst) st.inst.resize(); });
    st.refresh = function () { return refresh(st); };
    return st;
  }

  async function refresh(st) {
    const o = st.opts;
    const token = ++st.token;
    o.controls.querySelectorAll('[data-rp]').forEach(function (b) {
      const on = b.dataset.rp === st.period;
      b.classList.toggle('btn-secondary', !on);
      b.classList.toggle('btn-primary', on);
    });
    const items = (o.getItems() || []).slice(0, 6);
    if (st.inst) { st.inst.dispose(); st.inst = null; }
    o.chart.innerHTML = '';
    if (!items.length) {
      o.chart.innerHTML = '<p class="text-muted text-center" style="padding-top:40px;">請先加入股票（最多 6 檔）</p>';
      o.summary.innerHTML = '';
      return;
    }
    o.summary.innerHTML = '<p class="muted-small-top">計算中…</p>';
    const loaded = await Promise.all(items.map(function (it) {
      return loadKline(it.sym).then(function (k) { return { it: it, k: k }; });
    }));
    if (token !== st.token) return; // 有較新的請求，丟棄這次結果
    const results = loaded.map(function (x, idx) {
      const s = x.k ? computeSeries(x.k.rows, st.period) : null;
      return { sym: x.it.sym, name: x.it.name || '', color: COLORS[idx % COLORS.length], s: s };
    });
    drawChart(st, results);
    drawSummary(st, results);
  }

  function drawChart(st, results) {
    const el = st.opts.chart;
    const ok = results.filter(function (r) { return r.s; });
    if (!ok.length || typeof global.echarts === 'undefined') {
      el.innerHTML = '<p class="text-muted text-center" style="padding-top:40px;">' +
        (typeof global.echarts === 'undefined' ? '圖表元件未載入（vendor/echarts.min.js）' : '所選股票在此區間的資料不足，無法繪製') + '</p>';
      return;
    }
    const ink = cssVar('--ink', '#e8eaed');
    const grid = cssVar('--border', '#2a2f3a');
    const series = ok.map(function (r, i) {
      const last = r.s.pts[r.s.pts.length - 1];
      return {
        name: r.sym + (r.name ? ' ' + r.name : ''),
        type: 'line', showSymbol: false, smooth: false,
        lineStyle: { width: 2, color: r.color }, itemStyle: { color: r.color },
        data: r.s.pts,
        markPoint: {
          symbol: 'circle', symbolSize: 7,
          itemStyle: { color: r.color },
          data: [{ coord: last, value: last[1] }],
          label: { color: r.color, fontWeight: 700, position: 'right', formatter: function (p) { return pctText(p.value); } },
        },
      };
    });
    if (series.length) {
      series[0].markLine = { symbol: 'none', silent: true, lineStyle: { color: ink, opacity: 0.4 }, label: { show: false }, data: [{ yAxis: 0 }] };
    }
    el.innerHTML = '';
    const inst = global.echarts.init(el);
    inst.setOption({
      color: COLORS, animation: false,
      tooltip: { trigger: 'axis', valueFormatter: function (v) { return v == null ? '-' : pctText(v); } },
      legend: { top: 0, textStyle: { color: ink } },
      grid: { left: 58, right: 96, top: 44, bottom: 30 },
      xAxis: { type: 'time', axisLabel: { color: ink }, axisLine: { lineStyle: { color: grid } } },
      yAxis: { type: 'value', scale: true, axisLabel: { color: ink, formatter: '{value}%' }, splitLine: { lineStyle: { color: grid, type: 'dashed' } } },
      series: series,
    });
    st.inst = inst;
  }

  function drawSummary(st, results) {
    const rows = results.map(function (r) {
      if (!r.s) {
        return '<tr><td>' + r.sym + '</td><td>' + r.name + '</td><td colspan="3" class="text-muted">資料不足（此區間無法取得基準日收盤）</td></tr>';
      }
      const cls = r.s.final >= 0 ? 'up' : 'down';
      return '<tr><td>' + r.sym + '</td><td>' + r.name + '</td><td>' + r.s.baseDate + '</td>' +
        '<td class="' + cls + '"><b>' + pctText(r.s.final) + '</b></td>' +
        '<td>' + r.s.baseClose + ' → ' + r.s.endClose + '（' + r.s.endDate + '）</td></tr>';
    }).join('');
    st.opts.summary.innerHTML =
      '<div class="table-wrap"><table><thead><tr><th>代號</th><th>名稱</th><th>基準日</th><th>區間漲跌</th><th>收盤（基準 → 期末）</th></tr></thead><tbody>' +
      rows + '</tbody></table></div>' +
      '<p class="muted-small-top">區間漲跌以基準日收盤為 0% 計算，僅代表歷史表現，不代表未來報酬。收盤價來自 data/kline，資料為收盤後更新。</p>';
  }

  MK.returns = { PERIODS: PERIODS, loadKline: loadKline, computeSeries: computeSeries, baseIndex: baseIndex, mount: mount };
})(window);
