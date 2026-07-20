# mklab-stock

手機優先的台股 / 美股 / A股（滬深+港股）股市儀表板。靜態優先（Static-First）、Build-Time 預算、零密鑰（zero-secret）即可上線。

> 線上版：**https://evanhsia-git.github.io/mklab-stock/**

## 設計原則（架構憲法）

- **不問「能不能做」，只問「應不應該做」**——每個功能過 8 題閘門，≥2 否則延後/轉 Optional/刪除。
- **最容易維護 > Fork 即跑 > 易理解 > 長期發展**（非功能最多）。
- **靜態優先**：資料以 JSON 進 repo，不依賴外部 DB；衍生資料進 repo，原始日線留外部。
- **零密鑰**：所有已實作功能不含 API key / token / secret；需要授權的資料源走 Build-Time 預算或公開 API。
- **執行效率第一，好維護第二**：輕量庫、少外部依賴。
- **GitHub-Native / Fork-First**：任何人 fork 本倉庫即可獨立運作，不需申請任何 API key。

## 頁面（Domain）

| 頁面 | 檔名 | 說明 |
|------|------|------|
| Market（首頁） | `index.html` | 五國股市走勢卡 + 自選股 + 績效表現 + 「綜合評分 TOP 10」推薦清單 |
| Screener（篩選） | `mklab-stock-screener.html` | 多條件篩選（PE/PB/ROE/EPS/漲跌%）+ 策略模板（價值/品質/成長/動能/高股息） |
| Research（研究） | `mklab-stock-research.html` | 個股深度研究，含 K 線圖（LightweightCharts）、MACD / KD 指標與畫線工具 |
| Industry（產業） | `mklab-stock-industry.html` | 依臺證所 114.06.09 要點劃分的 33 個官方產業大類，查看各產業動態與成分股 |
| Watchlist（自選） | `mklab-stock-watchlist.html` | 在設定抽屜填入最多 5 檔代號，首頁與自選頁即顯示其走勢 |
| Help（說明） | `mklab-stock-help.html` | 功能說明、使用指南、資料來源、評分標準 |
| Log（開發日誌） | `mklab-stock-log.html` | 開發歷程記錄 |

## 使用說明

- **Market（首頁）**：大盤走勢、自選股、績效表現，以及「綜合評分 TOP 10」推薦清單。
- **Screener（篩選）**：依 PE / PB / ROE / EPS / 漲跌% 等條件過濾股票，內建價值 / 成長 / 動能 等策略模板。
- **Research（研究）**：個股深度研究，含 K 線圖、MACD / KD 指標與畫線工具。
- **Industry（產業）**：依臺證所 114.06.09 要點劃分的 33 個官方產業大類，查看各產業動態與成分股。
- **Watchlist（自選）**：在設定抽屜填入最多 5 檔代號，首頁與自選頁即顯示其走勢。

### 通用操作

- 點擊右上 🔍 可展開搜尋框，輸入代號（如 `2330`）搜尋。
- 點擊 🌓 主題 切換深色 / 淺色。
- 點擊 ⚙ 設定 開啟抽屜：設定自選股、主題、語言、查看系統狀態。
- 表格標題（代號 / 價格 / PE / ROE…）可**點擊排序**，再點一次切換升 / 降序。
- 所有表格每頁最多 10 筆，底部有分頁鍵（換頁）。

## 股市資料來源

| 資料類型 | 來源 | 說明 |
|----------|------|------|
| 每日收盤價 / 漲跌 | **TWSE OpenAPI** | 臺灣證交所公開 API（`STOCK_DAY_ALL`），免 key、雲端可達 |
| ROE / ROA | **FinMind** → yfinance | FinMind（台灣證交所授權資料）為主；雲端 weekly 用 yfinance 備援 |
| 產業分類 | **33 類對照表** | 依臺證所「上市公司產業類別劃分暨調整要點（114.06.09）」 |
| 歷史股價 | **本機 DB 灌種** | 初始 260 個交易日快照，後續由 GitHub Actions 每日追加 |

