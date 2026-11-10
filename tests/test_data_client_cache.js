// P0 效率修正迴歸測試：node tests/test_data_client_cache.js
//
// 鎖住 assets/js/data-client.js 的兩件事，避免下一次 ZIP 覆蓋時被改回去：
//   ① 進行中的請求要共用同一個 Promise（同一頁不可對同一個檔重複抓）
//   ② fetch 必須用 cache:'no-cache'（不可用 'no-store' 關掉瀏覽器快取）
//
// 做法：把 data-client.js 的原始碼用 new Function 載進沙箱，注入假的 window 與 fetch，
// 直接觀察 fetch 被呼叫幾次、帶了什麼參數。不改動任何頁面。
const fs = require('fs'), path = require('path'), assert = require('assert');

const SRC = fs.readFileSync(path.join(__dirname, '..', 'assets', 'js', 'data-client.js'), 'utf8');

/** 建立沙箱：回傳 { win, calls, setFetch } — calls 記錄每次 fetch 的 url 與 options */
function makeEnv(handler) {
  const calls = [];
  const win = {};
  let current = handler;
  const fetchStub = function (url, opts) {
    calls.push({ url, opts });
    return current(url, opts);
  };
  // jsData 內部用 new Function(text) 執行動態載入的 .js，那個函式活在「真正的全域」裡，
  // 看不到這裡的參數 window → 測試時要把假 window 掛上全域，否則掛全域的斷言會失敗。
  globalThis.window = win;
  new Function('window', 'fetch', 'console', SRC)(
    win, fetchStub, { warn() {}, log() {}, error() {} }
  );
  return {
    win, calls,
    setFetch(fn) { current = fn; },
  };
}

/** 標準的成功回應（body 可自訂） */
function ok(body) {
  return Promise.resolve({
    ok: true, status: 200,
    text: () => Promise.resolve(typeof body === 'string' ? body : JSON.stringify(body)),
  });
}

const results = [];
async function t(name, fn) {
  try { await fn(); results.push(['PASS', name]); }
  catch (e) { results.push(['FAIL', name + ' :: ' + (e && e.message ? e.message : e)]); }
}

