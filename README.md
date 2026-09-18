# mklab-stock

手機優先的台股 / 美股 / 全球指數股市儀表板。靜態優先（Static-First）、Build-Time 預算、零密鑰（zero-secret）即可上線，`git clone` 或 fork 後即可獨立運作。

> 線上版：**https://evanhsia-git.github.io/mklab-stock/**

## 設計原則

- **靜態優先**：所有資料以 JSON 的形式進 repo，不依賴外部 DB／後端；純前端 vanilla JS + Web Components，無框架依賴。
- **零密鑰**：所有功能不含 API key / token / secret，資料源皆為公開 API 或 Build-Time 排程抓取。
- **GitHub-Native / Fork-First**：任何人 fork 本倉庫、開啟 GitHub Pages 即可獨立運作，不需申請任何 API key。
- **Build-Time 優先**：所有資料由 GitHub Actions 排程預先算好寫入 `data/*.json`，前端只負責讀取與呈現，不在瀏覽器端呼叫任何第三方金融 API。

## 頁面（11 個功能頁 + 說明/日誌）

| 頁面 | 檔名 | 說明 |
|------|------|------|
| Market（首頁） | `index.html` | 全球主要股市卡（台股/美股/日經/恆生/歐股/KOSPI）、Market Health 走勢圖、市場情緒與原物料、市值前 10 大、綜合評分 TOP 10、ETF 市值前 10 大 |
| Screener（篩選） | `mklab-stock-screener.html` | 多條件篩選（PE / PB / ROE / EPS / 漲跌%）+ 策略模板（價值 / 品質 / 成長 / 動能 / 高股息） |
| Research（研究） | `mklab-stock-research.html` | 個股深度研究：K 線圖、MACD / KD 指標、財報摘要 |
| Industry（產業） | `mklab-stock-industry.html` | 依臺證所 33 個官方產業大類，查看漲跌績效、產業輪動熱力圖、成分股（含市值欄） |
| Watchlist（自選） | `mklab-stock-watchlist.html` | 新增自選股代號排序追蹤；目標價／停損價提醒設定（示意，資料存於瀏覽器 localStorage） |
| Dividend（股息） | `mklab-stock-dividend.html` | 全市場殖利率排行 |
| Compare（比較） | `mklab-stock-compare.html` | 最多同時比較 4 檔個股的關鍵指標，自動標示最優欄位（股票代號不分大小寫） |
| Breadth（市場寬度） | `mklab-stock-breadth.html` | 今日市場寬度（上漲/下跌家數）與漲跌幅分布 |
| Backtest（回測） | `mklab-stock-backtest.html` | 兩點式試算（買進日 vs 最新一日收盤價）試算報酬，非完整走勢回測，僅供教育參考 |
| Portfolio（投資組合） | `mklab-stock-portfolio.html` | 持股損益追蹤、持股佔比圓餅圖、個股筆記（資料存於瀏覽器 localStorage） |
| Digest（每日摘要） | `mklab-stock-digest.html` | 每日市場摘要，提供 RSS 訂閱（`rss.xml`） |
| Help（說明） | `mklab-stock-help.html` | 使用說明、資料來源、資料更新頻率、評分標準、免責聲明 |
| Log（開發日誌） | `mklab-stock-log.html` | 開發歷程記錄 |

### 通用操作

- 頂列（Utility Bar）：品牌名稱＋🔍 搜尋／🌓 深色主題／GitHub／⚙ 設定（手機版為☰選單），下方第二列為各分頁導覽（Market / Screener / … / Digest）。
- 點擊 🔍 展開搜尋框，輸入代號（如 `2330`）直接跳到 Research 頁。
- 點擊 🌓 切換深色／淺色主題，設定會存在瀏覽器 localStorage，下次開啟延續上次選擇。
- 點擊 ⚙ 開啟設定抽屜：主題切換、語言（中/EN）、功能說明／開發日誌／GitHub README 捷徑、系統狀態。
- 表格標題（代號／價格／PE／ROE…）可點擊排序，再點一次切換升／降序；每頁最多 10 筆，底部有分頁鍵。
- Watchlist／Portfolio 的自選股、持股與筆記皆存在瀏覽器 localStorage，換裝置或清除瀏覽器資料會遺失，請自行留存紀錄。

## 股市資料來源

