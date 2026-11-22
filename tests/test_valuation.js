// 估值指標與 DCF 測試：node tests/test_valuation.js
const assert = require('assert');
const V = require('../assets/js/valuation.js');

let pass = 0, fail = 0;
function t(name, fn) {
  try { fn(); pass++; console.log('PASS  ' + name); }
  catch (e) { fail++; console.log('FAIL  ' + name + '\n      ' + e.message); }
}
const close = (a, b, eps) => assert.ok(Math.abs(a - b) <= (eps || 1e-6), `expected ${b}, got ${a}`);

// ---------- 基本統計與工具 ----------
t('median 奇數／偶數／空值', () => {
  assert.strictEqual(V.median([3, 1, 2]), 2);
  assert.strictEqual(V.median([4, 1, 2, 3]), 2.5);
  assert.strictEqual(V.median([null, undefined, 'x']), null);
});

t('grahamNumber：√(22.5 × EPS × 每股淨值)；EPS ≤ 0 或 PB ≤ 0 為 null', () => {
  close(V.grahamNumber(4, 100, 2), Math.sqrt(4500));
  assert.strictEqual(V.grahamNumber(0, 100, 2), null);
  assert.strictEqual(V.grahamNumber(4, 100, 0), null);
});

t('industryMedian：範圍外的值不計入；樣本不足時該產業為 null', () => {
  const rows = [
    { ind: 'A', pe: 10 }, { ind: 'A', pe: 20 }, { ind: 'A', pe: 30 },
    { ind: 'B', pe: 50 },
    { ind: 'C', pe: 999 },
  ];
  const m = V.industryMedian(rows, 'ind', 'pe', [0, 100], 3);
  assert.strictEqual(m.byGroup.A, 20);
  assert.strictEqual(m.byGroup.B, null);
  assert.strictEqual(m.overall, 25);
});

// ---------- 估值指標：防止誇大 ----------
const medians = {
  pe: { byGroup: { A: 15 }, overall: 14 },
  pb: { byGroup: { A: 2 }, overall: 1.5 },
};

t('valuationRow：EPS 由股價 ÷ 報告 PE 推算（與股價同時點），不採用獨立 EPS 欄位', () => {
  // 股價 100、PE 20 → EPS 5；PE 合理價 = 5 × 15 = 75
  const r = V.valuationRow({ price: 100, pe: 20, pb: 2.5, divPct: 4, group: 'A' }, medians, { targetYieldPct: 5 });
  close(r.pe, 75);
  // PB 2.5 → 每股淨值 40；PB 合理價 = 40 × 2 = 80
  close(r.pb, 80);
  // 殖利率 4% ÷ 目標 5% → 股價 × 0.8 = 80
  close(r.yield, 80);
  close(r.graham, Math.sqrt(22.5 * 5 * 40));
  assert.strictEqual(r.methods, 4);
  // 候選值 Graham 67.08、PE 75、PB 80、殖利率 80 → 中位數 (75+80)/2
  close(r.ref, 77.5);
});

t('valuationRow：PE 低於 5（疑似一次性獲利）不計入 PE 與 Graham', () => {
  const r = V.valuationRow({ price: 100, pe: 3, pb: 2.5, divPct: null, group: 'A' }, medians);
  assert.strictEqual(r.pe, null);
  assert.strictEqual(r.graham, null);
  assert.ok(r.methods <= 2);
});

t('valuationRow：PB 低於 0.3（資產減損或資料異常）不計入 PB 與 Graham', () => {
  const r = V.valuationRow({ price: 100, pe: 15, pb: 0.1, divPct: null, group: 'A' }, medians);
  assert.strictEqual(r.pb, null);
  assert.strictEqual(r.graham, null);
});

t('valuationRow：殖利率只用報告殖利率（百分比），不再以單次現金股利放大', () => {
  const r = V.valuationRow({ price: 50, pe: 15, pb: 2, divPct: 40, group: 'A' }, medians);
  assert.strictEqual(r.yield, null);   // 40% 超出 0.5–15% 範圍
});

t('valuationRow：可用方法少於 2 個時不給綜合參考價', () => {
  const r = V.valuationRow({ price: 100, pe: null, pb: null, divPct: null, group: 'A' }, medians);
  assert.strictEqual(r.ref, null);
  assert.strictEqual(r.upside, null);
});

t('valuationRow：離譜的合理價（超過股價 5 倍）不計入綜合參考價', () => {
  // PE 合理價 = (100÷5)×15 = 300 = 股價 3 倍（保留）；PB 合理價若超過 5 倍則排除
  const med = { pe: { byGroup: { A: 60 }, overall: 60 }, pb: { byGroup: { A: 10 }, overall: 10 } };
  const r = V.valuationRow({ price: 100, pe: 5, pb: 0.5, divPct: 3, group: 'A' }, med);
  assert.ok(r.ref === null || r.ref <= 500, 'ref must stay within 5x of price');
  if (r.pb !== null) assert.ok(r.pb > 500, 'PB 合理價應超過 5 倍而被排除（測試前提）');
});

t('referenceValue：只取股價 0.2–5 倍之間的候選值之中位數', () => {
  close(V.referenceValue(100, [50, 120, 900, 80]), 80);   // 900 被排除 → [50,80,120] 中位數 80
  assert.strictEqual(V.referenceValue(100, [900, 800]), null);
});

