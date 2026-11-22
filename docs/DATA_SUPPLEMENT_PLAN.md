# MKLAB‑STOCK Data Supplement Plan (Phase B – Completion)

> **Status**：唯讀審查報告已完成，僅建立此補齊計畫文件。  
> **未修改任何正式程式或原始資料**（除非您同意進一步寫入）。  
> **目標**：依 P0/P1 優先級，逐步填入官方 TWSE / MOPS / SEC EDGAR 資料，並對美股個股與 ETF 完成關鍵財務欄位。

---

## A. TWSE Official Financials → `data/stocks.json`

### 目的
將 `data/official-fundamentals.json` 中 1052 檔財報（營收、毛利、營業利益、稅後淨利、EPS、ROE、ROA、資產、負債、股本等）寫入 `stocks.json` 的對應 TWSE 記錄。

### 對照方式
- `official-fundamentals.json` 結構：`{meta, financial:{period, asof,...}, dividend:{...}}`
  - `financial` 子字典的 `period` 為類似 `1101`, `1102` …（每年/季）。
  - 需要將 `period` 映射到 `as_of` 日期或 `date`。目前無直接映射表；建議先建立 **symbol → official_fund_number** 對照表（如 2330 → 1101, 2308 → 1102 …），或根據 `asof` 取最新期。
- 已確認以下 TWSE 代號在 `official-fundamentals.json` 中有記錄：
  - `2330` (台積電) → `in_off_fin=True`
  - `2454` (聯發科) → `in_off_fin=True`
  - `2317` (鴻海) → `in_off_fin=True`
  - `2308` (台達電) → `in_off_fin=True`
  - `2885` (元大金) → `in_off_fin=False` 但 `in_off_div=True`
  - `0050` (元大台灣50) → `in_off_fin=False`, `is_etf=True`
  - `006208` (富邦台50) → `is_etf=True`
  - `00981A` (主動統一台股增長) → `is_etf=True`
  - `009816` (凱基台灣TOP50) → `is_etf=True`

### 待補入欄位（以 2330 為例）
| 欄位 | 現有值 | 需補入來源 | 備註 |
|------|--------|-----------|------|
| `fcf` / `fcf_musd` | `None` | `official-fundamentals.json` → `financial.1101.revenue_ytd_thousand`… 或 `yfinance` freeCashflow | 現金流量表 FCF |
| `cash_musd` | `56722.0` | `official-fundamentals.json` → `financial.1101.liabilities_total_thousand`… | 現金及約當現金 |
| `debt_musd` | `94479.0` | `official-fundamentals.json` → `financial.1101.liabilities_total_thousand`… | 短期借款 + 長期借款合算 |
| `shares_mln` | `25932370067.0` | `official-fundamentals.json` → `financial.1101.equity_parent_thousand`… | 流通股數 |
| `pe` / `pb` / `roe` / `roa` / `eps` / `div` / `market_cap` | 已存在 | 同上 | 部分已填，缺少 `fcf`、`netDebt`、`is_etf`（已加） |

### 補入範例（2330）
```json
{
  "sym": "2330",
  "name": "台積電",
  "price": 2100.0,
  "open": 2165.0,
  "high": 2190.0,
  "low": 2085.0,
  "volume": 56582314.0,
  "pe": 21.29,
  "pe_official": 21.37,
  "pe_src": "computed",
  "pb": 7.78,
  "div": 1.05,
  "roe": 39.77,
  "roa": 27.3,
  "eps": 98.66,
  "capital_stock": 259323700670.0,
  "shares": 25932370067.0,
  "market_cap": 54457977140700,
  "ind": "半導體業",
  "is_etf": false,
  "chg": -3.45,
  "rank": 50.2,
  "listing_date": "1994-09-05",
  "source": "TWSE",
  "quality": "official",
  "security_type": "stock",
  "fcf": <to be filled>,
  "netDebt": <to be filled>,
  "div_cash_latest": 14.0,
  ...
}
```

> ⚠️ **安全提醒**：`netDebt` 為 `null`（未自動轉成 0），保留原有 `calc()` 阻擋邏輯不變。

### 執行步驟（待確認）
1. 建立 `symbol_map.json`：`{sym: official_fund_number}`（例如 `{2330: 1101, 2308: 1102, ...}`).
2. 用 Python 批量更新 `stocks.json`，針對每筆記錄查找對應 `financial[period]` 並填入相應字段。
3. 保存後重新跑 `node tests/test_screener_dcf.js` 與 `test_valuation.js` 驗證。

---

## B. US Stock Detailed Financials → `data/us/us-stocks.json`

### 目的
補充 `Revenue`, `Gross Profit`, `Operating Income`, `Net Income`, `OCF`, `CapEx`, `FCF`, `Cash`, `Debt`, `Shares Outstanding` 等字段。

### 已有欄位
- `fcf_musd`, `cash_musd`, `debt_musd`, `shares_mln` 已存在（來源 `yfinance_info_*`）。