| 資料類型 | 來源 | 說明 |
|----------|------|------|
| 每日收盤價／漲跌／PE/PB/殖利率 | **TWSE OpenAPI**（`STOCK_DAY_ALL`） | 台灣證交所公開 API，免 key、雲端可達 |
| ROE / ROA / EPS | **TWSE 營益分析／資產負債表**，雲端備援 **yfinance** | 官方資料為主，週六排程補齊 |
| 全球指數／代表 ETF | **yfinance** | 台股、美股、日股、港股、歐股、韓股（KOSPI）等 |
| TWII 加權指數 K 線 | **yfinance**（`^TWII`，260 日窗口） | 供首頁 Market Health 走勢圖使用 |
| 產業分類 | **臺證所 33 類對照表** | 依「上市公司產業類別劃分暨調整要點（114.06.09）」 |

零 API key、零 secret，fork 即可用。

## 資料更新排程（GitHub Actions，`.github/workflows/daily-update.yml`）

| 排程（UTC） | 台灣時間 | 內容 |
|---|---|---|
| 週一至週五 09:00 | 17:00 | 抓當日收盤、PE/PB/殖利率（TWSE OpenAPI） |
| 每週六 10:00 | 18:00 | 補齊 ROE/ROA（yfinance，含防 ban 延遲） |
| 週一至週五 09:30 | 17:30 | 抓全球指數＋代表 ETF 收盤／漲跌（yfinance） |
| 週一至週五 10:00 | 18:00 | 產生每日市場摘要 + RSS（`data/digest/`、`rss.xml`） |

- 週末／國定假日／突發休市自動跳過（資料源本身無交易日資料）。
- 資料以收盤為準，非即時；各頁頂部黃色提示列會顯示實際資料日。

## 目前資料規模（依 `data/stocks.json` meta，會隨每日更新變動）

- 個股／ETF 檔數：**1,835 檔**（上市 TWSE 1,379 檔＋上櫃 TPEX 456 檔）
- 歷史股價切片：`data/history/` 逐日 JSON，目前約 **300+ 個交易日**
- 產業分類：**33 個官方大類**（`data/industry-codes.json`）
- 全球指數／ETF：`data/indices-config.json` 設定、`data/indices.json` 輸出

## 綜合評分計算標準（Market 首頁「綜合評分 TOP 10」）

即時依下列加權計算（0–100 分），**只列出資料齊全且評分 > 0 的股票**：

| 指標 | 權重 | 計算方式 |
|------|------|----------|
| ROE（股東權益報酬率） | 最高 40 | 越高越好 |
| PE（本益比） | 最高 20 | 越低越好 |
| PB（價格淨值比） | 最高 15 | 越低越好 |
| EPS（每股盈餘） | 最高 10 | 越高越好 |
| 漲跌% | 最高 15 | 越高越好 |

任一欄位缺漏（null）則該股不列入計算。評分僅供研究參考，**非投資建議**。

## 目錄結構

```text
mklab-stock/
├── index.html                    # Market（首頁）
├── mklab-stock-screener.html     # Screener 篩選
├── mklab-stock-research.html     # Research 研究
├── mklab-stock-industry.html     # Industry 產業
├── mklab-stock-watchlist.html    # Watchlist 自選
├── mklab-stock-dividend.html     # Dividend 股息
├── mklab-stock-compare.html      # Compare 比較
├── mklab-stock-breadth.html      # Breadth 市場寬度
├── mklab-stock-backtest.html     # Backtest 回測
├── mklab-stock-portfolio.html    # Portfolio 投資組合
├── mklab-stock-digest.html       # Digest 每日摘要
├── mklab-stock-help.html         # Help 說明
├── mklab-stock-log.html          # Log 開發日誌
├── rss.xml                       # Digest 頁 RSS 訂閱來源
├── assets/
│   ├── css/
│   │   ├── mklab-theme.css       # Design Tokens（:root 變數）+ 基礎 Reset
│   │   ├── layout.css            # 版面配置（Grid/Flex/Card/Table…）
│   │   ├── component.css         # 元件樣式（Nav/Drawer/Footer/Btn/Badge…）
│   │   └── mobile.css            # 響應式斷點
│   └── js/
│       ├── mklab-core.js         # 核心：Shell（導覽列）/ Drawer（設定抽屜）/ DataTable / Notes 等
│       ├── data-client.js        # 統一資料層（快取／新鮮度提示）
│       └── mklab-wc.js           # Web Components（K 線圖等）
├── data/                         # Build-Time 產生的 JSON，前端只讀
│   ├── stocks.json                 # 全市場個股最新一日（1,835 檔全欄位）
│   ├── industry.json               # 33 產業聚合績效
│   ├── industry-codes.json         # 臺證所 33 產業代碼對照表
│   ├── indices.json                 # 全球指數／ETF 收盤
│   ├── indices-config.json          # 指數／ETF 靜態配置（市場/符號/來源）
│   ├── symbol-map.json              # 股票代號對照
│   ├── etf-shares.json              # ETF 發行張數（估算市值用）
│   ├── schema-version.json          # schema 版號
│   ├── twii_kdata.js                # 加權指數 K 線（window.TWII_KDATA）
│   ├── digest/                      # 每日市場摘要（逐日 JSON + index.json）
│   └── history/                     # 每日股價切片（逐日 JSON，OHLCV+PE/PB/DY）
├── docs/                          # 設計依據／資料欄位說明／規範文件
├── skills/                        # Skills First — 每個 Skill 自包含（qa-gate/html-health/lint/data/deployment/design-system/development）
├── vendor/                        # 第三方 JS（lightweight-charts.min.js）
├── .github/workflows/
│   ├── daily-update.yml          # 每日收盤 + 週六 ROE/ROA + 指數/ETF/K線 + 每日摘要
│   └── qa-gate.yml                # 品質門禁
├── HANDOFF.md                    # 架構規範文件
└── README.md                     # 本檔案
```

