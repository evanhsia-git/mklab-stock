# mklab-stock Handoff（2026-07-18 更新 — main 分支持續開發輪）

> 新 session 接手時：先讀此檔 + 執行導航（SCHEMA/policy/index/log）+ 讀 `docs/mklab-stock-dev.md`（完整開發指引）。
>
> **歷史脈絡**：7/15 的 `dev/web-components` 分支開發（Web Components 基礎 + `<mklab-kline>`）已完成並合併 main。7/16–7/18 在 **main 分支直接開發**（用戶指示「確認備份完成後接手」），已完成 Template 框架重構 + 元件化 + cap10 ETF 過濾修復。舊 handoff 的「待做 #7–#13」多數已完成，下方為真實現狀。

## 當前 Git 狀態（重要）
- **當前分支**：`main`（直接在此開發，非 dev 分支）
- **最新 commit**：`edf28e9` — fix(cap10): 補 is_etf 欄位到 stocks.json (242檔ETF) + 擴充前端ETF關鍵字
- **工作樹**：clean（無未提交變更）
- **備份分支**：`backup/static-2026-07-15`（靜態頁備份，仍保留）
- **線上**：https://evanhsia-git.github.io/mklab-stock/ （GitHub Pages，部署成功）

## 一、本輪已完成事項（7/16–7/18）

### ✅ 1. Template 框架重構（mklab-stock-webbase Skill）
- `templates/base.html`：頁面骨架，含 `{{META}} {{HEADER}} {{DRAWER}} {{CONTENT}} {{FOOTER}}` 佔位符 + `<base href="/mklab-stock/">`
- `templates/meta.html` / `header.html` / `drawer.html` / `footer.html`：拆分元件
- `pages/*.html`：7 個頁面內容片段（index / screener / research / industry / help / log / watchlist），已 de-shell（移除 `<html><head><body>`）
- `build/build_pages.py`：Template 組裝 + 自動注入 TITLE/DESCRIPTION
- `assets/css/` 拆分：`mklab-theme.css` / `layout.css` / `component.css` / `mobile.css`

### ✅ 2. Web Components 元件化（延續 7/15）
- `assets/js/mklab-wc.js`：
  - `<mklab-kline>` ✅（封裝 LightweightCharts v4.1.3）
  - `<mklab-datatable>` ✅（取代舊 `MKLAB.DataTable`，支援 `data-src="stocks"` / `cols` / `default-sort` / 分頁 / 排序）
  - 舊 `MKLAB.Shell` / `MKLAB.Drawer` 已改為 WC 標籤（`<mklab-drawer>` / `<mklab-router>` 標籤存在於頁面，但 `mklab-wc.js` 中 **MklabDrawer / MklabRouter class 尚未定義** — 見未完成 #2）
- `assets/js/data-client.js` ✅：統一資料層（IIFE，掛 `window.MKLAB.data`，含 `stocks()` / `indices()` / `twiiKline()` / `json()`）
- `assets/js/mklab-core.js`：核心 JS（Shell.mount / Drawer / 工具函式）

### ✅ 3. cap10 ETF 過濾修復（用戶回報「數據不對」）
**問題**：`台股市值前10大` 表格顯示 ETF（00400A、0050 等），非個股。
**根因**：`stocks.json` 中 ETF 與個股混排，且舊正則 `^00\d{3,5}[A-Z]{0,2}$` 過寬/過窄都漏抓。
**修復**（歷經 5 次迭代）：
1. `mklab-wc.js` `_sorted()`：先嘗試 sym 正則過濾 → 失敗（漏 0061/00636 等，誤殺個股）
2. 改用 **name 關鍵字** 判斷（`ETF|基金|指數|高息|優息|收益|台灣50|...`）
3. `fetch_data.py`：產資料時補 `is_etf` 欄位（長期修復）
4. `data/stocks.json`：直接補 `is_etf` 欄位（**242 檔 ETF 已標記**）
5. 擴充前端 `ETF_RE` 關鍵字涵蓋台股 ETF 命名（50/100/科技/型/元大/富邦/國泰等）
**結果**：台股市值前 10 大 = 2330台積電 / 2454聯發科 / 2308台達電 / 2317鴻海 / 3711日月光投控 / 2303聯電 / 2383台光電 / 2327國巨 / 2881富邦金 / 2408南亞科（或 2382廣達）✅
**市值單位**：`cap` 欄位 formatter 做 `market_cap / 1e8` → 顯示「億元」，個股 ETF 統一為億元級。

