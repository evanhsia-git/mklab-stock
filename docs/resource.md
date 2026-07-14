---
title: "mklab-stock 資源清單"
description: "股市 Dashboard 開發的參考資源——分析平台/Python 框架/Pages 框架/UI 庫/圖表庫/資料源/學習順序；並標註與 mklab-stock-skill 的採用狀態。"
summary: "mklab-stock 參考資源頁：OpenBB/TradingView 等平台、Streamlit/Dash 等 Python 框架、Quartz/Astro 等靜態框架、shadcn/Tremor UI、Plotly/ECharts 圖表、10 家 Provider 資料源；每項標註「我們狀態：採用/參考/備援/未採用」以對齊 skill。"
type: project
status: active
tags:
  - etf
  - finance
created: 2026-07-13
updated: 2026-07-14
---

# mklab-stock 資源清單

> 參考資源彙整，供 [[mklab-stock-v2-100個功能|mklab-stock 專案架構]] 與 [[finance/mklab-stock-prompt|實作紀錄]] 選型使用。
> 來源：用戶提供《Python 股票分析 Dashboard 開發指南（Hermes Edition）》。
> **對齊依據**：本頁每項標註「我們狀態」以對照可部署 Skill 正文 [[mklab-stock-skill|mklab-stock 可部署 Skill]] 與架構主文 [[finance/mklab-stock|mklab-stock 架構主文 v3.0]]。

**我們狀態圖例**：`採用` = skill/主文已納入正式技術棧；`參考` = UI/UX 或實作借鏡但不直接依賴；`備援` = Tier2/3 設 secret 才啟用；`未採用` = 替代路線，當前架構不選。

### 我們技術對照總表（skill §二 / §四 / §六）
| 類別 | 我們採用 | 來源章節 |
|------|----------|----------|
| 前端框架 | React + TS + Vite | skill §二 |
| UI | Tailwind + shadcn/ui | skill §二 / §四 |
| 圖表 | ECharts | skill §二 |
| 表格 | TanStack Table（虛擬化） | skill §二 |
| 後端腳本 | Python 3.11 純腳本（產 `data/*.json`，免 DB） | skill §二 / §五 |
| 部署 | Actions artifact-based Pages + `make deploy` | skill §二 / §九 |
| 資料源 Tier1 | TWSE / TPEx / Yahoo / Stooq（免 key） | skill §四 |
| 資料源 Tier2/3 | FinMind / Alpha Vantage / FMP / Finnhub / Polygon / Bloomberg（設 secret） | skill §四 |

---

## 一、股票分析平台（參考對象）
| 名稱 | 官方網站 | GitHub | 推薦 | 我們狀態 |
| --- | --- | --- | --- | --- |
| OpenBB | https://openbb.co | https://github.com/OpenBB-finance/OpenBB | ⭐⭐⭐⭐⭐ | 參考（UI/UX 風格） |
| TradingView | https://www.tradingview.com | - | ⭐⭐⭐⭐⭐ | 參考（UI/UX 風格；但非即時盤，見主文 §4 新手心態） |
| Finviz | https://finviz.com | - | ⭐⭐⭐⭐⭐ | 參考（Heatmap / Screener 概念） |
| Koyfin | https://www.koyfin.com | - | ⭐⭐⭐⭐ | 參考（複合視圖） |
| Simply Wall St | https://simplywall.st | - | ⭐⭐⭐⭐ | 參考（財報燈號視覺） |
| StockAnalysis | https://stockanalysis.com | - | ⭐⭐⭐⭐ | 參考 |
| MacroTrends | https://www.macrotrends.net | - | ⭐⭐⭐⭐ | 參考 |
| CompaniesMarketCap | https://companiesmarketcap.com | - | ⭐⭐⭐⭐⭐ | 參考（市值排名） |

> 我們的 Dashboard 風格參考 Bloomberg Terminal / TradingView / OpenBB / Koyfin（見 prompt 頁 6.0）。這些皆為**參考對象**，非我們的依賴或 fork 來源。

---

