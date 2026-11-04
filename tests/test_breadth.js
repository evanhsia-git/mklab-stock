// P0-5 市場寬度測試：node tests/test_breadth.js
// 直接從 mklab-stock-industry.html 抽出 BUCKETS 與 validStocks 執行，不改動頁面。
const fs = require('fs'), path = require('path'), assert = require('assert');
const html = fs.readFileSync(path.join(__dirname, '..', 'mklab-stock-industry.html'), 'utf8');
const bm = html.match(/const BUCKETS = \[([\s\S]*?)\n    \];/);
assert(bm, '找不到 BUCKETS');
const BUCKETS = eval('[' + bm[1] + ']');
const vm = html.match(/function validStocks\(stocks\) \{\n\s*return ([^\n]+);\n/);
assert(vm, '找不到 validStocks');
const validStocks = eval('(function (stocks) { return ' + vm[1] + '; })');

const results = [];
function t(name, fn) { try { fn(); results.push(['PASS', name]); } catch (e) { results.push(['FAIL', name + ' :: ' + e.message]); } }

t('分布區間：每個漲跌幅（含邊界）恰好落在一個區間，不重疊、不遺漏', () => {
  const samples = [-100, -7.0001, -7, -6.99, -3, -2.99, -1, -0.5, 0, 0.5, 1, 2.99, 3, 6.99, 7, 9.9, 10.5];
  for (const v of samples) {
    const hits = BUCKETS.filter(b => b.test(v)).length;
    assert.strictEqual(hits, 1, `值 ${v} 落在 ${hits} 個區間`);
  }
});

t('分布區間加總 = 有效行情檔數（上漲+下跌+平盤）', () => {
  const stocks = [
    { security_type: 'stock', chg: 1.2 }, { security_type: 'stock', chg: -0.5 }, { security_type: 'stock', chg: 0 },
    { security_type: 'stock', chg: -8 }, { security_type: 'stock', chg: 7.5 },
    { security_type: 'stock', chg: null }, { security_type: 'etf', chg: 1 }, { security_type: 'other', chg: -2 },
  ];
  const valid = validStocks(stocks);
  const total = BUCKETS.reduce((s, b) => s + valid.filter(r => b.test(r.chg)).length, 0);
  const up = valid.filter(r => r.chg > 0).length, down = valid.filter(r => r.chg < 0).length, flat = valid.filter(r => r.chg === 0).length;
  assert.strictEqual(valid.length, 5);
  assert.strictEqual(total, valid.length);
  assert.strictEqual(up + down + flat, valid.length);
});

t('validStocks 排除 ETF、其他證券與 chg=null（不補 0、不當平盤）', () => {
  const stocks = [
    { security_type: 'stock', chg: null }, { security_type: 'etf', chg: 0.4 }, { security_type: 'other', chg: 0 },
    { security_type: 'stock', chg: 0 }, { security_type: 'unverified', chg: 3 },
  ];
  const v = validStocks(stocks);
  assert.deepStrictEqual(v.map(r => r.security_type + ':' + r.chg), ['stock:0']);
});

const fail = results.filter(r => r[0] === 'FAIL');
results.forEach(r => console.log(r[0], r[1]));
console.log(`\n合計 ${results.length} 項，PASS ${results.length - fail.length}，FAIL ${fail.length}`);
process.exit(fail.length ? 1 : 0);