### ✅ 4. K線圖資料源修復
- `templates/base.html` 加入 `data/twii_kdata.js`（掛 `window.TWII_KDATA`）
- `mklab-kline` 讀 `window[sym+'_KDATA']` 全域變數

### ✅ 5. QA Gate 通過
- `scripts/qa_gate.py` + `scripts/check_html_health.py`：處理 Web Components 標籤（mklab-* 視為 VOID/自定義標籤）、`<code>/<pre>` 嵌套解析
- 最終：0 Critical, 0~2 Warnings（🟢 ALLOW DEPLOY）

## 二、未完成事項（待續）

| # | 項目 | 狀態 | 備註 |
|---|------|------|------|
| 1 | **Market Health K線圖空白** | 🔴 未解 | 線上快照顯示 `<mklab-kline>` 區塊空白。可能原因：`LightweightCharts` 未載入（base.html 未引 vendor）、或 `TWII_KDATA` 資料格式不對、或 canvas 高度 0。需瀏覽器實測 console 確認 |
| 2 | **MklabDrawer / MklabRouter class 未定義** | 🔴 未做 | 頁面用 `<mklab-drawer>` / `<mklab-router>` 標籤，但 `mklab-wc.js` 中無對應 class 註冊。目前靠舊 `mklab-core.js` 的 `MKLAB.Shell.mount()` 補位。應正式實作為 WC |
| 3 | **市場情緒與原物料全顯示 '—'** | 🟡 待資料源 | VIX / USD-TWD / 黃金 / 原油 WTI / 比特幣 全部無資料。`renderMacro()` 有呼叫但 `data/macro.json` 或 API 未提供。需接資料源或明確標示「暫不提供」 |
| 4 | **載入指示器隱藏時機** | 🟡 待確認 | `freshness` 元素預設顯示「資料載入中...」，應在資料載入完成後更新為日期或隱藏。用戶截圖曾看到停留狀態 |
| 5 | **SPA 路由（History API）** | ❌ 待做 | `<mklab-router>` 標籤存在但無實作。目前多頁獨立 HTML，非 SPA |
| 6 | **逐頁 WC 接入完整性** | 🟡 部分 | screener/research/industry/watchlist/help/log 已 de-shell 並接入 WC，但部分頁面功能（篩選邏輯、自選股 CRUD）可能仍依賴舊 `MKLAB.*` API，需逐一驗證 |
| 7 | **superpowers 完整驗證** | ❌ 待做 | verification-before-completion + qa_gate 應在每次大改後跑，目前僅手動瀏覽器實測 |

## 三、中斷接手部分（新 session 必讀）

### 🔴 當前中斷點
- **main 分支直接開發**（非 dev 分支）。工作樹 clean，最新 `edf28e9`。
- 下一個應做：**#1 Market Health K線圖空白排查**（用戶截圖回報的核心問題之一）

### ⚠️ 接手注意事項（踩坑記錄）
1. **ETF 過濾用 `is_etf` 欄位 + name 關鍵字雙重判斷**：`stocks.json` 已標記 242 檔 ETF。`mklab-wc.js` `_sorted()` 中 `cap10` 表格過濾邏輯：
   ```js
   const ETF_RE = /ETF|基金|指數|正[0-9]|反[0-9]|...|台灣50|中型100|科技|電子|...|元大|富邦|國泰|中信|統一|聯博|第一金|凱基/;
   const looksETF = (r) => r.is_etf || ETF_RE.test(String(r.name||''));
   rows = rows.filter(r => !looksETF(r));
   ```
   **勿改回 sym 正則**（已證明不可靠）。