## 二、Python Dashboard 框架
| 框架 | 網址 | GitHub | 用途 | 我們狀態 |
| --- | --- | --- | --- | --- |
| Streamlit | https://streamlit.io | streamlit/streamlit | 快速 Dashboard | 未採用（React 替代） |
| Dash | https://dash.plotly.com | plotly/dash | 專業互動圖表 | 未採用（React 替代） |
| NiceGUI | https://nicegui.io | zauberzeug/nicegui | 全 Python Web UI | 未採用 |
| Panel | https://panel.holoviz.org | holoviz/panel | 科學分析 | 未採用 |
| Bokeh | https://bokeh.org | bokeh/bokeh | 互動圖表 | 未採用 |
| PyGWalker | https://docs.kanaries.net/pygwalker | Kanaries/pygwalker | 視覺分析 | 未採用 |
| Gradio | https://gradio.app | gradio-app/gradio | AI Demo | 未採用 |
| Reflex | https://reflex.dev | reflex-dev/reflex | Python Full Stack | 未採用（替代路線：若未來想零前端學習可重構，但當前選 React） |

> ⚠️ **與我們架構的關係**：我們已決定前端用 **React+TS+Tailwind+shadcn/ui**（非 Python 框架，見 skill §二）。上表是「全 Python 方案」替代路線——當前不採用。

---

## 三、GitHub Pages / 文件框架
| 框架 | 網址 | 我們狀態 |
| --- | --- | --- |
| Quartz | https://quartz.jzhao.xyz | 未採用（本專案）；但**我們 Obsidian Vault 已用 Quartz 發布**（另項，非 dashboard 本身） |
| Material for MkDocs | https://squidfunk.github.io/mkdocs-material/ | 未採用 |
| Docusaurus | https://docusaurus.io/showcase | 未採用 |
| Astro | https://astro.build/showcase | 未採用 |
| Hugo | https://gohugo.io/showcase/ | 未採用 |
| Jekyll | https://jekyllrb.com/showcase/ | 未採用 |
| VitePress | https://vitepress.dev | 未採用 |
| Nextra | https://nextra.site | 未採用 |

> 我們的 mklab-stock 用 **React (Vite) 直接 build → Pages**（見 skill §二 / 主文 §10 樹），不走上述文件框架（那些是文件/部落格型，非 Dashboard 型）。Quartz 僅用於本 vault 文件站，與 dashboard 部署無關。

---

## 四、Dashboard UI 元件庫
| 庫 | 網址 | 我們狀態 |
| --- | --- | --- |
| Tremor | https://www.tremor.so | 參考（Dashboard 元件概念） |
| shadcn/ui | https://ui.shadcn.com | **採用**（skill §二 / §四） |
| Tabler | https://tabler.io | 未採用 |
| Flowbite | https://flowbite.com | 未採用 |
| Mantine | https://mantine.dev | 未採用 |
| Aceternity UI | https://ui.aceternity.com | 未採用 |

---

## 五、圖表庫
| 庫 | 網址 | 我們狀態 |
| --- | --- | --- |
| KLineChart | https://klinecharts.com | **採用（K線專用頁）**：自託管 dist 進 repo，零依賴、內建 MACD/KDJ/畫圖工具；Market 版塊2 與 Research 個股 K線使用 |
| Apache ECharts | https://echarts.apache.org | **備選（複雜儀表板）**：當需要地理圖/統計圖時；非 K線首選（K線需手刻 MACD/KD/畫圖，違反效率第一） |
| Chart.js | https://www.chartjs.org | **備選（一般小圖）**：體積比 ECharts 輕，必要時取代 ECharts 畫非 K線圖 |
| Plotly | https://plotly.com | 參考（體積大，不採用） |
| Highcharts | https://www.highcharts.com | 未採用（商用授權） |

> 分層策略（2026-07-14 依執行效率第一修訂）：**K線頁 = KLineChart（自託管，內建 MACD+KD+畫圖）**；**其餘小圖 = 內聯 SVG sparkline（0KB）或 Chart.js**；ECharts 降為「複雜儀表板備選」，不再作統一圖表庫。原 `網頁設計0714-1.md` 與 skill §二「統一 ECharts」已廢止，改採本分層。

---

## 六、資料源（Data Provider Layer）
對齊 skill §四 10 provider 模型（Tier1 免 key 主源；Tier2/3 設 secret 才實例化）。

