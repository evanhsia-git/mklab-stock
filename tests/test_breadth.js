// P0-5 市場寬度測試：node tests/test_breadth.js
// 直接從 assets/js/mklab-core.js（共用 BreadthPanel）抽出 BUCKETS 與 validStocks 執行，不改動頁面。
const fs = require('fs'), path = require('path'), assert = require('assert');
const html = fs.readFileSync(path.join(__dirname, '..', 'assets', 'js', 'mklab-core.js'), 'utf8');
const bm = html.match(/const BUCKETS = \[([\s\S]*?)\n\s*\];/);
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

// 共用 BreadthPanel.render 煙霧測試（用假 DOM；確認 Industry / Breadth 兩頁共用的面板能完整渲染且數字自洽）
{
  const core = fs.readFileSync(path.join(__dirname, '..', 'assets', 'js', 'mklab-core.js'), 'utf8');
  const s = core.indexOf('const BreadthPanel = (function () {');
  const e = core.indexOf('  // ============================================================\n  //  Notes');
  assert(s > 0 && e > s, '找不到 BreadthPanel 區塊');
  const els = {};
  const document = { getElementById: id => (els[id] = els[id] || { innerHTML: '', textContent: '' }) };
  const BreadthPanel = new Function('document', core.slice(s, e) + '\nreturn BreadthPanel;')(document);
  t('BreadthPanel.render：摘要／分布／產業表／說明列都有輸出，且有效行情 = 上漲+下跌+平盤', () => {
    BreadthPanel.render([
      { security_type: 'stock', chg: 1.2, ind: 'A' }, { security_type: 'stock', chg: -2, ind: 'A' },
      { security_type: 'stock', chg: 0, ind: 'B' }, { security_type: 'stock', chg: null, ind: 'B' },
      { security_type: 'etf', chg: 3, ind: 'A' }, { security_type: 'other', chg: 9, ind: 'A' },
    ], '2026-11-03');
    assert(els.breadthSummary.innerHTML.includes('上漲家數') && els.histWrap.innerHTML.includes('breadth-bar-row'));
    assert(els.indBreadthTable.innerHTML.includes('<td>A</td><td>1</td><td>2</td><td>2</td>'), els.indBreadthTable.innerHTML);
    assert(els.breadthMeta.textContent.includes('有效行情 3 檔') && els.breadthMeta.textContent.includes('排除無行情 1 檔'), els.breadthMeta.textContent);
  });
}

const fail = results.filter(r => r[0] === 'FAIL');
results.forEach(r => console.log(r[0], r[1]));
console.log(`\n合計 ${results.length} 項，PASS ${results.length - fail.length}，FAIL ${fail.length}`);
process.exit(fail.length ? 1 : 0);
