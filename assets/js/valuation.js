/*
 * valuation.js — 估值指標與 DCF 計算（純函式，無 DOM 依賴，可用 node 測試）
 *
 * ── 估值指標（相對估值）──────────────────────────────────────────
 * 為避免極端值被放大，所有輸入先經過合理範圍（BOUNDS）：
 *   PE 5–60、PB 0.3–10、殖利率 0.5–15%。PE 低於 5 多半來自一次性獲利，PB 低於 0.3 多半是資產減損或資料異常；超出範圍者不計入中位數，也不計入該股的合理價。
 * EPS 與每股淨值一律由「股價 ÷ 報告 PE」「股價 ÷ 報告 PB」推算，與股價同一時點、同一單位，
 * 避免 EPS 欄位單位或期間不一致造成放大。
 *   PE 合理價   = (股價 ÷ PE) × 同產業中位數 PE
 *   PB 合理價   = (股價 ÷ PB) × 同產業中位數 PB
 *   Graham      = √(22.5 × (股價 ÷ PE) × (股價 ÷ PB))
 *   殖利率合理價 = 股價 × (殖利率 ÷ 目標殖利率)
 * 綜合參考價 = 上列方法中，落在股價 0.2–5 倍之間者的中位數；可用方法少於 2 個則為空（不顯示）。
 *
 * ── DCF（5 年明確預測 + 永續成長終值，年末折現）────────────────────
 *   FCF_t = FCF_0 × (1+g)^t，t = 1…5
 *   TV    = FCF_5 × (1+gT) ÷ (WACC − gT)
 *   EV    = Σ FCF_t ÷ (1+WACC)^t + TV ÷ (1+WACC)^5
 *   每股價值 = (EV − 淨負債) ÷ 股數
 *
 * 單位：金額以「百萬」計，股數以「百萬股」計，百分比以「%」數字傳入（WACC 9 = 9%）。
 */