(async () => {

  await t('併發呼叫同一個檔：只發出 1 次請求（原本會抓 3 次）', async () => {
    let release;
    const gate = new Promise(r => { release = r; });
    const env = makeEnv(() => gate.then(() => ok({ meta: {}, stocks: [] })));
    const p1 = env.win.MKLAB.data.json('stocks');
    const p2 = env.win.MKLAB.data.json('stocks');
    const p3 = env.win.MKLAB.data.stocks();
    assert.strictEqual(env.calls.length, 1, `在回應前就發了 ${env.calls.length} 次請求`);
    release();
    await Promise.all([p1, p2, p3]);
    assert.strictEqual(env.calls.length, 1, `總共發了 ${env.calls.length} 次請求`);
  });

  await t('併發呼叫拿到同一份資料（不是各拿到一份拷貝）', async () => {
    const env = makeEnv(() => ok({ meta: { as_of: '2026-11-06' }, stocks: [{ sym: '2330' }] }));
    const [a, b] = await Promise.all([env.win.MKLAB.data.json('stocks'), env.win.MKLAB.data.json('stocks')]);
    assert.strictEqual(a, b, '兩次呼叫不是同一個物件');
    assert.strictEqual(a.meta.as_of, '2026-11-06');
  });

  await t('fetch 必須用 cache:"no-cache"，不可用 "no-store"（關掉瀏覽器快取）', async () => {
    const env = makeEnv(() => ok({}));
    await env.win.MKLAB.data.json('indices');
    assert.strictEqual(env.calls.length, 1);
    const opts = env.calls[0].opts || {};
    assert.strictEqual(opts.cache, 'no-cache', `cache 目前是 ${JSON.stringify(opts.cache)}`);
    assert.notStrictEqual(opts.cache, 'no-store', 'no-store 會讓每次換頁都重下整個檔');
  });

  await t('路徑要用相對的 data/ 前綴（配合 <base href>，不可變絕對路徑）', async () => {
    const env = makeEnv(() => ok({}));
    await env.win.MKLAB.data.json('stocks');
    assert.strictEqual(env.calls[0].url, 'data/stocks.json', `實際 url=${env.calls[0].url}`);
    await env.win.MKLAB.data.json('history/20261106');
    assert.strictEqual(env.calls[1].url, 'data/history/20261106.json');
  });

  await t('已快取後再呼叫：不再發出請求', async () => {
    const env = makeEnv(() => ok({ meta: {}, stocks: [] }));
    await env.win.MKLAB.data.json('stocks');
    await env.win.MKLAB.data.json('stocks');
    await env.win.MKLAB.data.stocks();
    assert.strictEqual(env.calls.length, 1, `重複呼叫後累計 ${env.calls.length} 次請求`);
  });

  await t('失敗後 _inflight 要被清掉：隔一次呼叫要能重試成功（不可永久卡住）', async () => {
    let n = 0;
    const env = makeEnv(() => {
      n++;
      if (n === 1) return Promise.resolve({ ok: false, status: 500, text: () => Promise.resolve('') });
      return ok({ meta: {}, stocks: [{ sym: '2330' }] });
    });
    const d = await env.win.MKLAB.data.json('stocks');   // 內建重試會自己救回來
    assert.strictEqual(d.stocks.length, 1);
    assert.ok(env.calls.length >= 2, `重試沒有發生（只有 ${env.calls.length} 次請求）`);
    // 重試成功後應已進快取
    const before = env.calls.length;
    await env.win.MKLAB.data.json('stocks');
    assert.strictEqual(env.calls.length, before, '重試成功後沒有進快取');
  });

  await t('clearCache 之後會重新抓（除錯用行為不可壞掉）', async () => {
    const env = makeEnv(() => ok({ meta: {}, stocks: [{ sym: '2330' }] }));
    await env.win.MKLAB.data.json('stocks');
    env.win.MKLAB.data.clearCache();
    await env.win.MKLAB.data.json('stocks');
    assert.strictEqual(env.calls.length, 2, `clearCache 後只發了 ${env.calls.length} 次請求`);
  });

  await t('stocks.json 必須「原樣通過」：前端不得改寫 roe / roa / eps', async () => {
    // 這條是防止有人把 data-client.js 裡那段已移除的死碼（曾寫 if (name === 'stocks')）
    // 「修好」成 if (name === 'stocks.json') 而重新啟用——那會改掉 66 檔的 roa。
    // 財報欄位的官方值優先規則由管線擁有（import_official_fundamentals.py），前端只負責呈現。
    const rows0 = [
      { sym: '2330', roe: 31.7, roa: 20.1, eps: 40.0, roe_off: 39.77, roa_off: 27.3, eps_off: 98.66 },
      { sym: '6789', roe: 12.0, roa: 5.5, eps: 3.2, roe_off: 12.0, roa_off: 7.1, eps_off: 3.2 },
      { sym: '2882', roe: 11.54, roa: 0.75, eps: null, roe_off: null, roa_off: null, eps_off: null },
    ];
    const env = makeEnv(() => ok({ meta: {}, stocks: JSON.parse(JSON.stringify(rows0)) }));
    const rows = await env.win.MKLAB.data.stocks();
    assert.strictEqual(rows[0].roe, 31.7, '前端不可把 roe 換成 roe_off（管線已決定要顯示哪個）');
    assert.strictEqual(rows[1].roa, 5.5, '前端不可把 roa 換成 roa_off（實測有 66 檔兩者不同）');
    assert.strictEqual(rows[0].eps, 40.0, '前端不可改寫 eps');
    assert.strictEqual(rows[2].roe, 11.54, '前端不可清掉 roe');
    assert.deepStrictEqual(rows, rows0, 'stocks 陣列被前端改寫了');
  });

  await t('jsData 讀 .js 檔要回原始文字、不當 JSON 解析', async () => {
    const env = makeEnv(() => ok('window.TWII_KDATA=[1,2,3];'));
    const s = await env.win.MKLAB.data.jsData('twii_kdata.js', 'TWII_KDATA');
    assert.strictEqual(env.calls[0].url, 'data/twii_kdata.js', `實際 url=${env.calls[0].url}`);
    assert.ok(env.win.TWII_KDATA !== undefined, 'jsData 應執行 .js 並掛上全域');
  });

  await t('historyOn 日期格式錯誤要 reject，不可偷偷發出請求', async () => {
    const env = makeEnv(() => ok({}));
    let rejected = false;
    await env.win.MKLAB.data.historyOn('2026-11-06').catch(() => { rejected = true; });
    assert.ok(rejected, '格式錯誤沒有 reject');
    assert.strictEqual(env.calls.length, 0, '格式錯誤仍然發出了請求');
  });

  const fail = results.filter(r => r[0] === 'FAIL');
  results.forEach(r => console.log(r[0], r[1]));
  console.log(`\n合計 ${results.length} 項，PASS ${results.length - fail.length}，FAIL ${fail.length}`);
  process.exit(fail.length ? 1 : 0);

})();
