// Screener「DCF 估值」分頁邏輯的煙霧測試（假 DOM＋假資料，不連網）：node tests/test_screener_dcf.js
const fs = require('fs'), path = require('path'), assert = require('assert');
const root = path.join(__dirname, '..');

// ---- 假 DOM（只實作本頁用到的 API） ----
class El {
  constructor(tag, id) {
    this.tagName = tag; this.id = id || ''; this.value = ''; this._t = '';
    this.children = []; this.className = ''; this.title = ''; this.style = {
      setProperty(k, v) { this[k] = v; },
    };
    this.dataset = {};
    this.classList = {
      _s: new Set(),
      add(c) { this._s.add(c); }, remove(c) { this._s.delete(c); },
      toggle(c, on) { if (on) this._s.add(c); else this._s.delete(c); },
      contains(c) { return this._s.has(c); },
    };
  }
  set textContent(v) { this._t = String(v); if (v === '') this.children = []; }
  get textContent() { return this._t; }
  get childNodes() { return this.children; }
  appendChild(c) { this.children.push(c); return c; }
  addEventListener() {}
  setAttribute(k, v) { this[k] = v; }
  closest() { return null; }
  querySelector() { return null; }
}
const els = {};
const document = {
  getElementById(id) { return els[id] || (els[id] = new El('div', id)); },
  createElement(tag) { return new El(tag); },
  createElementNS(ns, tag) { return new El(tag); },
  createTextNode(t) { return { textContent: t }; },
  querySelectorAll() { return []; },
};

// ---- 假資料 ----
const fixtures = {
  'stocks': { stocks: [
    { sym: '2330', name: '台積電', security_type: 'stock', price: 2100, pe: 21.29, pb: 7.78, eps: 98.66, div: 0.67, ind: '半導體業', shares: 25932370067, source: 'TWSE' },
    { sym: '2454', name: '聯發科', security_type: 'stock', price: 1500, pe: 20, pb: 5, eps: 75, div: 2.7, ind: '半導體業', shares: 1588000000, source: 'TWSE' },
    { sym: '2317', name: '鴻海', security_type: 'stock', price: 200, pe: 15, pb: 2, eps: 13.3, div: 3, ind: '其他電子業', shares: 13000000000, source: 'TWSE' },
    { sym: '1101', name: '台泥', security_type: 'stock', price: 40, pe: null, pb: 1.2, eps: -0.5, div: 3.75, ind: '水泥工業', shares: 5000000000, source: 'TWSE' },
    { sym: '0050', name: '元大台灣50', security_type: 'etf', price: 60, pe: null, pb: null, eps: null, ind: null, source: 'TWSE' },
  ] },
  // 真實結構：美股資料只有市值(market_cap)與 EPS，沒有 shares/fcf/debt/cash
  'us/us-stocks': { stocks: [
    { sym: 'AAPL', name: 'Apple', price: 342.56, pe: 38.1, pb: 44.4, eps: 8.98, div: 0.32, industry: 'Consumer Electronics', sector: 'Technology', market_cap: 4978144444416 },
    { sym: 'MSFT', name: 'Microsoft', price: 523.88, pe: 27.3, pb: 8.3, eps: 19.16, div: 0.75, industry: 'Software', sector: 'Technology', market_cap: 3890000000000 },
    { sym: 'NVDA', name: 'NVIDIA', price: 166.19, pe: 21, pb: 17, eps: 7.91, div: 0.02, industry: 'Semiconductors', sector: 'Technology', market_cap: 4058000000000 },
  ] },
};

// ---- 假 MKLAB ----
const tables = {};
const exportCalls = [], registered = {};
const MKLAB = {
  data: { json: (name) => Promise.resolve(fixtures[name]) },
  DataTable(id, opts) { tables[id] = { id, cols: opts.cols, rows: opts.rows, page: 1, render() {}, setRows(r) { this.rows = r; this.page = 1; } }; return tables[id]; },
  exportCSV(rows, cols, opts) { exportCalls.push({ rows, cols, opts }); },
  registerExport(label, fn) { registered[label] = fn; },
};

// ---- 載入被測模組 ----
const valSrc = fs.readFileSync(path.join(root, 'assets/js/valuation.js'), 'utf8');
const dcfSrc = fs.readFileSync(path.join(root, 'assets/js/screener-dcf.js'), 'utf8');
const store = {};
const win = { MKLAB, localStorage: { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } } };
const V = (new Function('window', 'globalThis', valSrc + '\nreturn window.MKLAB_VAL;'))(win, {});
win.MKLAB_VAL = V;
new Function('window', 'document', 'MKLAB', dcfSrc)(win, document, MKLAB);
const DCF = win.MKLAB_DCF;
assert.ok(DCF, 'MKLAB_DCF 未載入');

