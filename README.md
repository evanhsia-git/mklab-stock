# mklab-stock

手機優先的台股 / 美股 / 全球指數股市儀表板。靜態優先（Static-First）、Build-Time 預算、資料層零密鑰即可上線，`git clone` 或 fork 後即可獨立運作。

> 線上版：**https://evanhsia-git.github.io/mklab-stock/**

## 設計原則

- **靜態優先**：所有資料以 JSON 形式進 repo，不依賴外部 DB／後端；純前端 vanilla JS + Web Components，無框架依賴。
- **資料層零密鑰**：所有股市資料源皆為公開 API 或 Build-Time 排程抓取，不需任何 API key（Telegram 通知為選配功能，使用 GitHub Secrets，未設定時自動跳過）。
- **GitHub-Native / Fork-First**：任何人 fork 本倉庫、開啟 GitHub Pages 即可獨立運作。
- **Build-Time 優先**：所有資料由 GitHub Actions 排程預先算好寫入 `data/*.json`，前端只負責讀取與呈現，不在瀏覽器端呼叫任何第三方金融 API。
- **Fail-Closed 品質門禁**：任何 QA Critical ERROR 一律阻擋發布，不推送壞資料。

## 頁面（13 個功能頁）

| 頁面 | 檔名 | 說明 |
|------|------|------|
| Market（首頁） | `index.html` | 全球主要股市卡、Market Health 走勢圖、市場情緒與原物料、市值前 10 大、綜合評分 TOP 10、ETF 市值前 10 大 |
| Screener（篩選） | `mklab-stock-screener.html` | 多條件篩選（PE / PB / ROE / ROA / RSI / 均線 / 漲跌% / 殖利率 / 產業別）+ 策略模板（價值 / 品質 / 成長 / 動能 / 高股息 / 超高股息） |
| Research（研究） | `mklab-stock-research.html` | 個股深度研究：K 線圖、MACD / KD 指標、財報摘要 |
| Industry（產業） | `mklab-stock-industry.html` | 臺證所 33 個官方產業大類：漲跌績效、輪動熱力圖、成分股 |
| Watchlist（自選） | `mklab-stock-watchlist.html` | 自選股追蹤；目標價／停損價提醒（資料存於瀏覽器 localStorage） |
| Compare（比較） | `mklab-stock-compare.html` | 最多 4 檔個股關鍵指標比較＋區間報酬率比較 |
| Backtest（回測） | `mklab-stock-backtest.html` | 策略回測 |
| Portfolio 投資組合 | `mklab-stock-portfolio.html` | 持股損益追蹤；選取 ETF 顯示前 10 大成分股與權重（`data/etf-holdings.json`） |
| Digest（每日摘要） | `mklab-stock-digest.html` | 每日市場摘要＋RSS 訂閱（`rss.xml`） |
| US（美股） | `mklab-stock-us.html` | 美股市值前 30 大個股＋ETF 規模前 30 大（`data/us/`，資料源 yfinance＋SEC EDGAR） |
| Sources（來源） | `mklab-stock-sources.html` | 資料來源清單與說明 |
| Help（說明） | `mklab-stock-help.html` | 使用說明、資料來源、更新頻率、評分標準、免責聲明 |
| Log（開發日誌） | `mklab-stock-log.html` | 開發歷程記錄 |

### 通用操作

- 頂列（Utility Bar）：品牌＋🔍 搜尋／🌓 深色主題／GitHub／⚙ 設定；第二列為分頁導覽。
- 表格標題可點擊排序，每頁最多 10 筆＋分頁鍵。
- Watchlist／Portfolio 的自選股、持股存於瀏覽器 localStorage，換裝置會遺失。

## 股市資料來源

| 資料類型 | 來源 | 說明 |
|----------|------|------|
| 每日收盤價／漲跌／PE/PB/殖利率 | **TWSE OpenAPI**（`STOCK_DAY_ALL`） | 台灣證交所公開 API，免 key |
| ROE / ROA / EPS | **TWSE 官方財報（MOPS）**，雲端備援 **yfinance** | 官方資料為主；無官方值且非 yfinance 補值者不留殘值（寧缺勿假） |
| 全球指數／代表 ETF | **yfinance** | 台股、美股、日經、恆生、歐股、KOSPI |
| 美股財報基本資料 | **SEC EDGAR Company Facts** | 合規 User-Agent（程式名＋聯絡 Email）、限速 ≤10 req/s |
| 台股加權指數 K 線 | **yfinance**（`^TWII`） | 首頁 Market Health 走勢圖 |
| 產業分類 | **臺證所 33 類對照表** | 依「上市公司產業類別劃分暨調整要點」 |
| 指數替代 ETF 持股 | **發行人官網**（SSGA／Vanguard／Invesco）＋ TickerInside 備援 | iShares 對資料中心 IP 403，改人工放入＋45 天期限 |

