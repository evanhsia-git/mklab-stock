# QA_CHECK_COVERAGE — qa_gate.py 檢查項目完整盤點

- 基準報告: 69 項（schema v2.0）｜10 分類｜MANUAL 3 項（不計入自動阻擋）

## 盤點結論（Data Protection v2.1）
- run() 為**全線性執行**：無提前 return（唯一 return 在尾端報告輸出）——不存在「跳過後半段檢查」的路徑
- 提前 return 僅存在於嵌套 helper（_load_opt/_num/字串處理），不影響檢查序列
- 動態檢查（Data 類規則項）：name 含當日數據（如 [TWSE_T_MINUS_1] 日期），**恆被 add**（條件只影響 status，不影響執行與否）
- 漏跑唯一路徑 = run() 中途崩潰（無報告）或報告截斷 → 由 scan_completed/expected_checks 防護
- REQUIRED_CHECKS（12 項）只含 name 恆穩定項；動態 name 項一律不列入（避免誤判漏跑）

## 必要檢查項目（REQUIRED_CHECKS，12 項）

- OHLC 合理性 (L<=O,C<=H, H>=L, 價格>0, 成交量>=0, 市值>0)
- Python 第三方依賴全部登記於 requirements.txt
- industry.json Schema
- meta 統計與實際陣列一致
- stocks.json Schema
- 內部連結 HTTP 200 (本地)
- 無髒值 (NaN/null/undefined/Infinity/空字串/非法'-')
- 異常漲跌檢查 (>10.5% 警示 / >30% 阻擋)
- 結構健康檢查
- 股票代號唯一
- 行情日期合理（非未來日期）、stale 資料明示
- 資料檔案大小預算（膨脹監控）

## 完整 69 項清單（分類／名稱／必要性／執行條件／資料依賴）

### 【Python】18 項（執行條件: 無條件（全線性）｜資料依賴: skills/data/*.py 檔案清單）

- `syntax: fetch_data.py` — 常規
- `syntax: fetch_us_data.py` — 常規
- `syntax: fetch_us_universe.py` — 常規
- `syntax: build_digest.py` — 常規
- `syntax: data_rules.py` — 常規
- `syntax: sanitize_snapshot.py` — 常規
- `syntax: compute_indicators.py` — 常規
- `syntax: check_html_health.py` — 常規
- `syntax: qa_gate.py` — 常規
- `import-ok: fetch_data.py` — 常規
- `import-ok: fetch_us_data.py` — 常規
- `import-ok: fetch_us_universe.py` — 常規
- `import-ok: build_digest.py` — 常規
- `import-ok: data_rules.py` — 常規
- `import-ok: sanitize_snapshot.py` — 常規
- `import-ok: compute_indicators.py` — 常規
- `import-ok: check_html_health.py` — 常規
- `import-ok: qa_gate.py` — 常規

### 【Data】17 項（執行條件: 無條件｜資料依賴: —）

- `股票代號唯一` — ⭐必要
- `無髒值 (NaN/null/undefined/Infinity/空字串/非法'-')` — ⭐必要
- `[PE_EPS_MISMATCH] PE 與 價/EPS 偏差超過 25%：1 檔，需確認期間基準`（動態 name） — 常規
- `[PE_OFFICIAL_FALLBACK] 1 檔無可用本站 EPS（含極端值），本益比沿用交易所公告值：['2540`（動態 name） — 常規
- `[PE_EPS_IMPLIED] 35 檔無官方損益表，EPS 由官方 PE 反推（TWSE_PE_IMPLIED；pe`（動態 name） — 常規
- `[TWSE_T_MINUS_1] TWSE 最新日期 2026-11-19 較 TPEX 2026-11-20 落後 1`（動態 name） — 常規
- `[NO_PRICE] 無收盤價（停牌/無成交）：8 檔，例 ['00625K', '00643K', '00707R',`（動態 name） — 常規
- `[SUSPENDED_HELD] 停牌／當日無成交，沿用前次紀錄：1 檔，例 ['1808']（保留最後成交日，非最新價`（動態 name） — 常規
- `[ETF_HOLDINGS_TRUNCATED] ETF 成份股總數仍標成 10（可能被截斷為前 10 大）：3 檔，例`（動態 name） — 常規
- `OHLC 合理性 (L<=O,C<=H, H>=L, 價格>0, 成交量>=0, 市值>0)` — ⭐必要
- `異常漲跌檢查 (>10.5% 警示 / >30% 阻擋)` — ⭐必要
- `meta 統計與實際陣列一致` — ⭐必要
- `行情日期合理（非未來日期）、stale 資料明示` — ⭐必要
- `公司行為登記完整 (CORPORATE_ACTION_UNSOURCED)`（動態 name） — 常規
- `歷史快照死值列 (DEAD_VALUE_RUN)`（動態 name） — 常規
- `待確認公司行為候選 (CORPORATE_ACTION_DETECTED)`（動態 name） — 常規
- `官方公司行為預告 (CORPORATE_ACTION_UPCOMING)`（動態 name） — 常規