const tick = () => new Promise(r => setTimeout(r, 0));
const el = id => document.getElementById(id);
let pass = 0, fail = 0;
async function t(name, fn) {
  try { await fn(); pass++; console.log('PASS  ' + name); }
  catch (e) { fail++; console.log('FAIL  ' + name + '\n      ' + e.message); }
}
const find = (node, cls) => node.children.find(c => c.className === cls);

(async () => {
  el('dvYield').value = '5';
  el('dvG').value = '8'; el('dvGT').value = '2'; el('dvWacc').value = '9';

  await t('啟動後估值表只含台股一般股（4 檔，ETF 排除），並計算出參考價', async () => {
    DCF.activate(); await tick(); await tick();
    assert.ok(tables.dvTable, '表格未建立');
    assert.strictEqual(tables.dvTable.rows.length, 4);
    const r = tables.dvTable.rows.find(x => x.sym === '2330');
    assert.ok(r.val_ref > 0 && isFinite(r.val_ref));
    assert.ok(/符合 4 \/ 4/.test(el('dvCount').textContent), el('dvCount').textContent);
  });

  await t('估值表：EPS 為負的 1101 不產生 Graham 與 PE 合理價', async () => {
    const r = tables.dvTable.rows.find(x => x.sym === '1101');
    assert.strictEqual(r.val_graham, null);
    assert.strictEqual(r.val_pe, null);
  });

  await t('選取台股：股數（百萬）與股價帶入；現金流留空並提示手動輸入', async () => {
    DCF.selectStock('2330'); await tick();
    assert.ok(Math.abs(parseFloat(el('dvShares').value) - 25932.370067) < 0.01);
    assert.strictEqual(el('dvPrice').value, '2100');
    assert.strictEqual(el('dvFcf').value, '');
    assert.ok(/自行估算.*輸入/.test(el('dvFcfHint').textContent));
  });

  await t('個股細節：五種方法長條圖（4 種合理價 + 綜合參考價）', async () => {
    const bars = el('dvBars');
    assert.strictEqual(bars.children.length, 5);
    assert.ok(/綜合參考價/.test(bars.children[4].children[0].textContent));
  });

  await t('DCF 試算：輸入現金流後顯示每股價值、EV 組成、5 年長條圖、敏感度表', async () => {
    el('dvNetDebt').value = '0';
    el('dvFcf').value = '1500000';
    DCF.calc();
    const res = el('dvResult');
    const flat = (n) => [n].concat(...(n.children || []).map(flat));
    const all = flat(res);
    assert.ok(all.some(c => c.className === 'dv-big'), '缺少每股價值');
    assert.ok(all.some(c => c.className === 'dv-stack'), '缺少企業價值組成條');
    const chart = el('dvChart');
    assert.ok(chart.children.some(c => c.tagName === 'svg'), '缺少長條圖');
    const svg = chart.children.find(c => c.tagName === 'svg');
    assert.strictEqual(svg.children.filter(c => c.tagName === 'text' && /第 \d 年/.test(c.textContent)).length, 5, '應有 5 個年度標籤');
    const table = el('dvSens').children.find(c => c.tagName === 'table');
    assert.strictEqual(table.children.length, 6, '表頭 + 5 列 WACC');
  });

  await t('DCF 試算：極端假設（折現率 30%、永續 29%）會顯示提醒', async () => {
    el('dvNetDebt').value = '0';
    el('dvWacc').value = '30'; el('dvGT').value = '29';
    DCF.calc();
    const warn = el('dvWarn');
    assert.ok(warn.children.length >= 1, '應有提醒');
    el('dvWacc').value = '9'; el('dvGT').value = '2';
    DCF.calc();
    assert.strictEqual(el('dvWarn').children.length, 0, '合理假設不應有提醒');
  });

  await t('折現率 ≤ 永續成長率：顯示原因而不輸出數字', async () => {
    el('dvWacc').value = '2'; el('dvGT').value = '3';
    DCF.calc();
    assert.ok(/無法計算/.test(el('dvResult').children.find(c => c.className === 'dv-hint is-error').textContent));
    el('dvWacc').value = '9'; el('dvGT').value = '2';
  });

  await t('參考價上漲篩選：≥ 0 只留正值；清空後恢復', async () => {
    el('dvMinUpside').value = '0';
    DCF.applyVal();
    const rows = tables.dvTable.rows;
    assert.ok(rows.every(r => r.val_upside != null && r.val_upside >= 0));
    assert.ok(/參考價上漲 ≥ 0%/.test(el('dvCount').textContent));
    el('dvMinUpside').value = '';
    DCF.applyVal();
    assert.strictEqual(tables.dvTable.rows.length, 4);
  });

  await t('參數記憶：只記假設參數，不記個股資料', async () => {
    el('dvG').value = '12';
    DCF.calc();
    const saved = JSON.parse(store['mklab.screener.dcf.params']);
    assert.strictEqual(saved.g, 12);
    assert.ok(!('fcf' in saved) && !('shares' in saved));
  });

  await t('切換市場不覆蓋使用者的假設參數', async () => {
    el('dvG').value = '12';
    DCF.setMarket('us', {}); await tick(); await tick();
    assert.strictEqual(el('dvG').value, '12');
    assert.strictEqual(JSON.parse(store['mklab.screener.dcf.params']).g, 12);
    DCF.setMarket('tw', {}); await tick(); await tick();
  });

  await t('恢復預設參數會回到預設值並寫入記憶', async () => {
    el('dvG').value = '20';
    DCF.resetCalc();
    assert.strictEqual(el('dvG').value, '8');
    assert.strictEqual(JSON.parse(store['mklab.screener.dcf.params']).g, 8);
  });

  await t('美股：切換後 3 檔；NVDA 缺 FCF 提示自行輸入', async () => {
    DCF.setMarket('us', {}); await tick(); await tick();
    assert.strictEqual(tables.dvTable.rows.length, 3);
    DCF.selectStock('NVDA'); await tick();
    assert.strictEqual(el('dvFcf').value, '');
    assert.ok(/缺少自由現金流/.test(el('dvFcfHint').textContent));
  });

  await t('美股：shares 由市值/股價回推；FCF/淨負債留空由使用者輸入', async () => {
    DCF.selectStock('AAPL'); await tick();
    // shares = market_cap / price / 1e6 = 4978144444416 / 342.56 / 1e6 ≈ 14533.0 百萬股
    assert.ok(Math.abs(parseFloat(el('dvShares').value) - 14533.0) < 1, el('dvShares').value);
    assert.strictEqual(el('dvFcf').value, '');
    assert.ok(/缺少自由現金流/.test(el('dvFcfHint').textContent));
    assert.strictEqual(el('dvNetDebt').value, '');
  });

  await t('美股：選單(datalist)載入美股股票清單', async () => {
    const dl = el('dvList');
    const syms = dl.children.map(o => o.value);
    assert.deepStrictEqual(syms, ['AAPL', 'MSFT', 'NVDA'], JSON.stringify(syms));
  });

  await t('切換市場：單位與說明文字隨市場改變', async () => {
    DCF.setMarket('us', {}); await tick(); await tick();
    assert.strictEqual(el('dvFcfCur').textContent, 'US$');
    assert.strictEqual(el('dvNetDebtCur').textContent, 'US$');
    assert.ok(/美股/.test(el('dvIntro').textContent), el('dvIntro').textContent);
    DCF.setMarket('tw', {}); await tick(); await tick();
    assert.strictEqual(el('dvFcfCur').textContent, 'NT$');
    assert.ok(/台股/.test(el('dvIntro').textContent), el('dvIntro').textContent);
  });

  await t('匯出：估值表 CSV 註冊到設定抽屜，並輸出目前篩選結果', async () => {
    DCF.setMarket('us', {}); await tick(); await tick();
    assert.ok(registered['匯出 DCF 估值表 CSV（目前分頁）'], '未註冊匯出');
    DCF.applyVal();
    exportCalls.length = 0;
    registered['匯出 DCF 估值表 CSV（目前分頁）']();
    assert.strictEqual(exportCalls.length, 1);
    assert.strictEqual(exportCalls[0].rows.length, 3);
    assert.ok(exportCalls[0].cols.includes('val_ref') && exportCalls[0].cols.includes('val_note'));
    assert.ok(/^mklab-dcf-valuation-/.test(exportCalls[0].opts.filename));
  });

  await t('翻頁：精簡翻頁顯示「第 x / y 頁」，上一頁／下一頁依頁數停用', async () => {
    DCF.setMarket('tw', {}); await tick(); await tick();
    const pager = el('dvPager');
    assert.ok(/第 1 \/ 1 頁/.test(pager.children[1].textContent), pager.children[1].textContent);
    assert.ok(pager.children.length === 3, '應只有上一頁、頁次、下一頁三個元素');
    assert.strictEqual(pager.children[0].disabled, true);
  });

  await t('找不到代號時在標題顯示提示', async () => {
    DCF.selectStock('XXXX');
    assert.ok(/找不到/.test(el('dvName').textContent));
  });

  console.log(`\n合計 ${pass + fail} 項，PASS ${pass}，FAIL ${fail}`);
  if (fail) process.exit(1);
})();
