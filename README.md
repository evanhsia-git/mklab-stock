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
| Screener（篩選） | `mklab-stock-screener.html` | 多條件篩選（PE / PB / ROE / ROA / RSI / 均線 / 漲跌% / 殖利率 / 產業別）+ 策略模板（價值 / 品質 / 成長 / 動能 / 高股息 / 超高股息），已整合原 Dividend 頁的殖利率排行功能 |
| Research（研究） | `mklab-stock-research.html` | 個股深度研究：K 線圖、MACD / KD 指標、財報摘要 |
| Industry（產業） | `mklab-stock-industry.html` | 依臺證所 33 個官方產業大類，查看漲跌績效、產業輪動熱力圖、成分股（含市值欄） |
| Watchlist（自選） | `mklab-stock-watchlist.html` | 新增自選股代號排序追蹤；目標價／停損價提醒設定（示意，資料存於瀏覽器 localStorage） |
| Compare（比較） | `mklab-stock-compare.html` | 最多同時比較 4 檔個股的關鍵指標，自動標示最優欄位（股票代號不分大小寫） |
| Breadth（市場寬度） | `mklab-stock-breadth.html` | 今日市場寬度（上漲/下跌家數）與漲跌幅分布 |
| Backtest（回測） | `mklab-stock-backtest.html` | 兩點式試算（買進日 vs 最新一日收盤價）試算報酬，非完整走勢回測，僅供教育參考 |
| Portfolio（投資組合） | `mklab-stock-portfolio.html` | 持股損益追蹤、持股佔比圓餅圖、個股筆記（資料存於瀏覽器 localStorage） |
| Digest（每日摘要） | `mklab-stock-digest.html` | 每日市場摘要，提供 RSS 訂閱（`rss.xml`） |
| US（美股） | `mklab-stock-us.html` | 美股市值前 30 大個股 + ETF 規模前 30 大（資料源 yfinance，與台股資料完全分開管理於 `data/us/`） |
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

併發控制分兩層：workflow 層級 `group: data-update`（同一時間一個 run）；job 層級 `group: mklab-git-push` + `queue: max`，讓各 job 依序執行、序列化 git push（`queue` 預設是 single，同群組只能「1 執行中 + 1 等待」，一次觸發多個 job 會被自己人取消）。推送統一透過 `scripts/ci_commit_push.sh`：先拉取遠端、衝突時取遠端較新版本、被拒絕時最多重試 5 次；因此每個 checkout 都設 `fetch-depth: 0`（淺層歷史無法合併遠端分岔，推送會失敗）。

### 各 job 說明（共 7 個）

| Job | 功能 | 抓取內容與數量 | 更新頻率（台灣時間） | 資料來源 | 產出 |
|---|---|---|---|---|---|
| `daily` | 每日收盤行情、PE、殖利率；本地計算技術指標、K 線、產業統計、官方公司資訊；每日市場摘要與 RSS | 上市個股與 ETF（TWSE）、上櫃標準 ETF（TPEx），約 1,440 檔；計算與摘要在本地完成 | 週一至週五 17:00 | TWSE OpenAPI、TPEx OpenAPI | `data/stocks.json`、`data/kline/`、`data/industry.json`、`data/history/`、`data/digest/`、`rss.xml` |
| `weekly-roe` | 補沒有官方財報的一般股票 ROE／ROA | 只抓不在 TWSE 官方財報內的一般股票，約數十檔，每檔間隔 3 秒 | 每週六 18:00 | yfinance（第三方） | `data/stocks.json` 的 ROE／ROA |
| `indices` | 全球指數、全球 ETF、總經指標；台股加權指數 K 線 | 指數 16、ETF 12、總經 8，共 36 個代號；`^TWII` 近 260 日 | 週一至週五 17:30 | yfinance（第三方） | `data/indices.json`、`data/twii_kdata.js` |
| `us-market` | 美股市值前 30 大個股、ETF 規模前 30 大 | 候選池約 60 檔個股、40 檔 ETF，取前 30 | 週一至週五 06:00（隔日） | yfinance（第三方） | `data/us/us-stocks.json`、`data/us/us-etfs.json` |
| `global-history` | 美股指數、全球指數與市場情緒的每日收盤，累積為月檔 | 14 個代號（美股 5、全球與情緒 9），每日新增一筆 | 週一至週五 06:30（隔日） | yfinance（第三方） | `data/us-history-YYYY/us-history-YYYY-MM.json`、`data/global-history-YYYY/global-history-YYYY-MM.json` |
| `index-holdings` | 四大指數替代 ETF 的持股與權重 | DIA（約 30）、QQQ（約 100）、SOXX（約 30）、VOO（約 500） | 每月 2 日 06:45（隔日） | SSGA 官方 XLSX（DIA）、Vanguard 官方 JSON（VOO，失敗時用手動檔）、Invesco 網站背後的公開 API（QQQ，JSON）、TickerInside 共同備援（SOXX 主要來源，四檔皆備援）；iShares 官方 CSV 對伺服器 403 | `data/index-holdings/*.json` |
| `official-fundamentals` | TWSE 官方財報、股利、基金與公司基本資料自動下載並匯入 | 損益、資產負債表（1,052 家上市公司）、股利（1,115 家）、基金（275 檔）、公司基本資料（1,099 家） | 每月 20 日 18:00 | TWSE OpenAPI（`t187ap03_L`、`t187ap45_L`、`t187ap47_L`）＋ MOPS opendata（`t187ap06_L`、`t187ap07_L`，當日增量批次與既有快照 upsert 合併） | `data/raw/official/`、`data/official-fundamentals.json`、`data/etf-official.json`、`data/stocks.json` 的 ROE／ROA／EPS 與產業欄位 |

