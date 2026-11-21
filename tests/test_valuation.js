// 估值指標與 DCF 測試：node tests/test_valuation.js
// 以封閉解（closed-form）驗證，不依賴外部資料。
const assert = require('assert');
const V = require('../assets/js/valuation.js');

let pass = 0, fail = 0;
function t(name, fn) {
  try { fn(); pass++; console.log('PASS  ' + name); }
  catch (e) { fail++; console.log('FAIL  ' + name + '\n      ' + e.message); }
}
const close = (a, b, eps) => assert.ok(Math.abs(a - b) <= (eps || 1e-6), `expected ${b}, got ${a}`);

t('median 奇數／偶數／空值', () => {
  assert.strictEqual(V.median([3, 1, 2]), 2);
  assert.strictEqual(V.median([4, 1, 2, 3]), 2.5);
  assert.strictEqual(V.median([null, undefined, 'x']), null);
});

t('grahamNumber：√(22.5 × EPS × 每股淨值)', () => {
  // 股價 100、PB 2 → 每股淨值 50；EPS 4 → √(22.5×4×50)=√4500
  close(V.grahamNumber(4, 100, 2), Math.sqrt(4500));
});

t('grahamNumber：EPS ≤ 0、PB ≤ 0、股價缺漏皆回傳 null', () => {
  assert.strictEqual(V.grahamNumber(0, 100, 2), null);
  assert.strictEqual(V.grahamNumber(-1, 100, 2), null);
  assert.strictEqual(V.grahamNumber(4, 100, 0), null);
  assert.strictEqual(V.grahamNumber(4, null, 2), null);
});

t('industryMedian：樣本不足時 byGroup 為 null，全體中位數仍可用', () => {
  const rows = [
    { ind: 'A', pe: 10 }, { ind: 'A', pe: 20 }, { ind: 'A', pe: 30 },
    { ind: 'B', pe: 50 },
    { ind: 'C', pe: 999 }, // 超出範圍 → 不計入
  ];
  const m = V.industryMedian(rows, 'ind', 'pe', [0, 100], 3);
  assert.strictEqual(m.byGroup.A, 20);
  assert.strictEqual(m.byGroup.B, null);
  assert.strictEqual(m.overall, 25); // [10,20,30,50] 中位數
});

t('valuationRow：產業樣本不足時改用全體中位數', () => {
  const medians = {
    pe: { byGroup: { A: null }, overall: 15 },
    pb: { byGroup: { A: 2 }, overall: 3 },
  };
  const r = V.valuationRow({ price: 100, eps: 5, pb: 2.5, group: 'A', cashDividend: 4 }, medians, { targetYieldPct: 5 });
  assert.strictEqual(r.medPE, 15);      // 退回全體
  assert.strictEqual(r.pe, 75);         // 5 × 15
  close(r.pb, 100 / 2.5 * 2);           // 每股淨值 40 × 2 = 80
  close(r.yield, 80);                   // 4 ÷ 5%
  close(r.graham, Math.sqrt(22.5 * 5 * 40));
  assert.ok(r.ref !== null);
  close(r.upside, (r.ref / 100 - 1) * 100);
});

t('yieldFairValue：無股利或目標殖利率無效回傳 null', () => {
  assert.strictEqual(V.yieldFairValue(0, 5), null);
  assert.strictEqual(V.yieldFairValue(3, 0), null);
});

t('dcf 封閉解：FCF 固定、無成長、永續 0%、WACC 10%', () => {
  // 每年 100，共 10 年：PV = 100 × 年金係數(10%,10) = 614.4567
  // TV = 100 × 1 ÷ 10% = 1000，PV(TV) = 1000 ÷ 1.1^10 = 385.5433
  // EV = 1000；股數 100 → 每股 10
  const r = V.dcf({ fcf0: 100, g1: 0, g2: 0, gT: 0, wacc: 10, shares: 100, netDebt: 0 });
  assert.ok(r.ok);
  close(r.pvFcf, 614.456670, 1e-3);
  close(r.pvTv, 385.543330, 1e-3);
  close(r.ev, 1000, 1e-3);
  close(r.perShare, 10, 1e-3);
  close(r.tvShare, 38.554333, 1e-3);
});

t('dcf：淨負債會從 EV 扣除', () => {
  const base = { fcf0: 100, g1: 0, g2: 0, gT: 0, wacc: 10, shares: 100 };
  const a = V.dcf(Object.assign({}, base, { netDebt: 0 }));
  const b = V.dcf(Object.assign({}, base, { netDebt: 500 }));
  close(a.perShare - b.perShare, 5, 1e-9); // 500 ÷ 100 股
});

t('dcf：兩階段成長率套用正確（第 1–5 年 g1、第 6–10 年 g2）', () => {
  const r = V.dcf({ fcf0: 100, g1: 10, g2: 5, gT: 2, wacc: 9, shares: 100, netDebt: 0 });
  close(r.fcfs[0].fcf, 110);
  close(r.fcfs[4].fcf, 100 * Math.pow(1.1, 5), 1e-9);
  close(r.fcfs[5].fcf, 100 * Math.pow(1.1, 5) * 1.05, 1e-9);
  assert.strictEqual(r.fcfs.length, 10);
});

t('dcf：WACC ≤ 永續成長率 → 不計算並給出原因', () => {
  const r = V.dcf({ fcf0: 100, g1: 5, g2: 3, gT: 3, wacc: 3, shares: 100, netDebt: 0 });
  assert.strictEqual(r.ok, false);
  assert.ok(r.reason.indexOf('折現率') >= 0);
  assert.strictEqual(r.perShare, null);
});

t('dcf：基期 FCF ≤ 0 → 不計算並給出原因', () => {
  const r = V.dcf({ fcf0: -10, g1: 5, g2: 3, gT: 2, wacc: 9, shares: 100, netDebt: 0 });
  assert.strictEqual(r.ok, false);
  assert.ok(r.reason.indexOf('自由現金流') >= 0);
});

t('dcf：缺參數或股數 ≤ 0 不計算', () => {
  assert.strictEqual(V.dcf({ fcf0: 100, g1: 5, g2: 3, gT: 2, wacc: 9 }).ok, false);
  assert.strictEqual(V.dcf({ fcf0: 100, g1: 5, g2: 3, gT: 2, wacc: 9, shares: 0 }).ok, false);
});

t('sensitivity：維度正確，且中心點與單次計算一致', () => {
  const base = { fcf0: 100, g1: 8, g2: 4, gT: 2, wacc: 9, shares: 100, netDebt: 0 };
  const waccs = [8, 9, 10], gTs = [1, 2, 3];
  const grid = V.sensitivity(base, waccs, gTs);
  assert.strictEqual(grid.length, 3);
  assert.strictEqual(grid[0].length, 3);
  close(grid[1][1], V.dcf(base).perShare, 1e-9);
});

t('sensitivity：無效組合（WACC ≤ gT）回傳 null 而不是負數', () => {
  const base = { fcf0: 100, g1: 5, g2: 3, gT: 2, wacc: 9, shares: 100, netDebt: 0 };
  const grid = V.sensitivity(base, [1, 9], [2, 3]);
  assert.strictEqual(grid[0][0], null); // WACC 1 ≤ gT 2
  assert.strictEqual(grid[0][1], null);
  assert.ok(grid[1][0] !== null);
});

console.log(`\n合計 ${pass + fail} 項，PASS ${pass}，FAIL ${fail}`);
if (fail) process.exit(1);
