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
- `parse_etf_meta.py` — 解析使用者手動匯出的 TWSE/TPEx ETF 投資篩選器 CSV（`data/raw/twse_etf.csv`、
  `data/raw/tpex_etf.csv`），輸出 `data/etf-meta.json`（上市/上櫃日期、發行人、受益人數等）。
  **半自動、不在排程裡**：這兩個網站表格是前端 JS 動態載入，沒有公開 JSON API，且使用條款
  禁止自動化擷取，改用網站本身提供的「CSV 下載」功能手動匯出，故本腳本需要人工先放好 CSV
  再執行，不會被 daily-update.yml 自動呼叫
- `fetch_us_data.py` — 美股個股/ETF 市值前 30 大抓取（僅 yfinance），輸出至獨立的 `data/us/`
  資料夾，與台股資料完全分開管理、互不呼叫、互不匯入（排程也獨立：UTC 22:00）
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
python3 skills/data/fetch_us_data.py all     # 美股個股+ETF 前30大（獨立於台股管線）
python3 skills/data/parse_etf_meta.py        # 解析 data/raw/*.csv → data/etf-meta.json（需先手動放好 CSV，見腳本檔頭說明）
```

## 資料源優先順序

TWSE → TPEX → Yahoo Finance (yfinance) → FinMind（選用，不依賴）

## 輸出

- `data/stocks.json`（含 MA/RSI/MACD/KD 技術指標欄位）/ `data/industry.json` / `data/indices.json`
- `data/history/YYYYMMDD.json` 每日切片
- `data/us/us-stocks.json` / `data/us/us-etfs.json`（美股專用，與台股資料完全分開）
- `data/etf-meta.json`（ETF 上市/上櫃日期、發行人、受益人數；`data/raw/` 底下放人工匯出的原始 CSV）