| Provider | 網址 | Tier | 市場 | 我們狀態 |
| --- | --- | --- | --- | --- |
| TWSE | https://www.twse.com.tw | 1 | TW 上市 | **採用（主源，免 key）** |
| TPEx | https://www.tpex.org.tw | 1 | TPEX 上櫃/ETF | **採用（主源，免 key）** |
| Yahoo (yfinance) | https://github.com/ranaroussi/yfinance | 1 | TW,US,GLOBAL,指數 | **採用（主源，免 key）**；原指南 `yfinance` 即此 |
| Stooq | https://www.stooq.com | 1 | US,GLOBAL,指數 | **採用（主源，免 key）** |
| FinMind | https://finmindtrade.com | 2 | TW | 備援（設 `FINMIND_TOKEN` 才啟用） |
| Alpha Vantage | https://www.alphavantage.co | 2 | US,GLOBAL | 備援（設 `ALPHAVANTAGE_KEY`） |
| FMP | https://financialmodelingprep.com | 2 | US,GLOBAL | 備援（設 `FMP_KEY`） |
| Finnhub | https://finnhub.io | 2 | US,GLOBAL | 備援（設 `FINNHUB_KEY`） |
| Polygon | https://polygon.io | 3 | US,GLOBAL | 備援（設 `POLYGON_KEY`） |
| Bloomberg | https://www.bloomberg.com | 3 | GLOBAL | 備援（設 `BLOOMBERG_KEY`） |

> Tier1（TWSE/TPEx/Yahoo/Stooq）為 Fork 即跑主源，免 API Key；Tier2/3 為選配備援，僅當使用者於 repo 設定對應 secret 才進 Provider 池（見 skill §四 Registry / 紅線）。原指南僅列 TWSE/TPEx/FinMind/yfinance，已擴充對齊 10 provider 模型。

---

## 七、建議架構（原指南版，供對照）
```
GitHub Actions → Python → FinMind/yfinance → 策略分析 → Plotly
→ Jinja2 → HTML Dashboard → GitHub Pages → Obsidian → Hermes Agent
```
> 此為「Python 全包」路線。我們的架構（見主文 v3.0 / skill）改為 **React 前端 + 雙源解耦 + Data Contract + Provider Layer**，更適合長期擴充。狀態：`未採用（參考對照）`。

---

## 八、學習順序（原指南建議）
1. TradingView（參考 UI）
2. OpenBB（參考 UI）
3. Streamlit Gallery（未採用路線）
4. Dash Gallery（未採用路線）
5. NiceGUI（未採用路線）
6. Quartz（我們 Vault 已用）
7. Material for MkDocs（未採用）
8. shadcn/ui（**我們採用**）
9. Tremor（參考）
10. Astro（未採用）

---

## 九、TODO（原指南，對照我們專案現行 Phase）
- [ ] 建立股票 Dashboard → 對應我們 **Phase 0 骨架 + Phase 1 核心**
- [ ] GitHub Actions 自動更新 → 對應**雙排程**（daily-tw / daily-us / deploy.yml）
- [ ] GitHub Pages 發布 → 對應**部署**（Actions artifact-based Pages + `make deploy`）
- [ ] Telegram 通知 → 對應**雙示警**（GitHub Issues + Telegram/Email 設 secret）
- [ ] Obsidian 自動同步 → Quartz 已有（vault 文件站，非 dashboard）
- [ ] Hermes Agent 整合 → 對應 P4 Optional Backend（AI 摘要設 Key 才啟用，Phase2）

> 原指南寫「Phase 1~5 / Admin Phase 6」已過時；現行路線為 **Phase 0 / 1 / 2**（見 skill §九）。

---

## 十、圖表庫與實作參考（用戶提供連結，2026-07-14 收錄）
評估基準：我們採 **React + Vite + Static First**，運算全 Build-Time、零常駐後端；圖表採**分層策略**（見 §五）：K線專用頁 = KLineChart（自託管），其餘小圖 = 內聯 SVG/Chart.js，ECharts 降為複雜儀表板備選。