## 資料更新排程（GitHub Actions，`daily-update.yml` 共 10 個 job）

**併發控制**：workflow 層 `group: data-update`；job 層 `group: mklab-git-push` + `queue: max` 序列化推送。所有推送統一經過 **`scripts/ci_commit_push.sh` v2.1**：路徑白名單外有變更即拒絕（fail closed）、合併衝突**中止不靜默挑版本**、QA 閘門固定不可繞過。

| Job | 功能 | 更新頻率（台灣時間） | 資料來源 |
|---|---|---|---|
| `daily` | 每日收盤行情、PE、殖利率；技術指標、K 線、產業統計、官方公司資訊整合；摘要與 RSS | 週一至週五 17:00（**21:00 有當日重試 cron**） | TWSE／TPEx OpenAPI |
| `weekly-roe` | 補沒有官方財報的一般股票 ROE／ROA | 週六 18:00 | yfinance |
| `indices` | 全球指數、全球 ETF、總經指標、`^TWII` K 線 | 週一至週五 17:30 | yfinance |
| `us-market` | 美股市值前 30 大個股、ETF 規模前 30 大 | 週一至週五 06:00（隔日） | yfinance |
| `sec-edgar` | 美股財報基本資料（Company Facts）更新 `us-stocks.json` | 每週五 06:15（隔日） | SEC EDGAR |
| `global-history` | 美股指數、全球指數與情緒的每日收盤（月檔累積） | 週一至週五 06:30（隔日） | yfinance |
| `index-holdings` | 四大指數替代 ETF（DIA/QQQ/SOXX/VOO）持股與權重 | 每月 2 日 06:45（隔日） | 發行人官網＋備援 |
| `official-fundamentals` | TWSE 官方財報、股利、基金與公司基本資料 | 每月 20 日 18:00 | TWSE OpenAPI＋MOPS |
| `etf-meta` | ETF 規模／受益人數＋官方清單分類 | 週日 18:00 | TWSE OpenAPI |
| `etf-qa` | Phase 4 QA Automation＋完整 QA 閘門 | 週一 17:00 | 本地計算 |
| —（投信持股） | 國泰／聯邦／大華銀 PCF＋富蘭克林華美月報＋13 家投信破解 | **每月 1/16 日**（耗時 98% 是等投信網站回應，15 天制） | 各投信官網 |

## 品質門禁（QA Gate，Data Protection v2.1）

四件套全鏈 fail-closed，任何一關失敗即中止、不發布：

```
ci_commit_push.sh v2.1   衝突中止（不靜默挑版本）／路徑白名單 fail closed／QA 閘門不可繞過
  ↓
ci_data_freshness.py v2.1 資料新鮮度守門（過時重寫不倒退）／兩階段恢復
  ↓
ci_qa_gate.sh v2.2      69 項檢查（契約檔 skills/qa-gate/qa_checks.json：總數+12 必要項+scan_completed）
                        掃描器非零退出一律拒絕（無環境變數放行）
  ↓
ci_qa_verdict.py v2.1   契約真值比對（不信任報告自報）／統計交叉重算
```

- 手動執行：`bash scripts/ci_qa_gate.sh`（qa-gate / etf-qa / sec-edgar 等所有 job 推送前自動執行）
- 檢查項契約與事件驅動檢查問題庫：`QA_CHECK_COVERAGE.md`
- 回歸測試：`tests/`（已知錯誤回歸、公司行為、Piotroski、SEC EDGAR、資料規則等 24 個測試檔）
- 已知限制：GitHub Actions 未啟動、平台故障或強制取消時，通知可能無法送達

## Telegram 通知（選配）

GitHub Actions 原生通知，零第三方套件、零修改既有 workflow：

- `telegram-test.yml`：手動測試（dry-run／real／db-status 資料庫狀態報告）
- `telegram-notify.yml`：workflow_run 監聽器——每日報告（P2）、QA 異常／更新失敗／Pages 部署失敗（P0 即時告警），防濫發（成功常態靜默、失敗彙整一則）
- 核心模組 `scripts/telegram_notify.py`（SENT/SKIPPED/FAILED 三態、4096 分段、有限重試、遮蔽）
- 文檔與 Bot 設定教學：`docs/TELEGRAM_NOTIFICATION.md`
- 未設定 Secrets 時全部自動跳過（SKIPPED），不影響任何資料更新與部署

## 目前資料規模（依 `data/stocks.json` meta，隨每日更新變動）

