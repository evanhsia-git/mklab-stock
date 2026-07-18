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
| Research（研究） | `mklab-stock-research.html` | 個股深度研究，含 K 線圖（KLineChart）、MACD / KD 指標與畫線工具 |
| Industry（產業） | `mklab-stock-industry.html` | 依臺證所 114.06.09 要點劃分的 33 個官方產業大類，查看各產業動態與成分股 |
| Watchlist（自選） | `mklab-stock-watchlist.html` | 在設定抽屜填入最多 5 檔代號，首頁與自選頁即顯示其走勢 |

## 使用說明
- **Market（首頁）**：大盤走勢、自選股、績效表現，以及「綜合評分 TOP 10」推薦清單。
- **Screener（篩選）**：依 PE / PB / ROE / EPS / 漲跌% 等條件過濾股票，內建價值 / 成長 / 動能 等策略模板。
- **Research（研究）**：個股深度研究，含 K 線圖（KLineChart）、MACD / KD 指標與畫線工具。
- **Industry（產業）**：依臺證所 114.06.09 要點劃分的 33 個官方產業大類，查看各產業動態與成分股。
- **Watchlist（自選）**：在設定抽屜填入最多 5 檔代號，首頁與自選頁即顯示其走勢。

### 通用操作
- 點擊右上 🔍 可展開搜尋框，輸入代號（如 `2330`）搜尋。
- 點擊 🌓 主題 切換深色 / 淺色。
- 點擊 ⚙ 設定 開啟抽屜：設定自選股、主題、語言。
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
- **休市處理**：週末 / 國定假日 / 突發颱風假自動跳過
- 資料以收盤為準，非即時。首頁黃標顯示實際資料日。

## 目前資料庫數量
- 上市 / ETF 檔數：**1,369 檔**
- 歷史股價切片：**260 個交易日**
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
├── index.html                    # Market 首頁
├── mklab-stock-screener.html     # Screener 篩選
├── mklab-stock-research.html     # Research 研究
├── mklab-stock-industry.html      # Industry 產業
├── mklab-stock-watchlist.html     # Watchlist 自選
├── mklab-stock-help.html          # 功能說明網頁
├── mklab-stock-log.html           # 開發日誌
├── assets/
│   ├── mklab-core.js             # 全站共用表格/抽屜/工具列模組
│   ├── mklab-wc.js               # Web Components 元件庫（K線/表格/抽屜/路由）
│   ├── data-client.js            # 統一資料存取層
│   └── lightweight-charts.min.js # 圖表庫 (vendor 複製)
├── data/                         # Build-Time 生成的 JSON（前端只讀這裡）
│   ├── stocks.json               # ★ 全市場個股最新一日（最完整，1369 檔全欄位，~359K）
│   ├── industry.json             # 33 產業聚合績效（~5K）
│   ├── indices.json              # 全球指數/ETF 收盤（15 指數+6 ETF，~5.4K）
│   ├── indices-config.json       # 指數/ETF 靜態配置（市場/符號/來源）
│   ├── industry-codes.json       # 臺證所 33 產業代碼對照表
│   ├── markets.json              # 多市場預留結構（US/CN/HK/JP/KR 元數據）
│   ├── market.json               # 五國大盤概覽（首頁五卡）
│   ├── schema-version.json       # schema 版號
│   ├── etf-shares.json           # ETF 發行張數（估算 market_cap 用）
│   ├── twii_kdata.js             # 加權指數 K 線 (window.TWII_KDATA)
│   └── history/                  # 每日股價切片（261 個交易日，各 ~289K）
│       ├── 20250714.json         #   最早一日
│       ├── ...                   #   （每日一檔，含 OHLCV+PE/PB/DY）
│       └── 20260714.json         #   最新一日
├── docs/                         # 設計依據 / 資源 / 規範
│   ├── design.md
│   ├── resource.md
│   ├── SKILL.md
│   └── mklab-stock-schema.md     # 規範與架構手冊
├── skills/
│   └── mklab-stock-lint/         # 品質門禁 Skill（fetch_data.py + qa_gate.py）
├── scripts/                      # 抓取/匯出/QA 腳本
│   ├── fetch_data.py             # 雲端每日抓取（TWSE + yfinance ROE/ROA）
│   ├── export_db.py              # 本機 DB 匯出 stocks.json
│   ├── update_overview.py        # ROE/ROA 補齊（cron 友善，本機 DB）
│   ├── qa_gate.py                # CI 質量門禁
│   └── check_html_health.py      # HTML 結構健康檢查
├── vendor/                       # 第三方庫（零建置，直接引用）
│   └── lightweight-charts.min.js # TradingView LightweightCharts v4.1.3
└── .github/workflows/            # CI/CD
    ├── daily-update.yml          # 每日收盤 + 每週六 ROE/ROA
    ├── qa-gate.yml               # 質量門禁
    └── html-health.yml           # HTML 結構檢查
```

> **資料源頭**：本機 `/root/Documents/database/tw_stock_all.db`（38MB SQLite）是權威來源；`scripts/export_db.py` 將其匯出為上方 `data/*.json` 推上 GitHub Pages。雲端 `fetch_data.py` 每日增量更新收盤價，每週六補 ROE/ROA。



## 本地預覽
```bash
cd mklab-stock
python3 -m http.server 8765
# 開瀏覽器 http://127.0.0.1:8765/index.html
```

## 上線（GitHub Pages / 靜態託管）
1. Fork 或 clone 本 repo。
2. 靜態託管根目錄指向 repo 根（`index.html` 在根）。
3. 無構建步驟需求——靜態成品即上線。
4. 每日更新由 GitHub Actions 自動執行，無需手動干預。

## 品質門禁（mklab-stock-lint）
- `python scripts/qa_gate.py --json qa-result.json`：掃描 5 頁 HTML 靜態結構，輸出 `ALLOW DEPLOY` / `BLOCK DEPLOY`
- CI 中 `.github/workflows/qa-gate.yml` 會在每次 push 自動跑

## 免責聲明
本網站所有資料與評分僅供研究與教育參考，不構成任何投資建議。使用者應自行判斷並承擔投資風險。

## License
MIT