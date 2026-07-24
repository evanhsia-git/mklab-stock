# mklab-stock 資料欄位對照表

> 最後更新：2026-07-19  
> 適用專案：mklab-stock (GitHub-Native, Fork First, 零外部依賴)

---

## 📋 核心欄位對照表

| 類別 | 中文名稱 | 內部欄位 | TWSE (上市) | TPEX (上櫃 ETF) | yfinance (備用) | 備註 |
|------|----------|----------|-------------|-----------------|-----------------|------|
| **基本識別** | | | | | | |
| | 股票代號 | `sym` / `stock_id` | ✅ `Code` | ✅ `SecuritiesCompanyCode` | ✅ `symbol` | 如 `2330`、`00679B` |
| | 股票名稱 | `name` / `stock_name` | ✅ `Name` | ✅ `CompanyName` | ✅ `longName` / `shortName` | 如 `台積電`、`元大美債20年` |
| | 市場別 | `market` | `TWSE` | `TPEX` | `TW`/`TWO` | 內部標記 |
| | 交易所 | `exchange` | `TWSE` | `TPEx` | `TPE`/`TWO` | yfinance 用 `.TW`/`.TWO` |
| | 產業別 | `ind` / `industry` | ❌ 需另抓 | ❌ 需另抓 | ✅ `industry` / `sector` | 用 33 類對照表補 |
| | 是否 ETF | `is_etf` | 名稱推斷 | 名稱/代碼推斷 | ✅ `quoteType`='ETF' | 關鍵字：ETF/基金/指數/正/反/槓桿... |
| **價格資訊 (每日更新)** | | | | | | |
| | 收盤價 | `price` / `close` | ✅ `ClosingPrice` | ✅ `Close` | ✅ `currentPrice` / `regularMarketPrice` | 單位：元 |
| | 開盤價 | `open` | ✅ `OpeningPrice` | ✅ `Open` | ✅ `open` / `regularMarketOpen` | ETF 可能無開高低 |
| | 最高價 | `high` | ✅ `HighestPrice` | ✅ `High` | ✅ `dayHigh` / `regularMarketDayHigh` | 同上 |
| | 最低價 | `low` | ✅ `LowestPrice` | ✅ `Low` | ✅ `dayLow` / `regularMarketDayLow` | 同上 |
| | 成交量 | `volume` | ✅ `TradeVolume` (張) | ✅ `TradingShares` (張) | ✅ `volume` / `regularMarketVolume` | 單位：張(台股) / 股(美股) |
| | 成交金額 | `turnover` | ✅ `TradeValue` (元) | ✅ `TradingAmount` (元) | ❌ | 台股特有 |
| | 成交筆數 | `transactions` | ✅ `Transaction` | ✅ `TradingCount` | ❌ | 台股特有 |
| | 漲跌價差 | `change` | ✅ `Change` (元) | ✅ `Change` (元) | ✅ `regularMarketChange` | 正=漲，負=跌 |
| | 漲跌幅 % | `chg` / `chg_pct` | 計算得出 | 計算得出 | ✅ `regularMarketChangePercent` | 內部統一存 % |
| | 昨收價 | `prev_close` | 推算 | 推算 | ✅ `previousClose` / `regularMarketPreviousClose` | |
| **估值指標 (每日更新)** | | | | | | |
| | 本益比 (PE) | `pe` | ✅ `PERatio` (BWIBBU) | ✅ `PERatio` (PE Ratio API) | ✅ `trailingPE` / `forwardPE` | TWSE/TPEX 為最新財報試算 |
| | 股價淨值比 (PB) | `pb` | ✅ `PB` (BWIBBU) | ❌ 通常無 | ✅ `priceToBook` | TPEX BWIBBU 可能無 PB |
| | 殖利率 % | `div` / `dividend_yield` | ✅ `DividendYield` (BWIBBU) | ❌ 通常無 | ✅ `dividendYield` | TWSE 為現金殖利率 |
| **財務基本面 (週/季更新)** | | | | | | |
| | 股東權益報酬率 % | `roe` | ⚠️ `t187ap06_L` 失效 | ❌ | ✅ `returnOnEquity` | 以 yfinance 週報補 |
| | 資產報酬率 % | `roa` | ⚠️ `t187ap06_L` 失效 | ❌ | ✅ `returnOnAssets` | 同上 |
| | 每股盈餘 (EPS) | `eps` | ⚠️ `t187ap06_L` 失效 | ❌ | ✅ `trailingEps` / `forwardEps` | 同上 |
| | 實收資本額 | `capital_stock` | ⚠️ `t187ap05_L` 失效 | ❌ | ❌ | 需 MOPS 公開資訊觀測站 |
| | 淨利 | `net_income` | ⚠️ `t187ap03_L` 失效 | ❌ | ✅ `netIncomeToCommon` | 綜合損益表 |
| | 總資產 | `total_assets` | ❌ | ❌ | ✅ `totalAssets` | 資產負債表 |
| | 股東權益 | `equity` | ❌ | ❌ | ✅ `totalStockholderEquity` | 同上 |
| **衍生/計算欄位** | | | | | | |
| | 時價總額 | `market_cap` | 估算 (價×張) | 估算 (價×張) | ✅ `marketCap` | 台股 ETF 用發行張數精算 |
| | 流通在外股數 | `shares_outstanding` | ❌ | ❌ | ✅ `sharesOutstanding` | yfinance 有 |
| | 52 週最高 | `high_52w` | ❌ | ❌ | ✅ `fiftyTwoWeekHigh` | |
| | 52 週最低 | `low_52w` | ❌ | ❌ | ✅ `fiftyTwoWeekLow` | |
| | Beta 值 | `beta` | ❌ | ❌ | ✅ `beta` | 美股常用 |
| **技術指標** | | | | | | |
| | RSI | `rsi` | ❌ | ❌ | 可計算 | 前端即時算 |
| | 移動平均 | `ma5/10/20/60` | ❌ | ❌ | 可計算 | 同上 |
| | MACD/KD | - | ❌ | ❌ | 可計算 | 前端 LightweightCharts 算 |
| **資料品質標記 (內部)** | | | | | | |
| | 資料來源 | `source` | `TWSE` | `TPEX` | `Yahoo Finance` | 追蹤來源 |
| | 品質等級 | `quality` | `official` | `official` | `yfinance_fallback` | 官方 vs 備用 |
| | 最後更新 | `last_updated` | 交易日期 | 交易日期 | 抓取日期 | YYYY-MM-DD |