2. **市值單位統一為億元**：`cap` 欄位 formatter `market_cap / 1e8`。個股 market_cap 是「元」（兆級），ETF 的也是「元」但數值小。過濾 ETF 後排序即正確。
3. **LightweightCharts v4.1.3**：全局變數 `LightweightCharts`。`<mklab-kline>` 需 `data/twii_kdata.js` 掛 `window.TWII_KDATA`。**base.html 已引該 JS，但 vendor/lightweight-charts 是否引入需確認**（K線空白可能根因）。
4. **Telegram 內建瀏覽器限制**：不支援 `position: sticky/fixed` 導覽列。用戶用手機 Telegram 開網頁會看不到 header/drawer。這是客戶端限制，非程式問題。建議用戶用 Chrome/Safari 開。
5. **Custom Element 時序**：呼叫元件方法須等 `customElements.whenDefined()`。snapshot 抓不到動態渲染內容（WC 非同步 fetch），驗證用 `browser_vision` 截圖或 console 取 shadowRoot。
6. **local server**：`python3 -m http.server 8765`（背景可能還在跑）。確認：`curl -s -o /dev/null -w "%{http_code}" http://localhost:8765/index.html`

### 📋 接手第一步建議
```bash
cd /root/Documents/mklab-stock
git branch --show-current          # 應為 main
git status --short                 # 應為 clean
# 排查 #1：瀏覽器開 https://evanhsia-git.github.io/mklab-stock/
#   console 查：window.LightweightCharts / window.TWII_KDATA / <mklab-kline> shadowRoot
# 若 LightweightCharts 為 undefined → 檢查 base.html 是否引 vendor/lightweight-charts.min.js
```

## 四、關鍵事實（防踩坑）
1. **圖表庫**：`vendor/lightweight-charts.min.js` = LightweightCharts v4.1.3（全局 `LightweightCharts`）。`<mklab-kline>` 封裝它。
2. **FinMind 不可用**：token 失效。TWII K線來源為 yfinance 或 TWSE。
3. **本機 DB 權威源**：`/root/Documents/database/tw_stock_all.db`
4. **零依賴原則**：Web Components 用 plain script + Custom Elements，不用 ES module（file:// 相容）。`mklab-wc.js` 是 IIFE + `customElements.define`。
5. **GitHub Pages subpath**：所有資源路徑相對 `/mklab-stock/`，`<base href="/mklab-stock/">` 已設。
6. **ETF 標記**：`stocks.json` 每筆含 `is_etf: bool`（242 檔 = true）。`fetch_data.py` 每次重產會自動標記（name 關鍵字）。
7. **數據更新**：CI `daily-update.yml` 跑 `fetch_data.py` 產 `data/stocks.json` + `history/`。push 前需 `git pull --no-rebase origin main -X ours` 避免並發衝突。

## 五、用戶回報問題追蹤（7/18）
| 用戶回報 | 狀態 | 處理 |
|---------|------|------|
| 台股市值前10大顯示 ETF，數據不對 | ✅ 已修 | 補 is_etf + name 關鍵字過濾 |
| 市值單位不統一（ETF億級/個股兆級混排） | ✅ 已修 | 過濾 ETF 後排序正確，cap 欄位統一 /1e8 顯示億元 |
| 全球主要股市卡片 | ✅ 正常 | 5 指數有資料 |
| Market Health K線圖空白 | 🔴 待查 | LightweightCharts 載入問題疑似 |
| 市場情緒/原物料全 '—' | 🟡 缺資料源 | 需接 API 或標示暫不提供 |
| 導覽列/抽屜在 Telegram 瀏覽器看不到 | ⚠️ 客戶端限制 | Telegram WebView 不支援 sticky |
| 載入指示器 '資料載入中...' 停留 | 🟡 待確認 | 應在載入完成後隱藏 |

## 六、用戶偏好/決策（本輪）
- 數據正確性 > 功能完整性。用戶對「數據不對」零容忍。
- 市值單位要統一（全億元或全兆元，不要混）。
- 直接用 main 分支開發（非 dev 分支），確認備份後接手。
- 手機 Telegram 為主要使用場景，但 Telegram WebView 限制需告知用戶。