(function (g) {
  'use strict';

  const GRAHAM_K = 22.5;
  const DCF_YEARS = 5;
  const BOUNDS = { pe: [5, 60], pb: [0.3, 10], yieldPct: [0.5, 15] };
  const CANDIDATE_RATIO = [0.2, 5];      // 合理價相對股價的可接受倍數
  const MIN_GROUP_N = 5;                 // 產業中位數最少樣本數
  const MIN_METHODS = 2;                 // 綜合參考價最少方法數

  function isNum(v) { return typeof v === 'number' && isFinite(v); }
  function inRange(v, r) { return isNum(v) && v >= r[0] && v <= r[1]; }

  function median(values) {
    const a = values.filter(isNum).slice().sort((x, y) => x - y);
    if (!a.length) return null;
    const m = Math.floor(a.length / 2);
    return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
  }

  function bookValuePerShare(price, pb) {
    if (!isNum(price) || !isNum(pb) || price <= 0 || pb <= 0) return null;
    return price / pb;
  }

  // 每股盈餘：由股價與報告 PE 推算（需 PE 落在合理範圍）
  function earningsPerShare(price, pe) {
    if (!isNum(price) || price <= 0 || !inRange(pe, BOUNDS.pe)) return null;
    return price / pe;
  }

  function grahamNumber(eps, price, pb) {
    const bvps = bookValuePerShare(price, pb);
    if (!isNum(eps) || eps <= 0 || bvps === null) return null;
    return Math.sqrt(GRAHAM_K * eps * bvps);
  }

  // 同產業中位數（只計入 range 內的值）；產業樣本少於 minN 時該產業為 null，改用全體中位數
  function industryMedian(rows, groupKey, valueKey, range, minN) {
    const groups = {};
    const all = [];
    rows.forEach(r => {
      const v = r[valueKey];
      if (!inRange(v, range)) return;
      all.push(v);
      const k = r[groupKey];
      if (!k) return;
      (groups[k] = groups[k] || []).push(v);
    });
    const overall = median(all);
    const byGroup = {};
    Object.keys(groups).forEach(k => {
      byGroup[k] = groups[k].length >= (minN || MIN_GROUP_N) ? median(groups[k]) : null;
    });
    return { byGroup, overall };
  }

  function referenceValue(price, candidates) {
    const ok = candidates.filter(v => isNum(v) && price > 0 &&
      v >= price * CANDIDATE_RATIO[0] && v <= price * CANDIDATE_RATIO[1]);
    if (ok.length < MIN_METHODS) return null;
    return median(ok);
  }

  function upsidePct(refValue, price) {
    if (!isNum(refValue) || !isNum(price) || price <= 0) return null;
    return (refValue / price - 1) * 100;
  }

  // 單一標的完整估值指標
  // row: { price, pe, pb, divPct, group }；medians: { pe, pb }（industryMedian 結果）
  function valuationRow(row, medians, opts) {
    const o = Object.assign({ targetYieldPct: 5 }, opts || {});
    const price = row.price;
    const grp = row.group;
    const pick = (m) => (grp && m.byGroup[grp] != null) ? m.byGroup[grp] : m.overall;
    const medPE = pick(medians.pe);
    const medPB = pick(medians.pb);

    const eps = earningsPerShare(price, row.pe);
    const bvps = inRange(row.pb, BOUNDS.pb) ? bookValuePerShare(price, row.pb) : null;
    const yieldOk = inRange(row.divPct, BOUNDS.yieldPct) && isNum(o.targetYieldPct) && o.targetYieldPct > 0;

    const parts = {
      graham: (eps !== null && bvps !== null) ? Math.sqrt(GRAHAM_K * eps * bvps) : null,
      pe: (eps !== null && isNum(medPE)) ? eps * medPE : null,
      pb: (bvps !== null && isNum(medPB)) ? bvps * medPB : null,
      yield: yieldOk ? price * (row.divPct / o.targetYieldPct) : null,
    };
    const ref = referenceValue(price, [parts.graham, parts.pe, parts.pb, parts.yield]);
    return Object.assign({}, parts, {
      medPE, medPB, ref, upside: upsidePct(ref, price),
      methods: [parts.graham, parts.pe, parts.pb, parts.yield].filter(v => v !== null).length,
    });
  }

  // ---------- DCF ----------
  // p: { fcf0, g, gT, wacc, shares, netDebt }  金額百萬、股數百萬、百分比為 %
  function dcf(p) {
    const out = { ok: false, reason: '', warnings: [], perShare: null, ev: null, pvFcf: null, pvTv: null, tvShare: null, fcfs: [] };
    for (const k of ['fcf0', 'g', 'gT', 'wacc', 'shares']) {
      if (!isNum(p[k])) { out.reason = `缺少參數：${k}`; return out; }
    }
    const netDebt = isNum(p.netDebt) ? p.netDebt : 0;
    if (p.shares <= 0) { out.reason = '股數必須大於 0'; return out; }
    if (p.wacc <= p.gT) { out.reason = '折現率必須大於永續成長率'; return out; }
    if (p.fcf0 <= 0) { out.reason = '基期自由現金流為負或 0，DCF 不適用（建議改用其他方法）'; return out; }

    const r = p.wacc / 100;
    let fcf = p.fcf0, pvSum = 0;
    for (let t = 1; t <= DCF_YEARS; t++) {
      fcf = fcf * (1 + p.g / 100);
      const pv = fcf / Math.pow(1 + r, t);
      out.fcfs.push({ year: t, fcf, pv });
      pvSum += pv;
    }
    const tv = fcf * (1 + p.gT / 100) / (r - p.gT / 100);
    const pvTv = tv / Math.pow(1 + r, DCF_YEARS);
    const ev = pvSum + pvTv;

    out.ok = true;
    out.pvFcf = pvSum;
    out.pvTv = pvTv;
    out.ev = ev;
    out.tvShare = ev > 0 ? pvTv / ev * 100 : null;
    out.perShare = (ev - netDebt) / p.shares;
    out.warnings = inputWarnings(p, out);
    return out;
  }

  // 輸入合理性提醒（不阻擋計算，但會顯示給使用者）
  function inputWarnings(p, res) {
    const w = [];
    if (p.gT > 3.5) w.push('永續成長率超過 3.5%，通常高於長期名目 GDP 成長，終值會被大幅放大。');
    if (p.wacc > 15) w.push('折現率超過 15%，偏高；結果會明顯偏低，請確認是否為刻意的風險溢酬。');
    if (p.wacc < 6) w.push('折現率低於 6%，偏低；結果會明顯偏高。');
    if (p.g > 25) w.push('前 5 年成長率超過 25%，長期持續的機率很低。');
    if (res && res.tvShare != null && res.tvShare > 75) w.push('終值佔企業價值超過 75%，結果高度依賴永續成長率與折現率。');
    return w;
  }

  // 敏感度表：列 = WACC、欄 = 永續成長率，其餘參數沿用 base
  function sensitivity(base, waccs, gTs) {
    return waccs.map(w => gTs.map(gt => {
      const r = dcf(Object.assign({}, base, { wacc: w, gT: gt }));
      return r.ok ? r.perShare : null;
    }));
  }

  // ---------- 現金流資料整理（純函式，供日後資料來源使用） ----------
  function toMillions(value, unit) {
    if (!isNum(value)) return null;
    if (unit === 'thousand') return value / 1000;
    if (unit === 'unit') return value / 1e6;
    if (unit === 'million') return value;
    return null;
  }
  function ttmSum(quarters) {
    if (!Array.isArray(quarters) || quarters.length !== 4) return null;
    if (!quarters.every(isNum)) return null;
    return quarters.reduce((a, b) => a + b, 0);
  }
  function fcfFromCashFlow(ocf, capex) {
    if (!isNum(ocf) || !isNum(capex)) return null;
    return ocf - Math.abs(capex);
  }

  const api = {
    BOUNDS, DCF_YEARS, GRAHAM_K, CANDIDATE_RATIO,
    median, bookValuePerShare, earningsPerShare, grahamNumber, industryMedian,
    referenceValue, upsidePct, valuationRow, dcf, inputWarnings, sensitivity,
    toMillions, ttmSum, fcfFromCashFlow,
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else g.MKLAB_VAL = api;
})(typeof window !== 'undefined' ? window : globalThis);
