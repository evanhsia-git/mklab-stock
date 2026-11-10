/*
 * data-client.js — 統一資料層（零依賴、plain script IIFE）
 * 2026-07-18 重構：整合到新架構 assets/js/，支援 <base href="/mklab-stock/">
 * 2026-11-10 效率修正：① 進行中的請求共用 Promise（原本會被同一頁重複抓 3 次）
 *                     ② fetch 由 cache:'no-store' 改為 'no-cache'（改用 ETag 304 驗證）
 * 設計：集中讀取 data/*.json + 快取 + 新鮮度計算 + 錯誤處理
 * 用法：
 *   MKLAB.data.stocks().then(d => ...)
 *   MKLAB.data.indices().then(d => ...)
 *   MKLAB.data.twiiKline().then(d => ...)
 *   MKLAB.data.freshness('stocks.json')  // 回傳 {age, level, text}
 */
(function (global) {
  'use strict';

  // BASE 用相對路徑（配合 <base href="/mklab-stock/">），避免 GitHub Pages 子路徑下絕對路徑 /data/ 解析到根域而 404
  const BASE = 'data/';

  // 快取
  const _cache = {};     // name → 已解析完成的資料（避免重複 fetch）
  const _inflight = {};  // name → 進行中的 Promise（同一個檔被同時要多次時共用，不各抓一次）

  function _fetchOnce(name) {
    // cache: 'no-cache' 的語意是「每次都要跟伺服器確認，但內容沒變就不用重傳」。
    //
    // ⚠️ 不可改回 'no-store'：那等於完全關掉瀏覽器快取，每個頁面、每次換頁都把整個檔重下一次。
    //    實測 GitHub Pages 對 data/*.json 有給 ETag 與 Cache-Control: max-age=600，
    //    帶 If-None-Match 再抓會回 304（0 byte）；stocks.json 未壓縮 1.4 MB（傳輸約 248 KB），
    //    關掉快取等於每次換頁都白付這筆。
    // ⚠️ 也不可用預設的 'default'：max-age=600 會讓使用者在 10 分鐘內讀到舊檔，
    //    而本站很在意「資料以 X 收盤為準」的正確性 → 寧可多一次便宜的 304 驗證。
    return fetch(BASE + name, { cache: 'no-cache' })
      .then(r => {
        if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + name);
        return r.text().then(text => {
          // 判斷 JSON vs JS（TWII_KDATA 是 JS 變數），JS 檔直接回傳原始文字
          if (name.endsWith('.js')) return text;
          try {
            return JSON.parse(text);
          } catch (e) {
            // 常見成因：大檔案（如 stocks.json ~500KB+）在行動網路上傳輸到一半被截斷，
            // 收到的內容前段看起來完全正常、只是後面被切斷，所以只印前 120 字看不出問題；
            // 這裡改成把「收到的總長度」+「JSON.parse 實際錯誤訊息（含出錯位置）」都印出來，
            // 且在 Safari 上直接呼叫 r.json() 只會看到很難懂的
            // 「The string did not match the expected pattern」，看不出實際原因
            const err = new Error(
              name + ' 不是有效的 JSON（收到 ' + (text ? text.length : 0) + ' 字元）：' +
              (e && e.message ? e.message : e)
            );
            err.rawText = text;
            throw err;
          }
        });
      });
  }

  /** 單次載入 + 自動重試（重試不走 _inflight，避免自己等自己） */
  function _load(name, retries) {
    return _fetchOnce(name).catch(e => {
      // 自動重試：大檔案在行動網路上偶發性被截斷是常見狀況，通常重試就會自己好，
      // 不需要每次都要使用者手動重新整理頁面
      if (retries > 0) {
        console.warn('[data-client] ' + name + ' 讀取失敗，重試中…（剩餘 ' + retries + ' 次）', e && e.message);
        return new Promise(resolve => setTimeout(resolve, 400)).then(() => _load(name, retries - 1));
      }
      throw e;
    });
  }

  function _fetch(name) {
    if (_cache[name]) return Promise.resolve(_cache[name]);
    // 進行中的請求直接共用同一個 Promise。
    // 舊版只把「結果」放進快取（_cache[name] = d 寫在 .then 內），所以在檔案還沒下載完之前
    // 發出的第二、第三次呼叫，快取仍是空的 → 同一個檔被抓好幾次
    // （實測 screener.html 對 stocks.json 發了 3 次請求，每次 248 KB）。
    if (_inflight[name]) return _inflight[name];

    const p = _load(name, 2).then(d => {
      // stocks.json 原始結構含 {meta, stocks}，回傳原始物件供 caller 自行取用。
      // ⚠️ 不可在此拆解或改寫 stocks 陣列：meta 會遺失，而且會與後端不一致。
      //
      // roe / roa / eps 的「官方值優先」規則**由資料管線擁有**
      // （skills/data/import_official_fundamentals.py 第 327-333 行；只處理
      //  security_type==='stock'，並刻意保留 weekly-roe job 以 yfinance 補的值）。
      // 前端只負責原樣呈現。build_digest.py 的 effective_fundamentals() 亦是同一口徑。
      //
      // 歷史陷阱（2026-11-10 查證後移除）：此處原有 `if (name === 'stocks')` 的覆寫，
      // 但 json() 會先把 name 補成 'stocks.json'，所以那個條件**永遠不成立**（死碼、從未生效）。
      // 經實測**不可**直接改成 'stocks.json' 啟用它：roa 有 66 列與 roa_off 不同
      // （weekly-roe job 以 yfinance 覆寫部分列的 roe/roa），接上會改變那 66 檔的顯示值——
      // 那是行為變更，不是修 bug。要做的話必須先與管線端對齊口徑。
      // 回歸測試：tests/test_data_client_cache.js（鎖住「原樣通過、不改寫財報欄位」）。
      _cache[name] = d;
      return d;
    });

    // 成功或失敗都要清掉 _inflight：否則一次失敗會讓這個檔永久卡在「已拒絕的 Promise」上，
    // 之後再呼叫也不會重試。
    _inflight[name] = p;
    p.then(() => { delete _inflight[name]; }, () => { delete _inflight[name]; });
    return p;
  }

  /** 讀 JSON 檔 */
  function json(name) {
    return _fetch(name.endsWith('.json') ? name : name + '.json');
  }

  /** 讀 JS 資料檔（如 twii_kdata.js → 解析出 TWII_KDATA 全域） */
  function jsData(name, globalKey) {
    return _fetch(name).then(text => {
      if (globalKey && !global[globalKey]) {
        try {
          // 執行 JS：twii_kdata.js 末尾有 window.TWII_KDATA=TWII_KDATA，故執行後 global 可取到
          new Function(text)();
        } catch (e) {
          console.warn('[data-client] jsData eval failed:', e);
        }
      }
      return global[globalKey] || null;
    });
  }

  /** 個股總表 stocks.json → 陣列（d.stocks） */
  function stocks() {
    return json('stocks').then(d => (d && Array.isArray(d.stocks)) ? d.stocks : []);
  }

  /** 讀取 indices.json（大盤、ETF、巨集指標） */
  function indices() {
    return json('indices');
  }

  /** 讀取巨集指標 */
  function macro() {
    return json('indices').then(d => d && d.macro ? d.macro : {});
  }

  /** TWII K 線（260 天） */
  function twiiKline() {
    // twii_kdata.js 已掛 window.TWII_KDATA（fetch_data.py 產出保證）
    if (global.TWII_KDATA) return Promise.resolve(global.TWII_KDATA);
    return jsData('twii_kdata.js', 'TWII_KDATA');
  }

  /**
   * 指定日期的全市場收盤快照（data/history/{YYYYMMDD}.json，單檔含全部 1370+ 檔股票，~289KB）
   * ⚠️ 僅在使用者主動觸發（如回測試算）時呼叫，不要在頁面載入時預先抓，避免不必要流量
   * dateStr 格式：'20260716'（8 碼，無分隔符）
   */
  function historyOn(dateStr) {
    if (!/^\d{8}$/.test(String(dateStr || ''))) return Promise.reject(new Error('historyOn: dateStr 需為 YYYYMMDD 格式'));
    return json('history/' + dateStr).then(d => (d && Array.isArray(d.stocks)) ? d.stocks : []);
  }

  /** 新鮮度計算：比對檔案 mtime 與現在 */
  function freshness(fileName) {
    // 靜態託管無 mtime API，改用「交易日歷」估算：
    // data/*.json 每日台灣收盤後由 Actions 更新 → 超過 2 日曆日視為過期
    // 這裡回傳提示文字，實際日期由呼叫方傳入 lastUpdate
    return {
      level: 'unknown',
      text: '資料每日收盤後更新',
    };
  }

  /** 清除快取（除錯用） */
  function clearCache() {
    for (const k in _cache) delete _cache[k];
    for (const k in _inflight) delete _inflight[k];
  }

  global.MKLAB = global.MKLAB || {};
  global.MKLAB.data = {
    json,
    jsData,
    stocks,
    indices,
    twiiKline,
    historyOn,
    freshness,
    clearCache,
    BASE,
  };

})(typeof window !== 'undefined' ? window : globalThis);