> **資料源優先順序**：FinMind（台灣證交所授權資料）→ TWSE OpenAPI → yfinance。**零 API key、零 secret**，fork 即可用。

## 資料更新

- **每日自動更新**：台灣收盤後 17:00（UTC 09:00）週一至週五，由 GitHub Actions 執行
- **ROE / ROA 更新**：每週六自動補齊（FinMind 為主，yfinance 備援）
- **全球指數/ETF 更新**：每個工作日 UTC 09:30（yfinance）
- **TWII K 線更新**：每個工作日 UTC 09:30（yfinance ^TWII，260 日窗口）
- **休市處理**：週末 / 國定假日 / 突發颱風假自動跳過
- 資料以收盤為準，非即時。首頁黃標顯示實際資料日。

## 目前資料庫數量

- 上市 / ETF 檔數：**1,370 檔**
- 歷史股價切片：**261 個交易日**
- 產業分類：**33 個官方大類**
- ROE/ROA 已涵蓋：**100%（由 update_overview.py 補齊）**

## 綜合評分計算標準

首頁「綜合評分 TOP 10」依下列加權即時計算（0–100 分），**只列出資料齊全且評分 > 0 的推薦股**：

| 指標 | 權重 | 計算方式 |
|------|------|----------|
| ROE（股東權益報酬率） | 最高 40 | `min(40, ROE × 1.2)`，越高越好 |
| PE（本益比） | 最高 20 | `min(20, (30 − PE) × 1.0)`，越低越好 |
| PB（價格淨值比） | 最高 15 | `min(15, (8 − PB) × 2.0)`，越低越好 |
| EPS（每股盈餘） | 最高 10 | `min(10, EPS × 0.3)`，越高越好 |
| 漲跌% | 最高 15 | `min(15, 漲跌% × 1.0)`，越高越好 |

> 任一欄位缺漏（null）則該股不列入推薦。評分僅供參考，**非投資建議**。

## 目錄結構

