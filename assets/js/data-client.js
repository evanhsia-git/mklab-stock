/*
 * data-client.js — 統一資料層（零依賴、plain script IIFE）
 * 2026-07-18 重構：整合到新架構 assets/js/，支援 <base href="/mklab-stock/">
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

  // 快取（避免重複 fetch）
  const _cache = {};

  function _fetch(name) {
    if (_cache[name]) return Promise.resolve(_cache[name]);
    return fetch(BASE + name)
      .then(r => {
        if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + name);
        // 判斷 JSON vs JS（TWII_KDATA 是 JS 變數）
        if (name.endsWith('.js')) return r.text();
        return r.json();
      })
      .then(d => {
        // stocks.json 結構為 {meta: {...}, stocks: [...]} —— 回傳 stocks 陣列
        if (d && Array.isArray(d.stocks)) d = d.stocks;
        _cache[name] = d;
        return d;
      });
  }

  /** 讀 JSON 檔 */
  function json(name) {
    return _fetch(name.endsWith('.json') ? name : name + '.json');
  }

  /** 讀 JS 資料檔（如 twii_kdata.js → 解析出 TWII_KDATA 全域） */
  function jsData(name, globalKey) {
    return _fetch(name).then(text => {
      // 執行 JS 以定義全域（const 不掛 window，故用 new Function 取出）
      if (globalKey && !global[globalKey]) {
        try {
          new Function(text + '\n;return typeof ' + globalKey + '!=="undefined"?' + globalKey + ':null;')();
        } catch (e) {}
      }
      return global[globalKey] || null;
    });
  }

  /** 個股總表 stocks.json → 陣列（原始 d.stocks） */
  function stocks() {
    return json('stocks').then(arr => arr || []);
  }

  /** indices.json（大盤快照） */
  function indices() {
    return json('indices');
  }

  /** TWII K 線（260 天） */
  function twiiKline() {
    // twii_kdata.js 已掛 window.TWII_KDATA（fetch_data.py 產出保證）
    if (global.TWII_KDATA) return Promise.resolve(global.TWII_KDATA);
    return jsData('twii_kdata.js', 'TWII_KDATA');
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
  }

  global.MKLAB = global.MKLAB || {};
  global.MKLAB.data = {
    json,
    jsData,
    stocks,
    indices,
    twiiKline,
    freshness,
    clearCache,
    BASE,
  };

})(window);