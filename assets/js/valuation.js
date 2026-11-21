/*
 * valuation.js — 估值指標與 DCF 計算（純函式，無 DOM 依賴，可用 node 測試）
 *
 * 估值指標（現有欄位即可計算）：
 *   Graham Number  = √(22.5 × EPS × 每股淨值)        每股淨值 = 股價 ÷ PB
 *   PE 合理價      = EPS × 同產業中位數 PE
 *   PB 合理價      = 每股淨值 × 同產業中位數 PB
 *   殖利率合理價   = 每股現金股利 ÷ 目標殖利率
 *   綜合參考價     = 上述各法（有值者）的中位數
 *
 * DCF（兩階段成長 + 永續成長終值，年末折現）：
 *   FCF_t = FCF_0 × ∏ (1+g)   前 5 年用 g1，第 6–10 年用 g2
 *   TV    = FCF_10 × (1+gT) ÷ (WACC − gT)
 *   EV    = Σ FCF_t ÷ (1+WACC)^t + TV ÷ (1+WACC)^10
 *   每股價值 = (EV − 淨負債) ÷ 股數
 *
 * 單位約定：金額以「百萬」計（台股為 NT$ 百萬，美股為 USD 百萬），股數以「百萬股」計。
 * 所有百分比以「%」數字傳入（例如 WACC 9 代表 9%）。
 */
(function (g) {
  'use strict';

  const GRAHAM_K = 22.5;
  const DCF_YEARS = 10;
  const STAGE1_YEARS = 5;

  function isNum(v) { return typeof v === 'number' && isFinite(v); }

  function median(values) {
    const a = values.filter(isNum).slice().sort((x, y) => x - y);
    if (!a.length) return null;
    const m = Math.floor(a.length / 2);
    return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
  }

  // 每股淨值：PB 與股價推算；PB 或股價無效時回傳 null
  function bookValuePerShare(price, pb) {
    if (!isNum(price) || !isNum(pb) || price <= 0 || pb <= 0) return null;
    return price / pb;
  }

  function grahamNumber(eps, price, pb) {
    const bvps = bookValuePerShare(price, pb);
    if (!isNum(eps) || eps <= 0 || bvps === null) return null;
    return Math.sqrt(GRAHAM_K * eps * bvps);
  }

  // 同產業中位數（只計入合理範圍內的值）；樣本少於 minN 時回傳 null，改用全體中位數
  function industryMedian(rows, groupKey, valueKey, range, minN) {
    const lo = range[0], hi = range[1];
    const groups = {};
    const all = [];
    rows.forEach(r => {
      const v = r[valueKey];
      if (!isNum(v) || v < lo || v > hi) return;
      all.push(v);
      const k = r[groupKey];
      if (!k) return;
      (groups[k] = groups[k] || []).push(v);
    });
    const overall = median(all);
    const byGroup = {};
    Object.keys(groups).forEach(k => {
      byGroup[k] = groups[k].length >= (minN || 3) ? median(groups[k]) : null;
    });
    return { byGroup, overall };
  }

  function peFairValue(eps, medianPE) {
    if (!isNum(eps) || eps <= 0 || !isNum(medianPE) || medianPE <= 0) return null;
    return eps * medianPE;
  }

  function pbFairValue(price, pb, medianPB) {
    const bvps = bookValuePerShare(price, pb);
    if (bvps === null || !isNum(medianPB) || medianPB <= 0) return null;
    return bvps * medianPB;
  }

  function yieldFairValue(cashDividend, targetYieldPct) {
    if (!isNum(cashDividend) || cashDividend <= 0 || !isNum(targetYieldPct) || targetYieldPct <= 0) return null;
    return cashDividend / (targetYieldPct / 100);
  }

  function referenceValue(parts) {
    return median([parts.graham, parts.pe, parts.pb, parts.yield]);
  }

  function upsidePct(refValue, price) {
    if (!isNum(refValue) || !isNum(price) || price <= 0) return null;
    return (refValue / price - 1) * 100;
  }

  // 單一標的完整估值指標
  function valuationRow(row, medians, opts) {
    const o = Object.assign({ targetYieldPct: 5 }, opts || {});
    const price = row.price;
    const grp = row.group;
    const medPE = (grp && medians.pe.byGroup[grp] != null) ? medians.pe.byGroup[grp] : medians.pe.overall;
    const medPB = (grp && medians.pb.byGroup[grp] != null) ? medians.pb.byGroup[grp] : medians.pb.overall;
    const parts = {
      graham: grahamNumber(row.eps, price, row.pb),
      pe: peFairValue(row.eps, medPE),
      pb: pbFairValue(price, row.pb, medPB),
      yield: yieldFairValue(row.cashDividend, o.targetYieldPct),
    };
    const ref = referenceValue(parts);
    return Object.assign({}, parts, {
      medPE, medPB, ref, upside: upsidePct(ref, price),
    });
  }

  // ---------- DCF ----------
  // p: { fcf0, g1, g2, gT, wacc, shares, netDebt }  金額百萬、股數百萬、百分比為 %
  function dcf(p) {
    const out = { ok: false, reason: '', perShare: null, ev: null, pvFcf: null, pvTv: null, tvShare: null, fcfs: [] };
    const req = ['fcf0', 'g1', 'g2', 'gT', 'wacc', 'shares'];
    for (const k of req) {
      if (!isNum(p[k])) { out.reason = `缺少參數：${k}`; return out; }
    }
    const netDebt = isNum(p.netDebt) ? p.netDebt : 0;
    if (p.shares <= 0) { out.reason = '股數必須大於 0'; return out; }
    if (p.wacc <= p.gT) { out.reason = '折現率必須大於永續成長率'; return out; }
    if (p.fcf0 <= 0) { out.reason = '基期自由現金流為負或 0，兩階段 DCF 不適用（建議改用其他方法）'; return out; }

    let fcf = p.fcf0, pvSum = 0;
    const r = p.wacc / 100;
    for (let t = 1; t <= DCF_YEARS; t++) {
      const g = (t <= STAGE1_YEARS ? p.g1 : p.g2) / 100;
      fcf = fcf * (1 + g);
      const pv = fcf / Math.pow(1 + r, t);
      out.fcfs.push({ year: t, fcf, pv });
      pvSum += pv;
    }
    const tv = fcf * (1 + p.gT / 100) / (r - p.gT / 100);
    const pvTv = tv / Math.pow(1 + r, DCF_YEARS);
    const ev = pvSum + pvTv;
    const equity = ev - netDebt;

    out.ok = true;
    out.pvFcf = pvSum;
    out.pvTv = pvTv;
    out.ev = ev;
    out.tvShare = ev > 0 ? pvTv / ev * 100 : null;
    out.perShare = equity / p.shares;
    return out;
  }

  // 敏感度表：列 = WACC、欄 = 永續成長率，其餘參數沿用 base
  function sensitivity(base, waccs, gTs) {
    return waccs.map(w => gTs.map(gt => {
      const r = dcf(Object.assign({}, base, { wacc: w, gT: gt }));
      return r.ok ? r.perShare : null;
    }));
  }

  const api = {
    median, bookValuePerShare, grahamNumber, industryMedian,
    peFairValue, pbFairValue, yieldFairValue, referenceValue, upsidePct,
    valuationRow, dcf, sensitivity,
    GRAHAM_K, DCF_YEARS, STAGE1_YEARS,
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else g.MKLAB_VAL = api;
})(typeof window !== 'undefined' ? window : globalThis);