```text
mklab-stock/
├── templates/                    # 共用區塊（非整頁）
│   ├── base.html                 # 頁面骨架參考
│   ├── meta.html                 # title/description/viewport/favicon/Open Graph
│   ├── header.html               # Sticky Header（導覽列 + 工具列）
│   ├── drawer.html               # 設定抽屜（主題/語言/自選股/系統狀態）
│   └── footer.html               # 頁腳
├── index.html                    # 正式網站（唯一來源，含完整頁面內容）
├── mklab-stock-screener.html     # Screener 篩選
├── mklab-stock-research.html     # Research 研究
├── mklab-stock-industry.html     # Industry 產業
├── mklab-stock-watchlist.html    # Watchlist 自選
├── mklab-stock-help.html         # Help 說明
├── mklab-stock-log.html          # Log 開發日誌

├── build/                        # Template Synchronizer（僅同步共用區塊）
│   └── template_sync.py          # 同步 Header/Drawer/Footer/Meta 至根目錄 HTML
├── assets/                       # 靜態資源
│   ├── css/
│   │   ├── mklab-theme.css       # Design Tokens + 基礎 Reset（:root 變數）
│   │   ├── layout.css            # 版面配置
│   │   ├── component.css         # 元件樣式
│   │   └── mobile.css            # 響應式斷點
│   └── js/
│       ├── mklab-core.js         # 核心：Shell / Watch / Drawer / Utils
│       ├── data-client.js        # 統一資料層（IIFE, 快取, ETag, 新鮮度）
│       └── mklab-wc.js           # Web Components（kline/datatable/drawer/router）
├── data/                         # Build-Time 生成的 JSON（前端只讀這裡）
│   ├── stocks.json               # ★ 全市場個股最新一日（最完整，1370 檔全欄位，~353K）
│   ├── industry.json             # 33 產業聚合績效（~5K）
│   ├── indices.json              # 全球指數/ETF 收盤（15 指數+6 ETF，~5.4K）
│   ├── indices-config.json       # 指數/ETF 靜態配置（市場/符號/來源）
│   ├── industry-codes.json       # 臺證所 33 產業代碼對照表
│   ├── markets.json              # 多市場預留結構
│   ├── schema-version.json       # schema 版號
│   ├── etf-shares.json           # ETF 發行張數（估算 market_cap 用）
│   ├── twii_kdata.js             # 加權指數 K 線 (window.TWII_KDATA)
│   └── history/                  # 每日股價切片（261 個交易日，各 ~289K）
│       ├── 20250714.json         #   最早一日
│       ├── ...                   #   （每日一檔，含 OHLCV+PE/PB/DY）
│       └── 20260716.json         #   最新一日
├── docs/                         # 設計依據 / 資源 / 規範
│   ├── design.md
│   ├── resource.md
│   ├── SKILL.md
│   ├── DATA_FIELDS.md            # 資料欄位對照表
│   └── mklab-stock-schema.md     # 規範與架構手冊
├── skills/                       # Skills First — 每個 Skill 自包含
│   ├── README.md                 # 索引
│   ├── router.md                 # 路由決策
│   ├── qa-gate/                  # 品質門禁
│   │   ├── skill.md  qa_gate.py  validate_data.py  checklist.md  config.json
│   ├── html-health/              # HTML 結構健康
│   │   ├── skill.md  check_html_health.py  checklist.md  rules.json
│   ├── lint/                     # 程式碼/結構規範
│   │   ├── skill.md  lint.py  checklist.md  lint-rules.json
│   ├── design-system/           # UI/Theme 規範
│   │   ├── skill.md  ui-rules.md  theme.json
│   ├── data/                     # 資料抓取/匯出
│   │   ├── skill.md  fetch_data.py  update_overview.py  export_db.py  schema.md
│   ├── deployment/              # GitHub Pages 部署
│   │   ├── skill.md  deploy.py  github-pages.md
│   └── development/             # 開發輔助
│       ├── skill.md  coding-style.md  helper.py
├── build/                        # Template Synchronizer（僅同步共用區塊）
│   └── template_sync.py
├── .github/workflows/            # CI/CD
│   ├── daily-update.yml          # 每日收盤 + 每週六 ROE/ROA + 指數/ETF/K線
│   ├── qa-gate.yml               # 質量門禁
│   └── html-health.yml           # HTML 結構檢查
├── templates/                    # 共用區塊（非整頁）
│   ├── base.html  header.html  drawer.html  footer.html  meta.html
├── sandbox/                      # 實驗/原型（GrapesJS/Dashboard/UI）
├── vendor/                       # 第三方 JS（lightweight-charts.min.js）
├── index.html                    # 正式網站（唯一來源）
├── mklab-stock-screener.html     # Screener 篩選
├── mklab-stock-research.html     # Research 研究
├── mklab-stock-industry.html     # Industry 產業
├── mklab-stock-watchlist.html    # Watchlist 自選
├── mklab-stock-help.html         # Help 說明
├── mklab-stock-log.html          # Log 開發日誌
├── HANDOFF.md                    # 架構標準規範（MKLAB Framework v1.x）
└── README.md                     # 本檔案
```

> **資料源頭**：本機 `/root/Documents/database/tw_stock_all.db`（38MB SQLite）是權威來源；`skills/data/export_db.py` 將其匯出為上方 `data/*.json` 推上 GitHub Pages。雲端 `skills/data/fetch_data.py` 每日增量更新收盤價，每週六補 ROE/ROA。

## 核心架構特色

### Template-based 架構
- **單一來源**：根目錄 HTML 即正式網站；Header/Drawer/Footer/Meta 只維護一份 `templates/`
- **模板同步**：`build/template_sync.py` 將共用區塊同步進 7 個根目錄 HTML
- **零重複**：改一次 Template，全站 7 頁同步更新

### Web Components 元件化
| 元件 | 標籤 | 功能 |
|------|------|------|
| K 線圖 | `<mklab-kline>` | LightweightCharts 包裝，支援 data-symbol、height |
| 表格 | `<mklab-datatable>` | 排序/分頁/資料源自動載入 |
| 抽屜 | `<mklab-drawer>` | 設定面板（主題/語言/自選股/系統狀態） |
| 路由 | `<mklab-router>` | SPA 風格頁面切換（無重新整理） |

