---
title: mklab-stock 規範與架構手冊 (mklab-stock-schema)
created: 2026-07-15
tags: [mklab-stock, schema, 規範, 運維, 文檔]
---

# mklab-stock 規範與架構手冊

> 本文檔為 mklab-stock 專案的**權威規範手冊**，涵蓋：
> 1. 資料管線與腳本職責（由誰抓取、來源優先順序）
> 2. `data/` JSON Schema 完整定義
> 3. 前端資產（`assets/mklab-core.js`）元件契約
> 4. 已記錄的故障排除（Troubleshooting）
> 5. 維護協議（誰可以改什麼、如何上線）

---

## 0. 最高原則（不可違背）

| 原則 | 說明 |
|------|------|
| **GitHub-Native / Fork-First** | 零外部依賴、零 secret，fork 即跑 |
| **資料源優先順序** | TWSE / TPEX 官方為主 → 抓不到才用 yfinance |
| **Build-Time 預算** | 資料在 build 時生成進 repo，前端不即時打 API |
| **Graceful Degradation** | 單檔失敗不中斷整批，缺值給 `null`（前端顯示 `-`） |
| **上傳前先核對** | schema / 命名 / 法規類易錯項，先確認來源與格式再 commit |

---

## 1. 資料管線與腳本職責

```
┌─────────────────────────────────────────────────────────────┐
│  本機 VPS (DB 源頭)                                          │
│  /root/Documents/database/tw_stock_all.db                    │
│    └─ stock_overview (roe/eps/market_cap/industry...)        │
│    └─ daily_prices_YYYYMMDD (OHLCV+pe/pb/div)                │
│         │                                                    │
│         ▼ scripts/export_db.py (一次性灌種)                  │
│    data/stocks.json / industry.json / history/*.json         │
└─────────────────────────────────────────────────────────────┘
                         │ git push
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  GitHub repo: evanhsia-git/mklab-stock (main)               │
│  .github/workflows/daily-update.yml (台灣 17:00=UTC 09:00)   │
│         │                                                    │
│         ▼ scripts/fetch_data.py daily / weekly              │
│    data/stocks.json (每日 TWSE 收盤) + indices.json (yf)     │
│         │                                                    │
│         ▼ GitHub Pages                                       │
│    https://evanhsia-git.github.io/mklab-stock/               │
└─────────────────────────────────────────────────────────────┘
```

### 1.1 `scripts/fetch_data.py`（雲端每日抓取，493 行）
**職責**：GitHub Actions 執行，免 key，產出與 `export_db.py` 一致 schema。
- **`daily` 模式**（每日 ~1min）：TWSE `STOCK_DAY_ALL`（收盤+漲跌）+ `BWIBBU_ALL`（PE/PB/殖利率）
- **`weekly` 模式**（每週六，~70min）：yfinance 補 ROE/ROA（每檔 `sleep 3s` 防 IP ban）
- **`indices` 模式**：yfinance 抓全球指數/ETF 收盤（見 §2.4）
- 來源標註：`meta.source` 會寫明 `TWSE OpenAPI` 或 `yfinance`
- 關鍵函式：`fetch_twse_json()` / `fetch_yfinance_roe()` / `load_existing()`（保留 weekly 欄位不被 daily 覆寫）

### 1.2 `scripts/export_db.py`（本機灌種，301 行）
**職責**：從本機 SQLite `tw_stock_all.db` 匯出統一 schema JSON。
- `load_overview()`：讀 `stock_overview` → 疊加 roe/eps/market_cap/industry
- `export_latest()`：找最新 `daily_prices_YYYYMMDD` 表 → 產 `stocks.json`
- `export_industry()`：33 產業聚合（依 `industry-codes.json` 官方 33 類）
- `export_history()`：259 天切片 → `history/YYYYMMDD.json`
- ⚠️ **已知限制**：本機 DB 的 `stock_overview` **無 `roa` 欄位**（經 PRAGMA 證實），故匯出 stocks.json 的 `roa` 為 `null`。ROA 目前只靠雲端 `weekly` 模式補。

### 1.3 `scripts/qa_gate.py`（489 行）
**職責**：CI 質量門禁（`.github/workflows/qa-gate.yml`）。
- 掃描 5 頁 HTML 靜態結構（head/body 完整性、JS 語法、表格殼）
- 輸出 `data/qa-report.md` + JSON
- 判定 `ALLOW DEPLOY` / `BLOCK DEPLOY`（任一 Critical 未過即 BLOCK）

### 1.4 `scripts/check_html_health.py`（166 行）
**職責**：本地 HTML 健康檢查（標籤配對、關鍵元素存在）。