| 項目 | 網址 | 功能 | 我們狀態 / 能否用於 Pages |
|------|------|------|---------------------------|
| KLineChart 官網 | https://klinecharts.com | 輕量 K線圖（canvas，零依賴，內建 MACD/KDJ/畫圖工具，支援手機） | **採用（K線專用頁）**：自託管 dist 進 repo/vendor，無 CDN、無外部依賴；Market 版塊2 與 Research 個股 K線實作；Apache-2.0 |
| KLineChart 倉庫 | https://github.com/klinecharts/KLineChart | 同上原始碼；零依賴、可高度自訂 | **採用**：本地 `npm pack klinecharts` 取 umd 自託管，符合 Static-First |
| Lightweight Charts 文件 | https://tradingview.github.io/lightweight-charts/docs | TradingView 輕量金融圖表庫（canvas，K線/面積/基線/柱狀） | **備選（未採用）**：雖快，但 MACD/KD/畫圖需手刻，且授權須標註 TradingView；KLineChart 已滿足需求故不引入 |
| Lightweight Charts 倉庫 | https://github.com/tradingview/lightweight-charts | 同上原始碼；含 AI coding skill（v5 API） | 同上；Apache-2.0，須 attribution |
| ECharts 範例庫 | https://echarts.apache.org/examples/ | 官方範例（K線/雷達/權益曲線模板） | **備選（複雜儀表板）**：僅當需要地理圖/統計圖時參考，非 K線首選 |
| Chart.js 倉庫 | https://github.com/chartjs/Chart.js | 通用圖表庫（非金融專精） | **備選（一般小圖）**：體積比 ECharts 輕，必要時取代 ECharts 畫非 K線圖 |
| D3 Gallery | https://observablehq.com/@d3/gallery | D3 資料視覺化範例（自定義/force/tree/geo） | **僅參考**：學習曲線高、React 整合重；Heatmap/自定圖可借鏡，不直接依賴（P8 簡單優先） |
| github_watch | https://github.com/RohanAdwankar/github_watch | 靜態 treemap 範例：Actions 每日產 `heatmap.json` → Pages，無 DB/無伺服器 | **架構級參考（推薦）**：其「Actions 算→寫 JSON→Pages 渲染」模式 = 我們 §三/§10 骨架；可作 Market Heatmap View（漲跌家數/市值 treemap）實作參考 |
| stock-screener 線上版 | https://xang1234.github.io/stock-screener/ | 多市場選股器靜態 Demo（80+ 篩選/廣度/RRG） | **概念參考**：其 Screener/Ranking/Breadth = 我們 Asset Domain Screener/Ranking + Market 廣度；靜態版功能受限 |
| stock-screener 倉庫 | https://github.com/xang1234/stock-screener | 同上原始碼（Docker+Postgres 重棧；含靜態版） | **概念參考（不引入後端）**：借其篩選邏輯/UI 概念；資料走我們 Tier1 + Build-Time，不引入其 Docker/Postgres |
|
**stock-screener 可應用功能映射（對照我們 Domain）**

| 它的功能 | 我們對應 Domain | 應用方式 |
|----------|----------------|----------|
| Scan 綜合評分 + 80+ 篩選 + CSV 匯出 | Asset（Screener/Ranking） | 採相同**綜合評分模型**（Minervini/CANSLIM 通過條件→評分門檻）；Build-Time 算好寫 `asset.json` 的 `screener[]/ranking[]`，前端只渲染。最該抄的核心 |
| Market Health & Exposure 0–100 量尺 | 首頁（風險彙整）+ Market | 移植其評分公式（DMA 距離/分發日/VIX）做首頁風險燈；純 Tier1 算，Phase1 可做 |
| Breadth（StockBee 廣度） | Market（Heatmap/漲跌家數） | ±4% 動能/趨勢窗定義直接沿用；`market.json` 漲跌家數加廣度指標 |
| Groups + RRG 相對旋轉圖 | Market（類股強弱，進階） | RRG 適合「市場層級只看好壞」進階視圖；運算貴→歸 Phase2 |
| Watchlist sparkline + 多週期漲跌條 | Portfolio（watchlist）/ 首頁 | UI 直接借；擴 `user.json` watchlist 欄位 |
| Stock Detail 評分面板 | Asset 個股頁 | 評分/燈號面板結構參考 |
| Validation 回測 | Research（Phase2） | 其「確定性可重現」設計值得學；設 Key/運算貴→Phase2 |
| Themes AI / Assistant AI | P4 Optional Backend | 僅設 secret 才啟用，不進核心 |

> 不抄：Live App 後端堆疊（FastAPI/Postgres/Redis/Celery）、Operations 頁（我們用 GitHub Issues/Projects）、Material-UI/Recharts（我們用 shadcn/ui+ECharts）、12 市場擴張（我們採 **TW + US + China(A股滬深/港股)**，見主文 §11；China 經 Yahoo/Stooq 符號零 secret 達成，非 stock-screener 的 12 市場 Docker 模式）。
> 其 Static Site 模式（預匯出 JSON→Pages 只讀）**驗證我們架構選擇正確**。