// ---------- DCF：5 年 ----------
t('dcf 封閉解：FCF 固定（g=0）、永續 0%、WACC 10%', () => {
  // 每年 100，共 5 年：PV = 100 × 年金係數(10%,5) = 379.0787
  // TV = 100 × 1 ÷ 10% = 1000，PV(TV) = 1000 ÷ 1.1^5 = 620.9213
  // EV = 1000；股數 100 → 每股 10
  const r = V.dcf({ fcf0: 100, g: 0, gT: 0, wacc: 10, shares: 100, netDebt: 0 });
  assert.ok(r.ok);
  close(r.pvFcf, 379.078676, 1e-3);
  close(r.pvTv, 620.921323, 1e-3);
  close(r.ev, 1000, 1e-3);
  close(r.perShare, 10, 1e-3);
  assert.strictEqual(r.fcfs.length, 5);
});

t('dcf：只有 5 年明確預測（不再有 10 年或第二階段成長率）', () => {
  const r = V.dcf({ fcf0: 100, g: 10, gT: 2, wacc: 9, shares: 100, netDebt: 0 });
  close(r.fcfs[0].fcf, 110);
  close(r.fcfs[4].fcf, 100 * Math.pow(1.1, 5), 1e-9);
  assert.strictEqual(r.fcfs.length, 5);
});

t('dcf：淨負債從 EV 扣除', () => {
  const base = { fcf0: 100, g: 0, gT: 0, wacc: 10, shares: 100 };
  close(V.dcf(Object.assign({}, base, { netDebt: 0 })).perShare - V.dcf(Object.assign({}, base, { netDebt: 500 })).perShare, 5, 1e-9);
});

t('dcf：WACC ≤ 永續成長率、FCF ≤ 0、股數 ≤ 0、缺參數皆不計算並說明原因', () => {
  assert.ok(V.dcf({ fcf0: 100, g: 5, gT: 3, wacc: 3, shares: 100 }).reason.indexOf('折現率') >= 0);
  assert.ok(V.dcf({ fcf0: -10, g: 5, gT: 2, wacc: 9, shares: 100 }).reason.indexOf('自由現金流') >= 0);
  assert.strictEqual(V.dcf({ fcf0: 100, g: 5, gT: 2, wacc: 9, shares: 0 }).ok, false);
  assert.strictEqual(V.dcf({ fcf0: 100, g: 5, gT: 2, wacc: 9 }).ok, false);
});

t('inputWarnings：極端假設會給提醒（永續成長率、折現率、終值佔比）', () => {
  const w = V.inputWarnings({ g: 5, gT: 29, wacc: 30 }, { tvShare: 94 });
  assert.ok(w.some(x => x.indexOf('永續成長率') >= 0));
  assert.ok(w.some(x => x.indexOf('折現率超過 15%') >= 0));
  assert.ok(w.some(x => x.indexOf('終值佔') >= 0));
  assert.strictEqual(V.inputWarnings({ g: 5, gT: 2.5, wacc: 9 }, { tvShare: 60 }).length, 0);
});

// ---------- 驗證案例：Datafin 截圖（2026-11 公開畫面） ----------
// 截圖參數：Year1 138,707.04、Year2 148,943.62（百萬美元）；淨負債 16,204；股數約 14,768 百萬股
// 截圖結果：每股公允價值 $458.31，折現率 30%，終值隱含永續成長約 29%，終值佔 EV 約 94%
const DF = { fcf0: 138707.04 / 1.0738, g: 7.38, netDebt: 16204, shares: 14768 };

t('驗證：引擎可精確重現 Datafin 每股 $458.31（證明計算公式正確）', () => {
  const r = V.dcf(Object.assign({}, DF, { wacc: 30, gT: 29 }));
  close(r.perShare, 458.31, 0.05);
  close(r.tvShare, 94.4, 0.1);
  assert.ok(r.warnings.length >= 2, '極端假設應觸發提醒');
});

t('驗證：同一現金流、合理假設（WACC 9%、永續 2.5%）每股約 $169，遠低於 $458', () => {
  const r = V.dcf(Object.assign({}, DF, { wacc: 9, gT: 2.5 }));
  close(r.perShare, 168.71, 0.05);
  assert.ok(r.perShare < 458.31 * 0.5, 'Datafin 的 +80% 安全邊際完全來自假設');
});

t('驗證：永續成長率每提高 1 個百分點，每股價值明顯上升（敏感度存在）', () => {
  const a = V.dcf(Object.assign({}, DF, { wacc: 9, gT: 2.5 })).perShare;
  const b = V.dcf(Object.assign({}, DF, { wacc: 9, gT: 3.5 })).perShare;
  assert.ok(b > a * 1.05);
});

// ---------- 敏感度 ----------
t('sensitivity：維度正確、中心點與單次計算一致、WACC ≤ gT 為 null', () => {
  const base = { fcf0: 100, g: 8, gT: 2, wacc: 9, shares: 100, netDebt: 0 };
  const grid = V.sensitivity(base, [8, 9, 10], [1, 2, 3]);
  assert.strictEqual(grid.length, 3);
  assert.strictEqual(grid[0].length, 3);
  close(grid[1][1], V.dcf(base).perShare, 1e-9);
  const g2 = V.sensitivity(base, [1, 9], [2, 3]);
  assert.strictEqual(g2[0][0], null);
  assert.ok(g2[1][0] !== null);
});

// ---------- 現金流資料整理 ----------
t('toMillions / ttmSum / fcfFromCashFlow 基本行為', () => {
  assert.strictEqual(V.toMillions(259303804, 'thousand'), 259303.804);
  assert.strictEqual(V.toMillions(null, 'thousand'), null);
  assert.strictEqual(V.ttmSum([1, 2, 3, 4]), 10);
  assert.strictEqual(V.ttmSum([1, 2, 3]), null);
  assert.strictEqual(V.fcfFromCashFlow(100, -30), 70);
  assert.strictEqual(V.fcfFromCashFlow(100, null), null);
});

console.log(`\n合計 ${pass + fail} 項，PASS ${pass}，FAIL ${fail}`);
if (fail) process.exit(1);
