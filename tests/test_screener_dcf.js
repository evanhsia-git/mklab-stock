// Screener「DCF 估值」分頁邏輯的煙霧測試（假 DOM + 假資料，不連網）：node tests/test_screener_dcf.js
const fs = require('fs'), path = require('path'), assert = require('assert');
const root = path.join(__dirname, '..');

// ---- 假 DOM ----
class El {
  constructor(id) { this.id = id || ''; this.value = ''; this._t = ''; this.children = []; this.className = ''; this.title = ''; this.style = {}; }
  set textContent(v) { this._t = String(v); if (v === '') this.children = []; }
  get textContent() { return this._t; }
  appendChild(c) { this.children.push(c); return c; }
}
const els = {};
const document = {
  getElementById(id) { return els[id] || (els[id] = new El(id)); },
  createElement(tag) { return new El(tag); },
  querySelectorAll() { return []; },
};

// ---- 假資料 ----
const fixtures = {
  'stocks': { stocks: [
    { sym: '2330', name: '台積電', security_type: 'stock', price: 2100, pe: 21.29, pb: 7.78, eps: 98.66, ind: '半導體業', div_cash_latest: 14, shares: 25932370067, price_asof: '2026-11-13', source: 'TWSE' },
    { sym: '2454', name: '聯發科', security_type: 'stock', price: 1500, pe: 20, pb: 5, eps: 75, ind: '半導體業', div_cash_latest: 40, shares: 1588000000, price_asof: '2026-11-13', source: 'TWSE' },
    { sym: '2317', name: '鴻海', security_type: 'stock', price: 200, pe: 15, pb: 2, eps: 13.3, ind: '其他電子業', div_cash_latest: 6, shares: 13000000000, price_asof: '2026-11-13', source: 'TWSE' },
    { sym: '1101', name: '台泥', security_type: 'stock', price: 40, pe: null, pb: 1.2, eps: -0.5, ind: '水泥工業', div_cash_latest: 1.5, shares: 5000000000, price_asof: '2026-11-13', source: 'TWSE' },
    { sym: '0050', name: '元大台灣50', security_type: 'etf', price: 60, pe: null, pb: null, eps: null, ind: null, source: 'TWSE' },
  ] },
  'us/us-stocks': { stocks: [
    { sym: 'AAPL', name: 'Apple', price: 342.56, pe: 38.1, pb: 44.4, eps: 8.98, div: 0.32, industry: 'Consumer Electronics', sector: 'Technology', shares_mln: 14776.35, fcf_musd: 99584, cash_musd: 61000, debt_musd: 98000 },
    { sym: 'MSFT', name: 'Microsoft', price: 523.88, pe: 27.3, pb: 8.3, eps: 19.16, div: 0.75, industry: 'Software', sector: 'Technology', shares_mln: 7430, fcf_musd: 70000, cash_musd: 30000, debt_musd: 40000 },
    { sym: 'NVDA', name: 'NVIDIA', price: 166.19, pe: 21, pb: 17, eps: 7.91, div: 0.02, industry: 'Semiconductors', sector: 'Technology', shares_mln: 24300, fcf_musd: null, cash_musd: null, debt_musd: null },
  ] },
};

// ---- 假 MKLAB ----
const tables = {};
const MKLAB = {
  data: { json: (name) => Promise.resolve(fixtures[name]) },
  DataTable(id, opts) { tables[id] = { id, cols: opts.cols, rows: opts.rows, setRows(r) { this.rows = r; } }; return tables[id]; },
};

// ---- 載入被測模組 ----
const valSrc = fs.readFileSync(path.join(root, 'assets/js/valuation.js'), 'utf8');
const dcfSrc = fs.readFileSync(path.join(root, 'assets/js/screener-dcf.js'), 'utf8');
const win = { MKLAB };
const V = (new Function('window', 'globalThis', valSrc + '\nreturn window.MKLAB_VAL;'))(win, {});
win.MKLAB_VAL = V;
new Function('window', 'document', 'MKLAB', dcfSrc)(win, document, MKLAB);
const DCF = win.MKLAB_DCF;
assert.ok(DCF, 'MKLAB_DCF 未載入');

const tick = () => new Promise(r => setTimeout(r, 0));
let pass = 0, fail = 0;
async function t(name, fn) {
  try { await fn(); pass++; console.log('PASS  ' + name); }
  catch (e) { fail++; console.log('FAIL  ' + name + '\n      ' + e.message); }
}

