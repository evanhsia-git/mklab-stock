---
name: data
title: mklab-stock Data Skill
description: 資料抓取/每日摘要/結構管理。統一所有 JSON 於 data/，Schema 定義於 schema.md。當用戶要求「更新資料/抓收盤/產生每日摘要/調整 schema」時使用。
version: 1.0
---

# Data Skill（資料管理）

所有執行資料與 Schema 統一放 `data/`，不得建立 `config/`。

## 腳本（自包含於本 Skill）

- `fetch_data.py` — GitHub Actions 每日抓取（daily/weekly/indices/twii）
- `build_digest.py` — 每日市場摘要 + RSS Feed 產生（只讀既有 data/*.json，不呼叫外部 API）
- `compute_indicators.py` — 技術指標計算（MA5/10/20/30、RSI14、MACD、KD），純讀取本地
  `data/history/*.json` 逐日快照做數學計算，不對外發送任何請求，計算結果直接寫回
  `data/stocks.json` 既有紀錄，不新增任何前端下載檔案

## 執行方式

```bash
python3 skills/data/fetch_data.py daily      # 每日收盤+PE/PB/殖利率
python3 skills/data/fetch_data.py weekly     # 每週 yfinance 補 ROE/ROA
python3 skills/data/fetch_data.py indices    # 全球指數+ETF
python3 skills/data/fetch_data.py twii       # ^TWII K 線
python3 skills/data/compute_indicators.py    # MA/RSI/MACD/KD（緊接在 daily 之後執行）
python3 skills/data/build_digest.py          # 每日摘要 + RSS
```

## 資料源優先順序

TWSE → TPEX → Yahoo Finance (yfinance) → FinMind（選用，不依賴）

## 輸出

- `data/stocks.json`（含 MA/RSI/MACD/KD 技術指標欄位）/ `data/industry.json` / `data/indices.json`
- `data/history/YYYYMMDD.json` 每日切片
