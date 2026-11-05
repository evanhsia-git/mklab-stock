// Screener 欄位勾選器：從頁面抽出邏輯，用假 localStorage/document 驗證（不需要瀏覽器）
const fs = require('fs'), path = require('path'), assert = require('assert');
const html = fs.readFileSync(path.join(__dirname, '..', 'mklab-stock-screener.html'), 'utf8');
const core = fs.readFileSync(path.join(__dirname, '..', 'assets', 'js', 'mklab-core.js'), 'utf8');
const s = html.indexOf('// ===== 顯示欄位勾選器 ====='), e = html.indexOf('  let resTable=null;');
assert(s > 0 && e > s, '找不到欄位勾選器區塊');
const results = [];
const t = (n, f) => { try { f(); results.push(['PASS', n]); } catch (x) { results.push(['FAIL', n + '：' + x.message]); } };
function load(stored) {
  const store = stored ? { 'mklab.screener.cols.v1': JSON.stringify(stored) } : {};
  const localStorage = { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = v; } };
  const api = new Function('localStorage', 'document', html.slice(s, e) +
    '\nreturn {visibleCols, colPickPreset: (k)=>{colSel = k===\'all\'?COL_ALL.slice():k===\'none\'?[]:COL_DEFAULT.slice();saveColSel();}, COL_ALL, COL_DEFAULT, setSel:(v)=>{colSel=v;saveColSel();}};')(localStorage, {});
  return { api, store };
}
t('預設：代號、名稱固定在前，且含 1/3/6月、1年漲跌幅', () => {
  const v = load().api.visibleCols();
  assert.deepStrictEqual(v.slice(0, 2), ['sym', 'name']);
  ['chg_1m', 'chg_3m', 'chg_6m', 'chg_1y'].forEach(c => assert(v.includes(c), c));
});
t('連續配息暫不開放：不在預設、不在可選清單，但欄位定義與資料欄位仍保留', () => {
  const { api } = load();
  assert(!api.visibleCols().includes('div_streak') && !api.COL_ALL.includes('div_streak'));
  assert(core.includes('div_streak: {') && html.includes('div_streak_years:s.div_streak_years'));
  assert(html.includes('const OPEN_DIV_STREAK = false;'));
});
t('2 年漲跌幅預寫但暫不開放：不在預設與可選清單，欄位定義、資料欄位與開關都在', () => {
  const { api } = load();
  assert(!api.visibleCols().includes('chg_2y') && !api.COL_ALL.includes('chg_2y'));
  assert(core.includes('chg_2y: {') && html.includes('chg_2y:s.chg_2y') && html.includes('const OPEN_CHG_2Y = false;'));
});
t('舊的 localStorage 即使含 div_streak 也會被濾掉（不會誤開）', () => {
  assert(!load(['price', 'div_streak']).api.visibleCols().includes('div_streak'));
});
t('勾選結果會存到 localStorage 並可還原；順序依固定欄序，不受勾選順序影響', () => {
  const { api, store } = load();
  api.setSel(['roe', 'price']);
  assert.deepStrictEqual(api.visibleCols(), ['sym', 'name', 'price', 'roe']);
  assert.deepStrictEqual(JSON.parse(store['mklab.screener.cols.v1']), ['roe', 'price']);
  assert.deepStrictEqual(load(JSON.parse(store['mklab.screener.cols.v1'])).api.visibleCols(), ['sym', 'name', 'price', 'roe']);
});
t('全不選只剩代號、名稱；全選涵蓋所有可選欄位', () => {
  const { api } = load();
  api.colPickPreset('none'); assert.deepStrictEqual(api.visibleCols(), ['sym', 'name']);
  api.colPickPreset('all'); assert.strictEqual(api.visibleCols().length, api.COL_ALL.length + 2);
});
t('所有可選欄位都在 COLUMNS 登錄（否則 DataTable 會拋錯）', () => {
  const api = load().api;
  api.COL_ALL.forEach(id => assert(new RegExp('\\n\\s+' + id + '\\s*:\\s*\\{').test(core), id + ' 未登錄'));
});
const fail = results.filter(r => r[0] === 'FAIL');
results.forEach(r => console.log(r[0], r[1]));
console.log(`\n合計 ${results.length} 項，PASS ${results.length - fail.length}，FAIL ${fail.length}`);
process.exit(fail.length ? 1 : 0);
