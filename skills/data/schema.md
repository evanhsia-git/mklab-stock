# Data Schema（結構定義）

## stocks.json

```json
{
  "meta": { "as_of": "YYYY-MM-DD", "source": "...", "schema_version": "1.0.0", "count": N },
  "stocks": [
    {
      "sym": "2330", "name": "台積電",
      "price": 1050.0, "open": 1045.0, "high": 1060.0, "low": 1040.0,
      "volume": 1234567, "pe": 24.1, "pb": 5.2, "div": 1.8,
      "roe": 28.5, "roa": 15.2, "eps": 43.6, "capital_stock": 259293870000,
      "market_cap": 2720000000000, "ind": "半導體業", "is_etf": false,
      "chg": 1.2, "rank": 1, "source": "TWSE", "quality": "official",
      "last_updated": "YYYY-MM-DD"
    }
  ]
}
```

## 欄位規則

- OHLC：`price>0`、`high>=low`、`high>=open`、`high>=close`、`low<=open`、`low<=close`、`volume>=0`、`market_cap>0`
- 可為 null（ETF/外股）：`pe/pb/div/roe/eps/rank/capital_stock`
- `ind` 用 33 類產業代碼（見 `data/industry-codes.json`）

## 禁止

- 不得建立 `config/`（設定 JSON 統一放 `data/`）
- 任意修改 JSON Schema 需同步更新本文件與 `fetch_data.py`
