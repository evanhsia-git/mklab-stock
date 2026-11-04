// P0-4 持股單位與估值測試：node tests/test_portfolio_units.js
// 直接從 mklab-core.js 抽出 Portfolio 區塊執行（不改動頁面），以 localStorage mock 驗證。
const fs = require('fs'), path = require('path'), assert = require('assert');
const root = path.join(__dirname, '..');
const src = fs.readFileSync(path.join(root, 'assets/js/mklab-core.js'), 'utf8');
const a = src.indexOf('const PORTFOLIO_KEY = ');
const b = src.indexOf('// 關鍵：在 Drawer/Shell/Watch');
assert(a > 0 && b > a, '找不到 Portfolio 區塊');
const block = src.slice(a, b);

function load(storage) {
  const localStorage = {
    _d: storage || {},
    getItem(k) { return Object.prototype.hasOwnProperty.call(this._d, k) ? this._d[k] : null; },
    setItem(k, v) { this._d[k] = String(v); },
  };
  const factory = new Function('localStorage', block + '\nreturn { Portfolio, PORTFOLIO_KEY, _migrateV1 };');
  const m = factory(localStorage);
  return { ...m, ls: localStorage };
}

const results = [];
function t(name, fn) {
  try { fn(); results.push(['PASS', name]); }
  catch (e) { results.push(['FAIL', name + ' :: ' + e.message]); }
}

t('1 張 → 1000 股', () => {
  const { Portfolio } = load({});
  assert.strictEqual(Portfolio.lotsToShares(1), 1000);
  assert.strictEqual(Portfolio.sharesToLots(1000), 1);
});
t('10 張 → 10000 股', () => {
  const { Portfolio } = load({});
  assert.strictEqual(Portfolio.lotsToShares(10), 10000);
});
t('0.5 張（零股）→ 500 股', () => {
  const { Portfolio } = load({});
  assert.strictEqual(Portfolio.lotsToShares(0.5), 500);
});
t('1 張 2330 @ 900、現價 1000 → 市值 1,000,000、成本 900,000、損益 100,000、報酬 11.11%', () => {
  const { Portfolio } = load({});
  const v = Portfolio.valuation({ shares: 1000, cost: 900 }, 1000);
  assert.strictEqual(v.mktVal, 1000000);
  assert.strictEqual(v.costTotal, 900000);
  assert.strictEqual(v.pnl, 100000);
  assert.ok(Math.abs(v.pnlPct - 11.111) < 0.01);
});
t('10 張 0050 @ 150、現價 140 → 市值 1,400,000、成本 1,500,000、損益 -100,000、報酬 -6.67%', () => {
  const { Portfolio } = load({});
  const v = Portfolio.valuation({ shares: 10000, cost: 150 }, 140);
  assert.strictEqual(v.mktVal, 1400000);
  assert.strictEqual(v.costTotal, 1500000);
  assert.strictEqual(v.pnl, -100000);
  assert.ok(Math.abs(v.pnlPct + 6.667) < 0.01);
});
t('無行情 → 市值/損益/報酬為 null（不補 0）', () => {
  const { Portfolio } = load({});
  const v = Portfolio.valuation({ shares: 1000, cost: 900 }, null);
  assert.strictEqual(v.mktVal, null); assert.strictEqual(v.pnl, null); assert.strictEqual(v.pnlPct, null);
  assert.strictEqual(v.costTotal, 900000);
});
t('同股加權平均：1 張 @100 + 2 張 @130 → 3000 股 @ 120', () => {
  const { Portfolio, ls } = load({});
  Portfolio.add('2330', 1000, 100);
  Portfolio.add('2330', 2000, 130);
  const list = Portfolio.getAll();
  assert.strictEqual(list.length, 1);
  assert.strictEqual(list[0].shares, 3000);
  assert.ok(Math.abs(list[0].cost - 120) < 1e-9);
});
t('舊版 v1（張數）遷移為股數：v1 shares=10 → v2 shares=10000，v1 原始資料保留', () => {
  const v1 = JSON.stringify([{ sym: '0050', shares: 10, cost: 150, note: '' }]);
  const { Portfolio, ls, PORTFOLIO_KEY } = load({ mk_portfolio_v1: v1 });
  const list = Portfolio.getAll();
  assert.strictEqual(list[0].shares, 10000);
  assert.strictEqual(list[0].cost, 150);
  assert.strictEqual(ls._d.mk_portfolio_v1, v1, 'v1 不得被刪除');
  assert.ok(ls._d[PORTFOLIO_KEY], '應寫入 v2');
});
t('遷移只做一次：v2 已存在時不再依 v1 覆寫（不重複 ×1000）', () => {
  const v1 = JSON.stringify([{ sym: '0050', shares: 10, cost: 150 }]);
  const v2 = JSON.stringify([{ sym: '0050', shares: 10000, cost: 150, note: '' }]);
  const { Portfolio } = load({ mk_portfolio_v1: v1, mk_portfolio_v2: v2 });
  assert.strictEqual(Portfolio.getAll()[0].shares, 10000);
  assert.strictEqual(Portfolio.getAll()[0].shares, 10000);
});
t('無效輸入（0 股、負數、成本 0）不寫入', () => {
  const { Portfolio } = load({});
  Portfolio.add('2330', 0, 100); Portfolio.add('2330', -1000, 100); Portfolio.add('2330', 1000, 0);
  assert.strictEqual(Portfolio.getAll().length, 0);
});
t('remove 只移除指定代號', () => {
  const { Portfolio } = load({});
  Portfolio.add('2330', 1000, 100); Portfolio.add('0050', 1000, 150);
  Portfolio.remove('2330');
  assert.deepStrictEqual(Portfolio.getAll().map(h => h.sym), ['0050']);
});

const fail = results.filter(r => r[0] === 'FAIL');
results.forEach(r => console.log(r[0], r[1]));
console.log(`\n合計 ${results.length} 項，PASS ${results.length - fail.length}，FAIL ${fail.length}`);
process.exit(fail.length ? 1 : 0);