---

## 🔑 關鍵 API 端點對照

| 功能 | TWSE (證交所) | TPEX (櫃買中心) | yfinance |
|------|---------------|-----------------|----------|
| **每日收盤** | `https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL` | `https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes?l=zh-tw` | `yf.Ticker("2330.TW").history()` |
| **PE/PB/殖利率** | `https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL` | `https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_pe_ratio?l=zh-tw` (僅 PE) | 含在 `info` 物件 |
| **營益分析 (ROE/ROA/EPS)** | `https://openapi.twse.com.tw/v1/opendata/t187ap06_L` **失效** | ❌ | `info['returnOnEquity']` 等 |
| **資產負債表 (股本)** | `https://openapi.twse.com.tw/v1/opendata/t187ap05_L` **失效** | ❌ | ❌ |
| **綜合損益表 (淨利)** | `https://openapi.twse.com.tw/v1/opendata/t187ap03_L` **失效** | ❌ | `info['netIncomeToCommon']` |
| **歷史 K 線** | 自建 DB / `STOCK_DAY` | 自建 DB | `history(period="1y")` |
| **指數/ETF** | `TWII` 等 | 上櫃 ETF 含在 daily | `^TWII`、`0050.TW` 等 |

---

## ⚠️ 現況摘要

| 狀態 | 說明 |
|------|------|
| ✅ **完整可用** | TWSE/TPEX 每日收盤、PE、漲跌、成交量 |
| ⚠️ **API 失效** | TWSE 營益分析/資產負債/損益表 (t187ap06/05/03_L 回傳 HTML) |
| 🔄 **備用方案** | yfinance 週報補 ROE/ROA/EPS (免 key，sleep 3s 防 ban) |
| ❌ **完全無** | TPEX 的 PB、殖利率、ROE、ROA、EPS、股本 |

---

## 💡 建議後續補強

1. **TWSE 新版財報 API** - 需研究 `https://mops.twse.com.tw/mops/web/ajax_t163sb04` 等 POST 端點
2. **MOPS 公開資訊觀測站** - 季報財務數據 (XBRL 格式)
3. **yfinance 擴充** - 補齊 `marketCap`、`sharesOutstanding`、`beta` 等衍生指標

---

## 📦 stocks.json 實際結構範例

```json
{
  "meta": {
    "as_of": "2026-07-17",
    "source": "TWSE OpenAPI STOCK_DAY_ALL (免 key, 雲端)",
    "schema_version": "1.0.0",
    "count": 1789,
    "sources": { "TWSE": 1371, "TPEX": 418 },
    "note": "收盤/漲跌每日更新；ROE/ROA/EPS/股本 由 TWSE 營益分析/資產負債表（官方免 key）補齊；ETF 含於上市清單；上限 2000 檔"
  },
  "stocks": [
    {
      "sym": "2330",
      "name": "台積電",
      "price": 1050.0,
      "open": 1045.0,
      "high": 1060.0,
      "low": 1040.0,
      "volume": 1234567,
      "pe": 24.1,
      "pb": 5.2,
      "div": 1.8,
      "roe": 28.5,
      "roa": 15.2,
      "eps": 43.6,
      "capital_stock": 259293870000,
      "market_cap": 2720000000000,
      "ind": "半導體業",
      "is_etf": false,
      "chg": 1.2,
      "rank": 1,
      "source": "TWSE",
      "quality": "official",
      "last_updated": "2026-07-17"
    },
    {
      "sym": "00679B",
      "name": "元大美債20年",
      "price": 12.35,
      "open": 12.30,
      "high": 12.40,
      "low": 12.25,
      "volume": 5000,
      "pe": null,
      "pb": null,
      "div": null,
      "roe": null,
      "roa": null,
      "eps": null,
      "capital_stock": null,
      "market_cap": 1235000000,
      "ind": "ETF",
      "is_etf": true,
      "chg": 0.4,
      "rank": null,
      "source": "TPEX",
      "quality": "official",
      "last_updated": "2026-07-17"
    }
  ]
}
```

---

## 🔗 相關檔案

- `scripts/fetch_data.py` - 主抓取腳本 (daily/weekly/indices)
- `scripts/validate_data.py` - 資料驗證 (必填欄位、數值範圍、新鮮度、來源品質)
- `data/symbol-map.json` - 統一代碼映射表 (TWSE/TPEX/Yahoo)
- `data/industry-codes.json` - 33 大產業代碼表
- `assets/css/component.css` - UI 元件樣式 (Design Token 化)

---

> 此文件為專案核心參考，修改欄位定義請同步更新 `fetch_data.py`、`validate_data.py`、前端顯示邏輯。