> 每個頁面是獨立的靜態 HTML（無伺服器端樣板系統），共用的導覽列／設定抽屜／頁尾等區塊由 `assets/js/mklab-core.js` 在載入時以 JS 動態填入對應的 `#mainNav` / `#utilbar` / `#drawer` 容器，樣式統一由 4 個共用 CSS 檔控制。

## 核心架構特色

### 統一資料層（`assets/js/data-client.js`）
- 零依賴 IIFE，支援 `file://` 直開本地預覽。
- 內建快取與新鮮度提示，網路失敗時自動回退可用的舊資料。

### 共用 Shell / Drawer（`assets/js/mklab-core.js`）
- 各頁 `<header>` 內僅留 `#utilbar`（品牌＋工具鈕）與 `#mainNav`（分頁導覽）兩個空容器，由 `MKLAB.Shell.mount()` 統一填入內容，改一次程式碼即可讓全站同步更新。
- 設定抽屜（`MKLAB.Drawer`）集中管理深色主題、語言切換、系統狀態顯示。
- `MKLAB.DataTable` 提供全站表格共用的排序／分頁能力。

### CSS 分層架構（4 檔）
| 檔案 | 職責 |
|------|------|
| `mklab-theme.css` | Design Tokens（`:root` 變數：色彩/圓角/陰影/z-index）+ 基礎 Reset |
| `layout.css` | 版面配置：Header/Nav/Utilbar/Grid/Card/Table 等結構樣式 |
| `component.css` | 元件樣式：按鈕/徽章/表單/工具列/utility class 等 |
| `mobile.css` | 響應式斷點、觸控目標、列印、減少動態、深色模式細節 |

## 本地預覽

```bash
git clone https://github.com/evanhsia-git/mklab-stock.git
cd mklab-stock
python -m http.server 8000
# 開瀏覽器 http://localhost:8000/index.html
```

無需安裝依賴、無需 build step，直接編輯根目錄 HTML／`assets/css/`／`assets/js/` 即可看到變化。

## 上線（GitHub Pages）

1. Fork 或 clone 本 repo。
2. GitHub Pages 設定：Source → `main` branch / `/`（root）。
3. Push 到 `main` 會觸發 `.github/workflows/daily-update.yml` 排程更新資料；網站本身由 GitHub Pages 直接託管靜態檔案，無需額外部署步驟。
4. 線上網址：https://evanhsia-git.github.io/mklab-stock/

## 品質門禁（QA Gate）

```bash
python skills/qa-gate/qa_gate.py --json qa-result.json
```

CI 會在 `.github/workflows/qa-gate.yml` 中自動執行，檢查資料完整性／Schema、HTML 結構健康、CSS Theme 變數一致性、JavaScript 語法等項目。

## 免責聲明

本網站所有資料與評分僅供研究與教育參考，不構成任何投資建議。使用者應自行判斷並承擔投資風險。

## License

MIT