### 統一資料層
```javascript
MKLAB.data = {
  json(name)        // 通用 JSON 載入
  stocks()          // 股票總表 → 陣列（自動解包 d.stocks）
  indices()         // 大盤快照
  twiiKline()       // TWII 260 天 K 線
  freshness(file)   // 新鮮度提示文字
  clearCache()      // 清除快取（除錯用）
}
```
- **零依賴**：IIFE + plain script，支援 `file://` 直開
- **自動快取**：5 分鐘 TTL，同一請求去重
- **統一錯誤處理**：網路失敗時自動回退過期快取

### CSS 分層架構（4 檔）
| 檔案 | 職責 |
|------|------|
| `mklab-theme.css` | Design Tokens (`:root` 變數) + 基礎 Reset |
| `layout.css` | 版面配置：Grid/Flex/Card/Layout/Panel/Table 等 |
| `component.css` | 元件樣式：Card/Nav/Drawer/Footer/Btn/Badge/Alert/Form 等 |
| `mobile.css` | 響應式斷點/觸控目標/列印/減少動態/高對比度 |

### GrapesJS 視覺編輯器（官方）
- 僅作為開發階段編輯器，**正式網站不引用 GrapesJS Runtime**
- 編輯 → 匯出乾淨 HTML/CSS → 手動同步回 `templates/`、`assets/css/`
- 保證輸出可再次載入 GrapesJS 編輯，無 `data-gjs-*` 殘留

## 本地預覽與開發

```bash
# 1. 進入專案
cd mklab-stock

# 2. 同步共用區塊（Template Synchronizer）
python build/template_sync.py

# 3. 本地預覽
python -m http.server 8000
# 開瀏覽器 http://localhost:8000/index.html

# 4. 開發流程：編輯根目錄 HTML、templates/、assets/css/、assets/js/
#    → 重新同步 → 驗證 → Commit
```

### 使用 GrapesJS 編輯設計

```bash
# 1. 先 Build 產出完整 HTML
python build/build_pages.py

# 2. 用 GrapesJS 線上編輯器
#    開啟 https://grapesjs.com/demo.html → Import index.html
#    或使用本地整合 editor.html（見 docs/design.md）

# 3. 編輯視覺（版面/色彩/間距/排版/元件拖拉）
# 4. 匯出 HTML/CSS
# 5. 手動同步回專案：
#    - Header → templates/header.html
#    - Drawer → templates/drawer.html
#    - Footer → templates/footer.html
#    - 頁面內容 → mklab-stock-*.html（根目錄）
#    - CSS 變數/樣式 → assets/css/mklab-theme.css 等
# 6. 重新 Build 驗證
```

## 上線（GitHub Pages）

1. Fork 或 clone 本 repo
2. GitHub Pages 設定：Source → `main` branch / `/` (root)
3. Push 到 `main` 觸發 GitHub Actions 自動部署
4. 線上網址：https://evanhsia-git.github.io/mklab-stock/

## 品質門禁（QA Gate）

```bash
# 本地執行
python skills/qa-gate/qa_gate.py --json qa-result.json

# CI 自動執行：.github/workflows/qa-gate.yml
# 檢查項目：
# - Python 語法/匯入
# - 資料完整性/Schema/OHLC 合理性
# - HTML 結構健康（含 check_html_health.py）
# - CSS Theme 變數一致性
# - 禁止硬寫核心樣式
# - JavaScript 語法
# - 內部連結 HTTP 200
# - Chart/Visual（Manual）
```

**判定標準**：Critical ERROR = 0 才 `ALLOW DEPLOY`，否則 `BLOCK DEPLOY`

## 免責聲明

本網站所有資料與評分僅供研究與教育參考，不構成任何投資建議。使用者應自行判斷並承擔投資風險。

## License

MIT