**收錄結論**
- 直接採用：ECharts 範例庫（#3）。
- 架構級參考（最值得學）：github_watch（#5，靜態 JSON→Pages 模式）；stock-screener（#6/#7，Screener/廣度概念）。
- 可選補強：Lightweight Charts（#1/#2，僅 K線效能需求時，注意授權標註）。
- 僅靈感 / 不採：D3（#4 借鏡）、Chart.js（#4 未採用）。

---

## 十一、對 stock-screener 功能覆蓋率 + 5 Domain 功能說明（2026-07-14）

### 11.1 我們的 Domain 主題
嚴格 **5 個功能 Domain + 首頁複合視圖**（架構 v3.0）；System 不佔導覽。

| # | Domain | 階段 | 只回答的問題 | 對應 stock-screener |
|---|--------|------|--------------|---------------------|
| 0 | **首頁** | 1 | 今天市場？持股有無問題？哪些值得注意/有風險？ | Daily 首頁 |
| 1 | **Market** | 1 | 今天市場怎麼樣？ | Market Health + Breadth + Groups(部分) |
| 2 | **Asset** | 1 | 這檔值得研究嗎？我想找股票？ | Scan + Stock Detail + Groups |
| 3 | **Portfolio** | 1 | 我的投資現在如何？ | Watchlists + Themes(持倉) |
| 4 | **Research** | 2 進階 | 我的策略有效嗎？ | Validation(回測) |
| 5 | **Learning** | 2 進階 | 我想學習什麼？ | —（stock-screener 無對應） |

### 11.2 各 Domain 功能說明
| Domain | 功能說明 | 資料契約 |
|--------|----------|----------|
| **首頁** | 複合視圖：市場狀態 banner + 持倉異常提示 + 值得注意/風險清單 | `market.json`(meta+狀態+新鮮度) + `portfolio.json`(含 watchlist) |
| **Market** | 市場層級好壞（Heatmap 漲跌家數/市值色塊）；Breadth 廣度指標（±4% 動能/趨勢窗）；不做事個股 Ranking | `market.json` |
| **Asset** | 個股/ETF 同構；Screener（Minervini/CANSLIM 綜合評分）、Ranking、Compare、News；個股頁含評分面板 + K線 | `asset.json` |
| **Portfolio** | 持倉績效（user.json 驅動，含 watchlist）；demo 內建、真實不 push | `portfolio.json` |
| **Research** | 策略回測（Phase2 進階）；Report 為 View | `research.json` |
| **Learning** | 學習中心（Phase2 進階，低頻）；calendar 為 Tool | `learning.json` |

### 11.3 覆蓋率估算（約束：不用外部工具、Actions+Pages 直接跑、零 secret）
| 類別 | 覆蓋率 | 說明 |
|------|--------|------|
| **核心功能**（首頁/Market/Asset/Portfolio + Health/Breadth/Screener/Detail） | **≈90–95%** | Phase1 即達；呈現方式與 stock-screener 靜態版幾乎同構 |
| **含 Phase2 進階**（Research 回測 / RRG / Learning） | **≈75–80%** | RRG/回測需 Phase2，基礎類股排名可做 |
| **含 AI / Live 後端** | **0%** | 刻意排除（違 Static-First）；AI 留 Optional（設 secret） |
| **市場範圍** | **TW+US+China** | stock-screener 含 12 市場；我們聚焦 3 區，China 經 Tier1 達成 |

> 結論：在「不用外部工具」約束下，我們能做到 stock-screener **靜態站呈現的約 90% 核心功能**；剩餘 10% 為 AI 主題發現與多市場擴張（定為未來開發性）。呈現形式非常接近。

### 11.4 China 市場擴充（對應主文 §11）
- 範圍：A股滬深（`.SS`/`.SZ`）+ 港股（`.HK`），經 Yahoo/Stooq 符號。
- 實作：不新增 Provider 契約/secret；`china.py` 做符號對應，路由走既有 yahoo/stooq；`daily-cn.yml` 19:00 排程；資料併入 `market.json`/`asset.json` 加 `market:"cn"` 欄位。
- 閘門：8 項全「是/低影響」→ 直接進核心，無違憲法（主文 §11.3 留存評估表）。

