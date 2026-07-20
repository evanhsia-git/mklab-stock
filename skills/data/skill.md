---
name: data
title: mklab-stock Data Skill
description: 資料抓取/匯出/結構管理。統一所有 JSON 於 data/，Schema 定義於 schema.md。當用戶要求「更新資料/抓收盤/匯出 DB/調整 schema」時使用。
version: 1.0
---

# Data Skill（資料管理）

所有執行資料與 Schema 統一放 `data/`，不得建立 `config/`。

## 腳本（自包含於本 Skill）

- `fetch_data.py` — GitHub Actions 每日抓取（daily/weekly/indices/twii）
- `update_overview.py` — 本機 DB 補齊 ROE/ROA
- `export_db.py` — 本機 DB 灌種進 data/（一次性）

## 執行方式

```bash
python3 skills/data/fetch_data.py daily      # 每日收盤+PE/PB/殖利率
python3 skills/data/fetch_data.py weekly     # 每週 yfinance 補 ROE/ROA
python3 skills/data/fetch_data.py indices    # 全球指數+ETF
python3 skills/data/fetch_data.py twii       # ^TWII K 線
python3 skills/data/update_overview.py       # 本機補 ROE/ROA
python3 skills/data/export_db.py             # 本機灌種（一次性）
```

## 資料源優先順序

TWSE → TPEX → Yahoo Finance (yfinance) → FinMind（選用，不依賴）

## 輸出

- `data/stocks.json` / `data/industry.json` / `data/indices.json`
- `data/history/YYYYMMDD.json` 每日切片
- `data/schema-version.json`