### 【CI】2 項（執行條件: 無條件｜資料依賴: requirements.txt、data/*.json 大小）

- `Python 第三方依賴全部登記於 requirements.txt` — ⭐必要
- `資料檔案大小預算（膨脹監控）` — ⭐必要

### 【JSON】2 項（執行條件: 無條件｜資料依賴: data/stocks.json、data/industry.json）

- `stocks.json Schema` — ⭐必要
- `industry.json Schema` — ⭐必要

### 【HTML】2 項（執行條件: 無條件（import 失敗仍以 ERROR 呈現）｜資料依賴: *.html）

- `結構健康檢查` — ⭐必要
- `pagerId 是否都有對應的 .pager 容器` — 常規

### 【CSS】5 項（執行條件: 無條件｜資料依賴: *.html 內 <style>）

- `統一 Theme 變數 (var(--bg) 等)` — 常規
- `禁止硬寫核心樣式 (違反 Design Token)` — 常規
- `屬性誤用 = 取代 :（語法錯誤）` — 常規
- `自訂屬性 (--xxx) 有使用但未定義` — 常規
- `跨檔案重複的選擇器（非 @media 層級）` — 常規

### 【JS】19 項（執行條件: 無條件｜資料依賴: *.html 內 <script>）

- `DataTable cols 是否都在 COLUMNS 定義內` — 常規
- `syntax: mklab-stock-screener.html#0` — 常規
- `syntax: index.html#0` — 常規
- `syntax: mklab-stock-us.html#0` — 常規
- `syntax: mklab-stock-backtest.html#0` — 常規
- `syntax: mklab-stock-research.html#0` — 常規
- `syntax: mklab-stock-research.html#1` — 常規
- `syntax: mklab-stock-research.html#2` — 常規
- `syntax: mklab-stock-research.html#3` — 常規
- `syntax: mklab-stock-research.html#4` — 常規
- `syntax: mklab-stock-research.html#5` — 常規
- `syntax: mklab-stock-compare.html#0` — 常規
- `syntax: mklab-stock-sources.html#0` — 常規
- `syntax: mklab-stock-industry.html#0` — 常規
- `syntax: mklab-stock-digest.html#0` — 常規
- `syntax: mklab-stock-log.html#0` — 常規
- `syntax: mklab-stock-portfolio.html#0` — 常規
- `syntax: mklab-stock-help.html#0` — 常規
- `syntax: mklab-stock-watchlist.html#0` — 常規

### 【Chart】2 項（執行條件: MANUAL（人工截圖核對）｜資料依賴: 瀏覽器渲染）

- `圖表渲染: index.html` — MANUAL
- `圖表渲染: mklab-stock-research.html` — MANUAL

### 【Links】1 項（執行條件: 無條件｜資料依賴: 本地 HTTP server）

- `內部連結 HTTP 200 (本地)` — ⭐必要

### 【Visual】1 項（執行條件: MANUAL（人工截圖核對）｜資料依賴: 瀏覽器截圖 vs Baseline）

- `視覺回歸比對` — MANUAL