### 資料來源分類

- **官方來源**：TWSE、TPEx 的收盤行情、PE、殖利率、產業分類、官方財報與股利、ETF 清單。
- **第三方來源（yfinance）**：ROE／ROA 補充、全球指數與 ETF、美股前 30 大、全球與情緒的月檔、台股加權指數 K 線。非官方，偶爾失敗或限流；失敗時保留上一版，不寫入假值。
- **發行人官網與公開 API**：DIA（SSGA XLSX）、VOO（Vanguard JSON）、QQQ（Invesco `dng-api` JSON）、SOXX（iShares 官方 CSV 對伺服器 403）。
- **共同備援（TickerInside）**：四檔指數替代 ETF 都有；在 VOO／QQQ 是 SEC N-PORT 季報（較舊），只在官方來源失敗時使用；SOXX 因官方 CSV 被封鎖，以它為主要來源。
- **尚未接入（程式面）**：SEC EDGAR（美國財報營收、淨利、EPS、資產負債表、現金流量表、10-K／10-Q）。官方存取規則：**不需要 API key**；HTTP Header 必須提供合規 User-Agent（程式名稱＋版本＋可聯絡 Email，例 `MKLAB Stock evan.hsia@gmail.com`，SEC 不接受隨意編造的信箱，用途是服務異常時能聯絡）；**每秒請求數不得超過 10 次**，本專案更保守，建議控制在 2～3 次/秒。端點、格式與 CIK 皆已確認，接入前提只剩選定要抓的美股標的與存放位置（例如 `data/us/us-fundamentals.json`）。

### ETF 持股自動獲取來源鏈（`index-holdings`）

四檔都是每月更新一次（`freq=monthly`，抓到後 25 天內自動跳過），來源依序嘗試：

| ETF | 主要來源 | 備援（依序） | 2026-11-03 實測產出 |
|---|---|---|---|
| VOO | Vanguard 官方 JSON（`holdingDetails.equityHoldings`） | 手動檔 `VOO_holdings.csv` → TickerInside | 501 檔、98.71%、基準日 2026-09-30 |
| DIA | SSGA 官方 XLSX（檔名必須含 `-en-`） | TickerInside → stockanalysis | 30 檔、99.95% |
| QQQ | Invesco `dng-api` 官方 API（CUSIP 46090E103） | TickerInside → stockanalysis | 101 檔、99.84%、基準日當日 |
| SOXX | 官方 iShares 下載檔（人工放入 `data/raw/official/SOXX_holdings.xls`，45 天內有效） | TickerInside → stockanalysis → iShares URL（僅參考） | 30 檔、99.83%、基準日 2026-11-02 |