- 個股／ETF 檔數：**1,450 檔**（上市一般股票 1,088＋ETF 362［上市＋上櫃］；上櫃一般股票、特別股、DR、受益證券、ETN、權證皆不收；數量以 data/stocks.json 為準）
- 歷史股價切片：`data/history/` 逐日 JSON，約 300+ 個交易日
- 產業分類：33 個官方大類（`data/industry-codes.json`）
- ETF 持股：`data/etf-holdings.json`（13 家投信＋官方 PCF）；ETF 淨值：`data/etf-nav.json`
- 全球指數／ETF：`data/indices.json`

## 綜合評分計算標準（Market 首頁「綜合評分 TOP 10」）

即時加權計算（0–100 分），只列出資料齊全且評分 > 0 的股票：

| 指標 | 權重 | 計算方式 |
|------|------|----------|
| ROE | 最高 40 | 越高越好 |
| PE | 最高 20 | 越低越好 |
| PB | 最高 15 | 越低越好 |
| EPS | 最高 10 | 越高越好 |
| 漲跌% | 最高 15 | 越高越好 |

任一欄位缺漏（null）則不列入。評分僅供研究參考，**非投資建議**。

## 目錄結構

```text
mklab-stock/
├── index.html                    # Market（首頁）
├── mklab-stock-*.html            # 其餘 12 個功能頁（Screener/Research/Industry/
│                                 #   Watchlist/Compare/Backtest/Portfolio/
│                                 #   Digest/US/Sources/Help/Log）
├── rss.xml                       # Digest 頁 RSS
├── assets/
│   ├── css/                      # mklab-theme/layout/component/mobile（4 檔分層）
│   └── js/                       # mklab-core/data-client/mklab-chart
├── data/                         # Build-Time 產生的 JSON，前端只讀
│   ├── stocks.json               # 全市場最新一日（1,450 檔）
│   ├── industry.json             # 33 產業聚合績效
│   ├── indices.json              # 全球指數／ETF 收盤
│   ├── history/                  # 每日股價切片（逐日 JSON）
│   ├── kline/                    # 個股 K 線（逐檔 JSON）
│   ├── digest/                   # 每日市場摘要
│   ├── etf-holdings.json         # 投信持股（13 家＋官方 PCF）
│   ├── etf-nav.json              # ETF 淨值／折溢價
│   ├── index-holdings/           # DIA/QQQ/SOXX/VOO 持股
│   ├── official-fundamentals.json # TWSE 官方財報彙整
│   └── us/                       # 美股資料（us-stocks.json / us-etfs.json）
├── scripts/                      # CI 與工具腳本
│   ├── ci_commit_push.sh         #   推送守門 v2.1
│   ├── ci_data_freshness.py      #   資料新鮮度守門 v2.1
│   ├── ci_qa_gate.sh             #   QA 閘門 v2.2
│   ├── ci_qa_verdict.py          #   QA 判決 v2.1
│   ├── telegram_notify.py        #   Telegram 核心模組
│   └── telegram_report.py        #   通知報告組裝（workflow_run 監聽）
├── skills/                       # Skills First — 每個 Skill 自包含（qa-gate/data/…）
├── tests/                        # 回歸測試（24 個檔案：資料/程式/通知）
├── docs/                         # 文檔（TELEGRAM_NOTIFICATION.md、DATA_FIELDS.md、schema 等）
├── QA_CHECK_COVERAGE.md          # 69 項 QA 檢查契約＋事件驅動檢查問題庫
├── vendor/                       # 第三方 JS（echarts.min.js）
└── .github/workflows/
    ├── daily-update.yml          # 10 個資料 job（見排程表）
    ├── qa-gate.yml               # 品質門禁（push/PR）
    ├── telegram-test.yml         # 通知手動測試
    └── telegram-notify.yml       # 通知監聽器（workflow_run）
```

## 本地預覽

```bash
git clone https://github.com/evanhsia-git/mklab-stock.git
cd mklab-stock
python -m http.server 8000
# 開瀏覽器 http://localhost:8000/index.html
```

無需安裝依賴、無需 build step。

## 上線（GitHub Pages）

1. Fork 或 clone 本 repo。
2. GitHub Pages 設定：Source → `main` branch / `/`（root）。
3. Push 到 `main` 即觸發排程更新與 QA 門禁；網站由 GitHub Pages 直接託管。
4. 線上網址：https://evanhsia-git.github.io/mklab-stock/

## 免責聲明

本網站所有資料與評分僅供研究與教育參考，不構成任何投資建議。使用者應自行判斷並承擔投資風險。

## License

MIT