### 11.5 歷史深度與容量約束（對應主文 §12）
- **基線：3 年每日收盤**（約 750 交易日）；可選 5 年。對照 stock-screener 方法論最少需 1 年，我們已超。
- **容量關鍵**：差異在「存什麼」非「存多久」。原始日線全量 JSON（反例）3 年台股 127.5 MB 會爆 repo；**只存衍生結果**（Screener/Ranking 評分+指標，不含 OHLCV）3 年全市場（TW+US+China 精選 ~3000 檔）僅 **~0.9 MB**。
- **GitHub 約束（用戶明定）**：單 repo <**100MB**、**預留 30%** → 可用 70MB；我們實際 ~1MB，佔 1.2%。
- **設計鐵律**：① 禁原始日線進 repo（留 VPS DB）② `data/*.json` 合計 <70MB ③ 每日增量覆寫非重寫 ④ 回溯不 push 原始 ⑤ CI 防護 `data/>70MB` 則 fail。

## 12. 策略與回測功能清單（對應主文 §13）

> 基於 Tier1 資料（TW/US/China OHLCV+財務，3 年基線）+ stock-screener 方法論。全部可用免 key 資料實作，不需 FinMind 等付費源。

### 12.1 可應用策略
| 策略 | 來源 | 說明 | 階段 |
|------|------|------|------|
| **Minervini 選股** | stock-screener 借鏡 | Stage-2 強勢股：52週新高附近、價 >200DMA、RS 領先、季營收成長 | Phase1（Asset Screener） |
| **CANSLIM** | 同上 | O'Neil 法：當季 EPS 成長 + 產業龍頭 + 價量突破 | Phase1 |
| **綜合評分 Ranking** | 同上 | Composite：Strong Buy≥80 / Buy≥70 / Watch≥60 / Pass<60 | Phase1 |
| **IPO 基部構型** | stock-screener 提及 | 上市不久、形成基部後突破 | Phase1（可擴充） |
| **RS 相對強度** | 方法論 | 3mo/6mo/9mo/12mo 加權評分，找市場相對強勢股 | Phase1 |
| **Market Breadth 廣度** | 已定義 Market Domain | ±4% 動能、34日趨勢窗、A/D 線 | Phase1 |
| **Market Health 量尺** | 首頁風險燈 | 0–100 曝險量尺，決定倉位大小 | Phase1 |
| **類股輪動 RRG** | stock-screener Groups | RS-Ratio vs RS-Momentum 四象循環（Leading→Weakening→Lagging→Improving） | Phase2 進階 |
| **Volume Breakthrough** | stock-screener 提及 | 爆量突破基部 | Phase1（可擴充） |
| **均線多空排列** | 技術 | MA20/50/200 黃金/死亡交叉、多頭排列選股 | Phase1 |

### 12.2 因子層（Research Domain，Phase2）
- 因子計算：動能、價值（PE/PB）、規模、股利殖利率（DB 已有 `pe_ratio`/`pb_ratio`/`dividend_yield`）
- 因子中性化：控制市值/產業後的純因子收益

### 12.3 回測功能（Research Domain，Phase2）
| 功能 | 說明 | 狀態 |
|------|------|------|
| **策略回測** | 3 年資料跑歷史表現 | 已定義 |
| **Validation 驗證** | 30/90/180 日 follow-through 追蹤 | 已定義 |
| **回測版本快照** | 比較策略演化 | 已定義 |
| **Report 為 View** | 回測報告頁（隱藏） | 已定義 |
| **Replay 工具** | 延後（低頻+運算貴） | 延後 |
| **因子中性化 / Compare** | Phase2 進階 | 已定義 |

### 12.4 刻意排除（架構憲法刪除）
| 功能 | 原因 |
|------|------|
| Walk-Forward 最佳化 | 過擬合風險 + 運算貴 |
| 蒙地卡羅模擬 | 回測縮小範圍刪除 |
| 因子權重優化 | 避免過擬合 |
| 恐慌貪婪指數 | 非 Tier1 可穩定取得 |

### 12.5 回測技術要點
- **資料**：3 年每日收盤，TW+US+China
- **避免未來函數**：`trade_date` 嚴格時序
- **樣本外驗證**：跨多空狀態
- **績效指標**：年化報酬、最大回撤、Sharpe、勝率

---

## 相關節點
- [[mklab-stock-skill|mklab-stock 可部署 Skill 正文（執行規範）]]
- [[finance/mklab-stock|mklab-stock 架構主文 v3.0（設計依據）]]
- [[mklab-stock-v2-100個功能|mklab-stock 專案架構]]
- [[finance/mklab-stock-prompt|mklab-stock 實作紀錄與提示詞]]
- [[finance/github-actions-pages-stock-analysis|GitHub Actions/Pages 股市應用研究]]