(async () => {
  // 先放好計算機的輸入欄位（頁面上會有這些元素）
  ['dcf_g1','dcf_g2','dcf_gT','dcf_wacc','dcf_fcf','dcf_shares','dcf_netdebt','dcf_price','dcfYield','dcfSearch','dcfValCount','dcfNote','dcfFcfHint','dcfOut','dcfSens','dcfList','dcfValPager']
    .forEach(id => document.getElementById(id));
  el('dcfYield').value = '5';

  await t('啟動分頁後估值指標表載入台股（僅股票、排除 ETF）', async () => {
    DCF.activate(); await tick(); await tick();
    assert.ok(tables.dcfValTable, '表格未建立');
    // 4 檔一般股（含 EPS<0 的 1101，其合理價顯示為空）；ETF 0050 排除
    assert.strictEqual(tables.dcfValTable.rows.length, 4);
    assert.ok(/符合：4 \/ 4/.test(el('dcfValCount').textContent), el('dcfValCount').textContent);
  });

  await t('估值指標：2330 的 Graham 與綜合參考價為有限正數', async () => {
    const row = tables.dcfValTable.rows.find(r => r.sym === '2330');
    assert.ok(row.val_graham > 0 && isFinite(row.val_graham));
    assert.ok(row.val_ref > 0 && isFinite(row.val_ref));
    assert.ok(isFinite(row.val_upside));
  });

  await t('估值指標：EPS 為負的 1101 不產生 Graham 與 PE 合理價', async () => {
    const row = tables.dcfValTable.rows.find(r => r.sym === '1101');
    assert.strictEqual(row.val_graham, null);
    assert.strictEqual(row.val_pe, null);
  });

  await t('搜尋過濾：輸入 聯發 只剩 2454', async () => {
    el('dcfSearch').value = '聯發';
    DCF.applyVal();
    assert.strictEqual(tables.dcfValTable.rows.length, 1);
    assert.strictEqual(tables.dcfValTable.rows[0].sym, '2454');
    el('dcfSearch').value = '';
    DCF.applyVal();
  });

  await t('台股選股：自動帶入股數（百萬股）與股價，FCF 留空並提示手動輸入', async () => {
    DCF.selectStock('2330'); await tick();
    assert.ok(Math.abs(parseFloat(el('dcf_shares').value) - 25932.370067) < 0.01, 'shares=' + el('dcf_shares').value);
    assert.strictEqual(el('dcf_fcf').value, '');
    assert.ok(/手動輸入/.test(el('dcfFcfHint').textContent));
  });

  await t('計算機：輸入 FCF 後產生每股內在價值與敏感度表', async () => {
    el('dcf_fcf').value = '1500000';          // 基期 FCF，單位 NT$ 百萬（1.5 兆）
    DCF.calc();
    const out = el('dcfOut');
    assert.ok(out.children.length > 0, '沒有輸出');
    const dl = out.children.find(c => c.className === 'dcf-summary');
    assert.ok(dl, '缺少結果摘要');
    const labels = dl.children.filter((_, i) => i % 2 === 0).map(c => c.textContent);
    assert.ok(labels.includes('每股內在價值'));
    const sens = el('dcfSens');
    const table = sens.children.find(c => c.className === 'dcf-sens');
    assert.ok(table, '缺少敏感度表');
    assert.strictEqual(table.children.length, 6, '表頭列 + 5 列 WACC');   // 1 header + 5 rows
  });

  await t('計算機：折現率 ≤ 永續成長率時顯示原因而不輸出數字', async () => {
    el('dcf_wacc').value = '2'; el('dcf_gT').value = '3';
    DCF.calc();
    assert.ok(/無法計算/.test(el('dcfOut').children[0].textContent));
    assert.strictEqual(el('dcfSens').textContent, '');
    el('dcf_wacc').value = '9'; el('dcf_gT').value = '2';
  });

  await t('美股切換：NVDA 缺 FCF，計算機留空並提示', async () => {
    DCF.setMarket('us', { }); await tick(); await tick();
    assert.strictEqual(tables.dcfValTable.rows.length, 3);   // AAPL / MSFT / NVDA
    DCF.selectStock('NVDA'); await tick();
    assert.strictEqual(el('dcf_fcf').value, '');
    assert.ok(/缺少自由現金流/.test(el('dcfFcfHint').textContent));
  });

  await t('美股選股：AAPL 預填 FCF、股數與淨負債（負債 − 現金）', async () => {
    DCF.selectStock('AAPL'); await tick();
    assert.strictEqual(parseFloat(el('dcf_fcf').value), 99584);
    assert.strictEqual(parseFloat(el('dcf_netdebt').value), 37000);
    assert.ok(/預填/.test(el('dcfFcfHint').textContent));
  });

  await t('重設會回到預設參數並清空選股', async () => {
    DCF.resetCalc();
    assert.strictEqual(el('dcf_g1').value, '8');
    assert.strictEqual(el('dcf_wacc').value, '9');
    assert.strictEqual(el('dcf_fcf').value, '');
  });

  await t('找不到代號時給出提示', async () => {
    DCF.selectStock('XXXX');
    assert.ok(/找不到/.test(el('dcfNote').textContent));
  });

  console.log(`\n合計 ${pass + fail} 項，PASS ${pass}，FAIL ${fail}`);
  if (fail) process.exit(1);
})();

function el(id) { return document.getElementById(id); }