### 1.5 維護協議
| 腳本 | 誰改 | 測試方式 |
|------|------|----------|
| fetch_data.py | 雲端管線變更需先本地 `python fetch_data.py daily` 實跑 | 看 `data/fetch-log.json` 輸出 |
| export_db.py | 本機 DB schema 變動才改 | `python export_db.py` 後 diff data/*.json |
| qa_gate.py | 僅當檢查規則需調整 | `python qa_gate.py --json qa-result.json` |
| mklab-core.js | 前端共用元件變更 | 本地 server + 瀏覽器實測（截圖+console） |

---

## 2. `data/` JSON Schema 定義

### 2.1 `data/stocks.json`（全市場個股最新一日）
```json
{
  "meta": {
    "as_of": "2026-07-14",
    "source": "TWSE OpenAPI STOCK_DAY_ALL (免 key, 雲端)",
    "schema_version": "1.0.0",
    "count": 1369,
    "note": "收盤/漲跌每日更新；ROE/ROA 由 weekly 模式補齊；ETF 含於上市清單"
  },
  "stocks": [
    {
      "sym": "2330",            // 代號（數字開頭，≤6碼；ETF 可帶字母尾如 00400A）
      "name": "台積電",
      "price": 224.5,           // 收盤價
      "open": 225.0, "high": 228.0, "low": 222.0,
      "volume": 38291831.0,
      "pe": 18.5,               // 本益比（null=缺）
      "pb": 4.2,                // 淨值比
      "div": 2.1,               // 殖利率 %
      "roe": 38.89,             // 股東權益報酬率 %（weekly 補）
      "eps": 22.08,
      "market_cap": 5812345000000,  // 市值（元）
      "ind": "半導體業",         // 33 類產業名
      "chg": -1.35,             // 漲跌 %（與前一日比）
      "rank": 79.0              // 綜合評分（簡易：roe*1.5+div*3）
    }
  ]
}
```
⚠️ **roa 欄位現狀**：schema 預留但值為 `null`（DB 無來源 + weekly 未完整跑）。前端 index 頁已**暫隱藏 ROA 欄**直到有資料。

### 2.2 `data/industry.json`（33 產業聚合）
```json
{
  "meta": { "as_of": "20260713", "schema_version": "1.0.0", "count": 33,
            "source": "twse-33-industry(114.06.09)" },
  "industry": [
    { "nm": "半導體業", "chg": 1.2, "cnt": 158, "top": 5.4, "top_sym": "2330",
      "w1": 1.2, "m1": 3.4, "m3": 5.1, "m6": 8.7, "ytd": 12.3, "y1": 18.2, "y5": null }
  ]
}
```
- `w1/m1/m3/m6/ytd/y1/y5`：1週/1月/3月/6月/年初至今/1年/5年 區間報酬 %
- `top`/`top_sym`：該產業區間表現最佳個股

### 2.3 `data/history/YYYYMMDD.json`（每日切片，259 天）
```json
{
  "trade_date": "20260713",
  "schema_version": "1.0.0",
  "count": 1369,
  "stocks": [
    { "stock_id": "2330", "stock_name": "台積電", "close": 224.5,
      "open": 225.0, "high": 228.0, "low": 222.0, "volume": 38291831.0,
      "pe_ratio": 18.5, "pb_ratio": 4.2, "dividend_yield": 2.1,
      "industry": "半導體業" }
  ]
}
```

### 2.4 `data/indices.json` + `data/indices-config.json`（全球指數/ETF）
```json
// indices.json
{
  "meta": { "as_of": "2026-07-15", "source": "yfinance",
            "index_count": 15, "etf_count": 6 },
  "indices": [
    { "market": "TW", "name": "加權股價指數 (TAIEX)", "yf": "^TWII",
      "desc": "台灣大盤", "close": 45631.59, "prev_close": 45380.52,
      "chg_pct": 0.55, "as_of": "2026-07-15" }
  ]
}
```
- `indices-config.json`：靜態配置（市場/符號/資料源），`1306.T` 作為 TOPIX 代理（^TOPX 已移除）
- 覆蓋：TW/US/JP/KR/HK/CN + 歐洲（^FTSE/^GDAXI/^FCHI/^STOXX50E）

### 2.5 `data/markets.json` / `data/market.json`
- `markets.json`：多市場保留結構（US/CN/HK/JP/KR 元數據 + 共享欄位定義，無假股價）
- `market.json`：五國大盤概覽（首頁五卡）

### 2.6 `data/industry-codes.json`
- 臺證所 114.06.09 要點官方 33 產業代碼對照（`{"01":"水泥工業",...}` + `fallback`）

### 2.7 `data/schema-version.json`
```json
{ "schema_version": "1.0.0", "generated_at": "2026-07-15",
  "generator": "scripts/fetch_data.py (GitHub Actions, daily)" }
```

---

## 3. 前端資產契約（`assets/mklab-core.js`）

### 3.1 共用 DataTable 模組
```js
MKLAB.DataTable(tableId, {
  cols: ['sym','price','chg','score','pe','pb','eps','roe','trend','ind'],
  rows: [...],
  pageSize: 10,           // 每頁上限（用戶規格：最多 10）
  pagerId: 'indPager',    // 分頁容器 id（對應 HTML <div class="pager" id="...">)
  defaultSort: 'score',
})
```
- **COLUMNS 定義**（格式化契約）：
  - `pe/pb/eps/roe/roa` → `.toFixed(2)`（用戶規格：最多 2 位小數）
  - `cap` → `market_cap/1e8` 轉億 + `.toFixed(2)`
  - `chg` → 漲跌 %（紅綠著色）
- **事件委派**：document-level delegate（修復排序點擊失效）

### 3.2 頭部二元固定佈局（2026-07-15 規格）
```html
<nav id="mainNav" class="nav"></nav>              <!-- 第一列：Market|Screener|Research|Industry|Watchlist -->
<div id="utilbar" class="utilbar">                <!-- 第二列：sticky top:49px -->
  <span class="brand" id="brand"></span>          <!-- 左：mklab-stock -->
  <span class="spacer"></span>                    <!-- 撐開 -->
  <!-- Shell.mount 注入 .shell-tools（搜尋/主題/GitHub/設定）到右側 -->
</div>
```
- `.nav`：`position:sticky; top:0; z-index:26`
- `.utilbar`：`position:sticky; top:49px; z-index:25`
- `.shell-tools`：`display:flex; gap:8px`（修復工具列直向）

### 3.3 分頁鍵統一樣式（`.pager`）
```css
.pager { display:flex; gap:6px; justify-content:center; margin:12px 0; flex-wrap:wrap; }
.pager button { background:var(--surface); border:1px solid var(--border);
                color:var(--ink); border-radius:8px; padding:6px 11px; }
.pager button.on { background:var(--accent); color:#fff; }
```
⚠️ 禁止白底突兀——必須用 `--surface` 變數。

### 3.4 Watch 模組
- `DEFAULT_WATCH = ['2330','2454','2308','2317','3711']`（台股市值前 5，確保圖表有值）
- `renderWatch()`：若自選含無資料跨市場標的，自動以台股市值前 5 替換

---

## 4. 故障排除（Troubleshooting）

### 4.1 工具列按鈕變直向（已修復）
- **症狀**：搜尋/主題/GitHub/設定 垂直堆疊
- **根因**：`.shell-tools` 容器缺 flex CSS
- **修復**：`Shell.mount` 注入 `tools.style.cssText='display:flex;...'`

### 4.2 index 表格 PE/PB/EPS/ROE 全 `-`（已修復）
- **症狀**：表格有欄位但無數據
- **根因**：`loadStocks()` 用 `stocks.json` 完全覆寫 fallback，但 stocks.json 的財務欄位為 null
- **修復**：以 fallback 真實財務為 base，stocks.json 每日欄位（price/chg/ind）覆寫 + 過濾無財務標的

### 4.3 分頁鍵白底（已修復）
- **症狀**：共用表格分頁數字鍵為瀏覽器預設白底
- **根因**：index.html 缺 `.pager` CSS（其他頁有）
- **修復**：5 頁統一加 `.pager` CSS（surface 底 + accent 高亮）

### 4.4 ROA 欄位無資料
- **症狀**：ROA 顯示 `-` 或全部隱藏
- **根因**：本機 DB `stock_overview` 無 `roa` 欄位；雲端 weekly 未完整跑
- **暫時處理**：index 頁隱藏 ROA 欄
- **待辦**：修正本機 DB 抓取 ROA（用戶指示：TWSE/TPEX 為主，yfinance 為輔；需記錄來源於腳本）

### 4.5 自選卡片圖表缺失
- **症狀**：AAPL/00700.HK/600519 無 sparkline
- **根因**：跨市場標的不在 stocks.json（僅台股）
- **修復**：`DEFAULT_WATCH` 改台股市值前 5

---

## 5. 上線流程（SOP）

1. 本地修改 → `python scripts/qa_gate.py --json qa-result.json` 確認 `ALLOW DEPLOY`
2. 本地 server `python3 -m http.server 8765` + 瀏覽器實測（截圖 + console 無 error）
3. `git add -A && git commit -m "type: 描述"`（參考 Conventional Commits）
4. `git push origin master:main`
5. 等 CI（qa-gate + daily-update）綠燈 → GitHub Pages 自動部署
6. 線上驗證：https://evanhsia-git.github.io/mklab-stock/

⚠️ **gh token 限制**：當前 fine-grained PAT 缺 `Administration`（不能建 repo/開 Pages）與 `actions:write`（不能手動觸發 workflow）。如需此類操作請用戶手動在 GitHub UI 做，或 `gh auth refresh -s repo,workflow`。

---

## 6. 文件對應表（防止漂移）

| 文檔 | 職責 | 修改時機 |
|------|------|----------|
| `docs/design.md` | 架構規劃/設計依據（為什麼這樣設計） | 改設計決策時 |
| `docs/resource.md` | 資源清單/外部依賴 | 加依賴時 |
| `docs/SKILL.md` | 可上線 SKILL.md 執行規範 | 改執行流程時 |
| `handoff.md` | 跨 session 工作交接 | 每輪結束 |
| **本文件** | schema/腳本/故障排除權威規範 | 任何結構變更時同步更新 |

---

*最後更新：2026-07-15 — 新增 §1.5 維護協議、§4 故障排除、§2 schema 完整定義*