### 待補入欄位（以 AAPL 為例）
| 欄位 | 現有值 | 需補入來源 | 備註 |
|------|--------|-----------|------|
| `revenue` | 未知 | `yfinance` `/financials/revenue` 或 `fetch_us_data.py` | 年/月營收 |
| `gross_profit` | 未知 | `profitability.operating_gross_profit_ytd_thousand` | 營業成本差額 |
| `operating_income` | 未知 | `profitability.operating_income_ytd_thousand` | 營業收入 - 營業成本 |
| `net_income` | 未知 | `profitability.net_income_ytd_thousand` | 稅前淨利 |
| `ocf` | 未知 | `financial.free_cash_flow_ytd_thousand` | 自由現金流 |
| `capex` | 未知 | `financial.capital_expenditure_ytd_thousand` | 資本支出 |
| `fcff` / `fcf` | 有 `fcf_musd` | 同上 | 自由現金流 |
| `cash` | 有 `cash_musd` | 同上 | 現金及約當現金 |
| `debt` | 有 `debt_musd` | 同上 | 短期+長期借款 |
| `shares_outstanding` | 有 `shares_mln` | 同上 | 流通股數 |

### 補入路徑
- 使用 `skills/data/fetch_us_data.py` 或 `scripts/ci_us_data.py` 抓取 yfinance 每日/週資料。
- 若只想「標記缺口」而不實際寫入，先在 `us-stocks.json` 中添加 `missing_fields: {revenue: true, gross_profit: true, ...}`。

### 執行步驟
1. 確保 `pip install yfinance`（工作流已包含）。
2. 執行 `python skills/data/fetch_us_data.py all` 取得 AAPL、MSFT、AMZN、NVDA 等 30 檔。
3. 把回傳的 `Revenue`, `GrossProfit`, `OpIncome`, `NetIncome`, `OCF`, `CapEx`, `FCF`, `Cash`, `Debt`, `SharesOutstanding` 填入 `us-stocks.json` 對應 `sym`。
4. 重演 `node tests/test_us_returns.py`、`test_us_valuation_fields.py` 驗證。

---

## C. ETF Component Data → `data/etf-meta.json`, `data/etf-categories.json`, `stocks.json` ETF rows

### 目的
將 ETF 元資料（`net_assets`, `expense_ratio`, `yield`, `category`, `52w_high/low`, `currency`, `exchange`, `chg_1m/ytd/1y`）與 ETF 成分股權重、基金規模、受益人數、NAV、費用率對應到 `stocks.json` 的 `is_etf=True` 記錄，或建立獨立的 ETF 成分股索引。

### 已有 ETF 元資料
- `data/etf-meta.json`: `etfs` list (365 檔)，每檔含 `net_assets`, `expense_ratio`, `yield`, `category`, `52w_high/low`, `currency`, `exchange`, `chg_1m/ytd/1y`.
- `data/etf-categories.json`: 分類規則（排除後綴、貨幣符號對照等）。
- `data/raw/twse_etf.csv` / `tpex_etf.csv` 提供成分股與權重。

### 待補入欄位（以 QQQ 為例）
| 欄位 | 現有值 | 需補入來源 | 備註 |
|------|--------|-----------|------|
| `nav` | 未知 | `etf-meta.json` → `net_assets`/`expense_ratio`/`yield` | NAV |
| `net_assets` | 未知 | `etf-meta.json` → `net_assets` | 總資產 |
| `expense_ratio` | 未知 | `etf-meta.json` → `expense_ratio` | 管理費率 |
| `category` | 未知 | `etf-categories.json` → category label | 國內/海外型 |
| `component_shares` / `weight` | 未知 | `raw/twse_etf.csv` / `tpex_etf.csv` | 成分股權重 |
| `nav_fraction` | 未知 | `etf-meta.json` → `net_assets`/`expense_ratio` | NAV 折溢價比例 |

### 執行步驟
1. 從 `data/raw/official/twse_etf.csv` 提取每行 `sym, component, weight, total_volume` 等。
2. 對應到 `stocks.json` 中 `is_etf=True` 記錄，追加 `component_shares`, `weight`, `nav_fraction`。
3. 更新 `etf-meta.json` 中的 `net_assets`, `expense_ratio`, `yield`, `category` 等。

---

## 下一步（您的指示）

- **A** → 建立 `symbol_map.json`（TWSE → official_fund_number）並開始填入 TWSE 完整財報。
- **B** → 選擇是否直接使用 `yfinance` 抓取美股詳細財報，或先標記缺口。
- **C** → 決定是否建立 ETF 成分股索引或直接更新 `stocks.json` ETF 行。

請回覆選項 **A / B / C / D**（或全部），以及您希望先做哪一環節，我會立即啟動相應的腳本與寫入操作（僅讀寫本地檔案，不改動 GitHub Actions 或原始資料）。