- 解析器：`parse_vanguard`／`parse_invesco`／`parse_tickerinside`（JSON 來源）、`parse_spreadsheetml`（iShares 的 `.xls` 其實是 Excel 2003 XML）、`parse_table`（HTML／CSV／XLSX）。只取股票部位，排除現金、期貨與交換等部位（有 `Asset Class` 欄時由 `filter_equity_only` 過濾）。
- **HTTP 200 不等於成功**：下載後同時驗證 status、Content-Type 與 body 開頭，符合格式才進解析流程（`check_content_type`）。實例：Invesco 的 `action=download` 宣稱是 CSV，實際回傳 415KB HTML 網頁；iShares 的 `.xls` 其實是 XML，`pandas.read_html`／`read_excel` 都讀不了。
- **部分官方來源是「IP 型封鎖」**：iShares／BlackRock 對資料中心 IP 一律 403（連瀏覽器都擋），GitHub Actions runner 拿不到 → 改用人工放入 + 45 天期限（`max_age_days`，過期自動讓位給自動來源）。
- 每個來源可各自覆寫驗證門檻（`{"url": …, "expected_min": …}`）：官方來源與免費備援的完整度差很多（QQQ 官方 101 檔 vs 免費層前 25 大），共用一組門檻會讓部分資料靜默通過。
- 產出檔記錄 `source`、`holdings_asof`（來源提供的持股基準日）與 `attribution`（來源條款要求標註時，如 TickerInside）。
- 完整來源清單、格式與實測狀態（含不可用原因）記在 `data/etf-source-urls.json`；生效的來源順序與門檻在 `data/index-proxy.json`。

### 已確認的設計決策

- `twii-kline` 併入 `indices`（兩者都抓 `^TWII`，原本重複）。
- `digest` 併入 `daily`（摘要只讀本地資料）。
- `us-market` 與 `global-history` 維持分開。
- `index-holdings` 改為每月一次（DIA、QQQ、SOXX、VOO 都是每月）。
- 新增 `official-fundamentals`，每月自動下載 TWSE 官方財報，取代原本的手動匯入。
- 所有推送統一經過 `scripts/ci_commit_push.sh`。

## 目前資料規模（依 `data/stocks.json` meta，會隨每日更新變動）

- 個股／ETF 檔數：**1,440 檔**（ETF 352［上市 239＋上櫃 113］、上市一般股票 1,088；範圍：上市一般股票 + 上市 ETF + 上櫃 ETF；上櫃一般股票、特別股、DR、受益證券、ETN、權證皆不收；數量以 data/stocks.json 為準）
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
├── mklab-stock-compare.html      # Compare 比較
├── mklab-stock-breadth.html      # Breadth 市場寬度
├── mklab-stock-backtest.html     # Backtest 回測
├── mklab-stock-portfolio.html    # Portfolio 投資組合
├── mklab-stock-digest.html       # Digest 每日摘要
├── mklab-stock-us.html           # US 美股（前 30 大個股/ETF）
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
│       └── mklab-chart.js        # K 線圖元件（ECharts）
├── data/                         # Build-Time 產生的 JSON，前端只讀
│   ├── stocks.json                 # 全市場個股最新一日（1,440 檔（TWSE 1,327 + TPEx ETF 113；數量以 data/stocks.json 實際筆數為準）
│   ├── industry.json               # 33 產業聚合績效
│   ├── industry-codes.json         # 臺證所 33 產業代碼對照表
│   ├── indices.json                 # 全球指數／ETF 收盤
│   ├── indices-config.json          # 指數／ETF 靜態配置（市場/符號/來源）
│   ├── symbol-map.json              # 股票代號對照
│   ├── etf-shares.json              # ETF 發行張數（估算市值用）
│   ├── schema-version.json          # schema 版號
│   ├── twii_kdata.js                # 加權指數 K 線（window.TWII_KDATA）
│   ├── digest/                      # 每日市場摘要（逐日 JSON + index.json）
│   ├── history/                     # 每日股價切片（逐日 JSON，OHLCV+PE/PB/DY）
│   ├── us/                          # 美股專用資料（與上面台股資料完全分開管理）
│   │   ├── us-stocks.json            # 美股市值前 30 大
│   │   └── us-etfs.json              # 美股 ETF 規模前 30 大
│   ├── etf-meta.json                # ETF 上市/上櫃日期、發行人、受益人數（半自動，見下方說明）
│   └── raw/                         # 人工匯出的原始 CSV（twse_etf.csv／tpex_etf.csv，僅供 parse_etf_meta.py 讀取）
│       ├── official/                # TWSE 官方財報／股利／基金原始檔（由 fetch_official_fundamentals.py 下載）
│       └── twse-openapi-full.md     # TWSE OpenAPI 143 端點完整清單（參考文件，來源 swagger.json）
├── docs/                          # 設計依據／資料欄位說明／規範文件
├── skills/                        # Skills First — 每個 Skill 自包含（qa-gate/html-health/lint/data/deployment/design-system/development）
├── vendor/                        # 第三方 JS（echarts.min.js）
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
