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
> 6. 資料源調查與 ROE/ROA 解決方案

---

## 0. 最高原則（不可違背）

| 原則 | 說明 |
|------|------|
| **GitHub-Native / Fork-First** | 零外部依賴、零 secret，fork 即跑 |
| **資料源優先順序** | TWSE / TPEX 官方為主 → 抓不到才用 FinMind → 再 yfinance |
| **Build-Time 預算** | 資料在 build 時生成進 repo，前端不即時打 API |
| **Graceful Degradation** | 單檔失敗不中斷整批，缺值給 `null`（前端顯示 `-`） |
| **上傳前先核對** | schema / 命名 / 法規類易錯項，先確認來源與格式再 commit |

---

## 1. 資料管線與腳本職責

```
┌─────────────────────────────────────────────────────────────┐
│  本機 VPS (DB 源頭)                                          │
│  /root/Documents/database/tw_stock_all.db                    │
│    └─ stock_overview (roe/eps/market_cap/industry/roa)       │
│    └─ daily_prices_YYYYMMDD (OHLCV+pe/pb/div)                │
│         │                                                    │
│         ▼ skills/data/export_db.py (一次性灌種)                  │
│    data/stocks.json / industry.json / history/*.json         │
└─────────────────────────────────────────────────────────────┘
                         │ git push
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  GitHub repo: evanhsia-git/mklab-stock (main)               │
│  .github/workflows/daily-update.yml (台灣 17:00=UTC 09:00)   │
│         │                                                    │
│         ▼ skills/data/fetch_data.py daily / weekly              │
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
- ⚠️ **已知限制（已解決）**：本機 DB 的 `stock_overview` 原無 `roa` 欄位，已由 `scripts/update_overview.py` 補齊（見 §7）

### 1.3 `scripts/update_overview.py`（ROE/ROA 補齊，新增）
**職責**：本機 DB 補齊財務衍生欄位 roe/roa，寫回 `tw_stock_all.db`。
- **優先順序**：FinMind（主源，台灣證交所授權資料）→ yfinance（備援）→ TWSE/MOPS（預留擴充）
- 計算公式：`ROE = NetIncome/StockholdersEquity*100`；`ROA = NetIncome/TotalAssets*100`
- 寫入：`ALTER TABLE stock_overview ADD COLUMN roa`（若不存在）+ UPDATE roe/roa
- 用法：`python3 scripts/update_overview.py [--limit N] [--force]`
- 詳見 §7

### 1.4 `scripts/qa_gate.py`（489 行）
**職責**：CI 質量門禁（`.github/workflows/qa-gate.yml`）。
- 掃描 5 頁 HTML 靜態結構（head/body 完整性、JS 語法、表格殼）
- 輸出 `data/qa-report.md` + JSON
- 判定 `ALLOW DEPLOY` / `BLOCK DEPLOY`（任一 Critical 未過即 BLOCK）

### 1.5 `scripts/check_html_health.py`（166 行）
**職責**：本地 HTML 健康檢查（標籤配對、關鍵元素存在）。

### 1.6 維護協議
| 腳本 | 誰改 | 測試方式 |
|------|------|----------|
| fetch_data.py | 雲端管線變更需先本地 `python fetch_data.py daily` 實跑 | 看 `data/fetch-log.json` 輸出 |
| export_db.py | 本機 DB schema 變動才改 | `python export_db.py` 後 diff data/*.json |
| update_overview.py | ROE/ROA 來源變更才改 | `python update_overview.py --limit 3 --force` |
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
    "note": "收盤/漲跌每日更新；ROE/ROA 由 update_overview.py 補齊；ETF 含於上市清單"
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
      "roe": 38.89,             // 股東權益報酬率 %（update_overview.py 補）
      "roa": 12.5,              // 總資產報酬率 %（update_overview.py 補，原 DB 無此欄）
      "eps": 22.08,
      "market_cap": 5812345000000,  // 市值（元）
      "ind": "半導體業",         // 33 類產業名
      "chg": -1.35,             // 漲跌 %（與前一日比）
      "rank": 79.0              // 綜合評分（簡易：roe*1.5+div*3）
    }
  ]
}
```

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
  cols: ['sym','price','chg','score','pe','pb','eps','roe','roa','trend','ind'],
  rows: [...],
  pageSize: 10,           // 每頁上限（用戶規格：最多 10）
  pagerId: 'indPager',    // 分頁容器 id（對應 HTML <div class="pager" id="...">）
  defaultSort: 'score',
})
```
- **COLUMNS 定義**（格式化契約）：
  - `sym` → `代號<small>名稱</small>`（代號緊接名稱，再價格）
  - `pe/pb/eps/roe/roa` → `.toFixed(2)`（用戶規格：最多 2 位小數）
  - `cap` → `market_cap/1e8` 轉億 + `.toFixed(2)`
  - `chg` → 漲跌 %（紅綠著色）
- **事件委派**：document-level delegate（修復排序點擊失效）
- **industry 明細表**：已改用此共用模組（原手工 innerHTML 導致 pb 超過 2 位，見 §4.7）

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
- 卡片名稱顯示：`代號<small>名稱</small>`（與表格統一，見 §3.1）

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

### 4.4 ROA 欄位無資料（已解決）
- **症狀**：ROA 顯示 `-` 或全部隱藏
- **根因**：本機 DB `stock_overview` 原無 `roa` 欄位；雲端 weekly 未完整跑
- **解決**：新增 `scripts/update_overview.py`（FinMind 主源 + yfinance 備援），`ALTER TABLE stock_overview ADD COLUMN roa` 並寫入；跑完 `export_db.py` 匯出即反映

### 4.5 自選卡片圖表缺失（已修復）
- **症狀**：AAPL/00700.HK/600519 無 sparkline
- **根因**：跨市場標的不在 stocks.json（僅台股）
- **修復**：`DEFAULT_WATCH` 改台股市值前 5

### 4.6 深色主題切換鍵無反應（已修復）
- **症狀**：設定抽屜的深色開關點了沒反應（頁面不切換淺色）
- **根因**：誤將呼叫改成 `MKLAB.Shell.toggleDark()`，但 `toggleDark` 定義在 `Drawer` 物件（core.js），`MKLAB.Shell.toggleDark` 為 `undefined` → onclick 報錯
- **修復**：恢復為 `MKLAB.Drawer.toggleDark()`（設定抽屜開關 + 工具列主題鍵皆改回 Drawer 命名空間）
- **教訓**：改 core.js 方法呼叫前，先用 console 確認 `typeof MKLAB.X.method === 'function'`，勿憑記憶猜命名空間

### 4.7 industry 成分股明細表 pb 超過 2 位小數（已修復）
- **症狀**：點產業展開明細表，PB 顯示 3+ 位（如 5.2345）
- **根因**：`selInd()` 手工 `innerHTML` 寫表格，pb 未做 `.toFixed(2)`
- **修復**：明細表改用共用 `MKLAB.DataTable`（cols: `['sym','price','chg','pe','pb','roe']`），pb 欄自動 2 位小數

### 4.8 表格代號/名稱分離（已修復）
- **症狀**：代號與名稱分兩欄，不符合「代號緊接名稱再價格」需求
- **根因**：`COLUMNS.sym` fmt 只顯代號；watchlist 還有獨立 `name` 欄
- **修復**：`sym` fmt 改 `代號<small>名稱</small>`（代號+名稱合一）；watchlist cols 移除獨立 name 欄

### 4.9 本機 DB 無 ROA 欄位（已修復腳本）
- **症狀**：`stock_overview` 無 `roa`，stocks.json 的 roa 全 null
- **根因**：原建庫腳本未抓 ROA；PRAGMA 證實無此欄
- **修復**：新增 `scripts/update_overview.py`（FinMind 主源 + yfinance 備援），`ALTER TABLE stock_overview ADD COLUMN roa` 並寫入

### 4.10 ROE 來源不明（已釐清）
- **症狀**：DB 的 roe（2330=38.89）與 yfinance 算的（31.7）不一致，不知來源
- **根因**：DB roe 是「歷史建庫腳本」用 `淨利/權益` 算式寫入的（非 TWSE API 直給、非 yfinance）；TWSE OpenAPI 本身不提供 ROE
- **解決**：統一改用 `update_overview.py`（FinMind 主源）重新計算並寫回，來源記錄於腳本 header
- 詳見 §7 資料源調查

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

## 7. 資料源調查與 ROE/ROA 解決方案

### 7.1 現狀調查（2026-07-15 實測）
| 資料源 | 台股 ROE/ROA 可用性 | 測試結果 |
|--------|---------------------|----------|
| **TWSE OpenAPI** (`openapi.twse.com.tw/v1/company/BalanceSheet`) | 財報端點 | ❌ 本環境直接呼叫回傳空（端點格式/權限問題） |
| **MOPS 公開觀測站** (`mops.twse.com.tw/mops/web/t146sb05`) | 財報 | ❌ 回傳 JS redirect（需 session/cookie，複雜） |
| **FinMind** (`FinMind.data.DataLoader`) | 資產負債表/財務報表 | ❌ **當前不可用**：匿名模式被 IP rate-limit（每 3-4 檔即 `Requests reach the upper limit`）；環境變數 `FINMIND_TOKEN` 經測試回傳 `Token is illegal`（過期）。FinMind 程式碼可呼叫，但本環境帳號層級被鎖 |
| **yfinance** (`yfinance.Ticker('2330.TW')`) | balance_sheet/income_stmt | ✅ **唯一可用**：每檔 ~3s（含 sleep），1369 檔全量 ≈ 70 分鐘；給「年度」財報（非季度）。ETF 無財報（回空） |

> ⚠️ **FinMind 標記更正**：先前標註「✅ 可用（匿名登入）」為**錯誤**。實測匿名模式被 IP 級 rate-limit，必須有有效 `FINMIND_TOKEN` 才能穩定使用（目前 token 已過期）。

### 7.5 抓取上限實測（2026-07-15）
| 項目 | 實測值 |
|------|--------|
| FinMind 匿名模式 | 每 3-4 檔觸發 `Requests reach the upper limit`（IP 級，90s+15s 間隔仍鎖） |
| FinMind token | 環境變數 `FINMIND_TOKEN` 回 `Token is illegal`（過期無效） |
| yfinance 單檔耗時 | ~3s（含 `time.sleep(3)` 防 ban） |
| yfinance 全量 1369 檔 | ≈ 70 分鐘（但 ETF 約 117 檔無財報，實際有效約 1252 檔 ≈ 63 分鐘） |
| yfinance 資料性質 | 年度財報（非季度）；ROE/ROA 為最近一年度值 |
| DB 現狀（補齊前） | roe 有值 1042/1486（缺 444）、roa 有值 0/1486（全缺） |

### 7.6 分批補齊策略（慢慢補足）
- **現有腳本**：`scripts/update_overview.py --skip-finmind`（純 yfinance，跳過被鎖的 FinMind）
- **跳過邏輯**：`--skip-finmind` 直接不呼叫 FinMind；未加此參數時，FinMind 連續失敗 3 次自動停用（避免每檔浪費 ~1s 在 limit 錯誤）
- **全量一次跑**：`python3 scripts/update_overview.py --skip-finmind`（背景跑 ~70min，補滿 roe 剩 444 + roa 全 1486）
- **未來 FinMind 解鎖後**：去掉 `--skip-finmind` 重跑（FinMind 主源覆蓋 yfinance 年度值，改抓季度更精準）
### 7.6 分批補齊策略（cron 友善）
- **改善版腳本**（2026-07-15 重寫）支援 cron 自動化：
  - `--cron`：增量模式，只補「roe 或 roa 為 null」的檔，跑完即退（適合排程）
  - `--daily-limit N`：每日限量分批（避免 yfinance 被 ban）
  - `--skip-etf`（預設開啟）：自動排除 ETF（含字母尾碼/末碼 T/B/D），因 yfinance 無 ETF 財報
  - `--skip-finmind`：跳過被鎖的 FinMind，純 yfinance
  - 輸出 JSON log + exit code（0=成功, 1=有失敗）
- **全量一次補完**：`python3 scripts/update_overview.py --skip-finmind`（背景跑 ~60min）
- **未來 FinMind 解鎖後**：去掉 `--skip-finmind` 重跑（FinMind 主源，季度更精準）

### 7.8 mklab-stock 能否「自動抓取 roa」？
**分兩層（2026-07-15 釐清）：**
| 層級 | 能否自動抓 roa | 機制 |
|------|---------------|------|
| **雲端 GitHub Pages（stocks.json）** | ✅ 已會 | `daily-update.yml` 的 `weekly-roe` job：**每週六 18:00 台灣時間**自動跑 `fetch_data.py weekly`，yfinance 補 ROE/ROA |
| **本機 DB（tw_stock_all.db）** | ✅ 可設（原為手動） | 改善版 `update_overview.py` 支援 `--cron` 增量模式，設系統 crontab / Hermes cron 即可自動補 |

**本機自動化設定（推薦）**：
```bash
# 每週六 03:00 跑（與雲端 weekly-roe 同頻率，避免重複打 yfinance）
0 3 * * 6 cd /root/Documents/mklab-stock && python3 scripts/update_overview.py --cron --skip-finmind >> /var/log/mklab_roa.log 2>&1
```
- `--cron` 增量：只補缺失檔，平時幾秒跑完；若某次補齊後有新上市股，下次自動補
- 若 FinMind 未來有有效 token：去掉 `--skip-finmind`（FinMind 主源，季度更精準）

**關鍵認知**：
- ROE/ROA 是**季度/年度**資料（非每日變動），「每日抓」意義不大 → 每週六補一次即可
- 真正的「每日」資料是收盤價/漲跌（已由 `daily` 模式處理）


| # | 問題 | 根因 | 解決 |
|---|------|------|------|
| 1 | `update_overview.py` 的 `--skip-finmind` 無效 | patch 被中斷，main() 殘留重複舊迴圈（無 skip 判斷） | 重寫 main()，移除重複迴圈，skip 參數生效 |
| 2 | FinMind 每檔先試都 limit，全量跑極慢 | 匿名模式被 IP rate-limit（每 3-4 檔鎖） | `--skip-finmind` 直接跳過；或未加參數時連續失敗 3 次自動停用 |
| 3 | yfinance 對 ETF 無財報（回空） | ETF 不發行資產負債表 | 自動跳過（roe/roa 保持 null），前端顯示 `-`，正常 |
| 4 | `FINMIND_TOKEN` 環境變數過期 | token 回 `Token is illegal` | 標記 Wiki；暫用 yfinance 備援，待有效 token |
| 5 | Wiki §7.1 錯標 FinMind「✅ 可用」 | 早期測試單檔成功，未測批量 limit | 修正為「❌ 當前不可用」+ 新增 §7.5 抓取上限實測 |

### 7.2 計算公式（計算式解決方案）
```
ROE (%) = NetIncome / StockholdersEquity * 100
ROA (%) = NetIncome / TotalAssets        * 100
```
- FinMind 財報為「單季」資料 → 若需年度 ROE/ROA 應取 TTM（近四季加總淨利）或年度財報（腳本預設取最新一季，未來可加 `--annual`）

### 7.3 解決腳本：`scripts/update_overview.py`
- **優先順序**：FinMind（主源，台灣證交所授權資料）→ yfinance（備援）→ TWSE/MOPS（預留擴充）
- **寫入**：`tw_stock_all.db` 的 `stock_overview` 表（ADD COLUMN roe/roa 若不存在）
- **用法**：
  ```bash
  python3 scripts/update_overview.py            # 全量（1369 檔，慢）
  python3 scripts/update_overview.py --limit 20 # 測試前 20 檔
  python3 scripts/update_overview.py --force    # 強制覆寫既有
  ```
- **後續**：跑完需 `python3 scripts/export_db.py` 匯出 stocks.json 才反映前端
- **來源記錄**：腳本 header 明載優先順序與公式（符合用戶「記錄在腳本裡」要求）

### 7.4 股市資料儲存位置（完整鏈）
```
本機 VPS: /root/Documents/database/tw_stock_all.db
  ├─ stock_overview    (roe/eps/market_cap/industry/roa)
  └─ daily_prices_YYYYMMDD (OHLCV + pe/pb/div)
        │ export_db.py
        ▼
mklab-stock/data/stocks.json  (推上 GitHub → GitHub Pages)
        │ fetch_data.py (雲端每日 TWSE + 每週 yfinance roe/roa)
        ▼
GitHub Pages: https://evanhsia-git.github.io/mklab-stock/
```
- **前端只讀 `data/*.json`**（Static-First，不直連 DB/API）
- **本機 DB 是 Build-Time 源頭**；雲端 GitHub Actions 是每日增量源頭

---

*最後更新：2026-07-15 — 新增 §1.3 update_overview.py、§4.6-4.10 故障排除、§7 資料源調查與 ROE/ROA 解決方案、§2.1 roa 欄位說明*
