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

## 事件驅動檢查（問題庫沉澱，2026-11-25 起）

每次 QA 閘門擋下真實事故後，該事故的模式化防護記錄於此——讓「事後補測試」
升級為「事前有契約」。新增事件時在表末追加一行。

| 日期 | 事故 | 根因 | 固化為 |
|---|---|---|---|
| 2026-11-25 | meta.price_asof_counts 鍵型 'null' vs None，擋下 11-24 推送 | 管線聚合鍵型與 meta 序列化不一致 | qa_gate 的 `meta 統計與實際陣列一致` 檢查含鍵型正規化（2026-11-24 #313 已修） |
| 2026-11-25 | 金融保險 36 檔 ROE 過期殘留（roe_src 丟失） | Piotroski MOPS 擴充後浮現舊值 | test_known_errors 的 `ROE/ROA：沒有官方值且非 yfinance 補值者不得殘留過期舊值` |
| 2026-11-25 | 00419A 未上市無 K 線，測試誤報 | 檢查項未考慮上市日 | test_known_errors 的 K 線覆蓋檢查加 `listing_date <= 今天` 豁免 |
| 2026-11-25 | 資料停更 6 天（QA 擋下後當天無重跑＋cron 延遲） | 偵測與恢復缺口（QA 只擋「推送時」） | scripts/quality_sentinel.py（本機哨兵：停更 2 個工作日告警＋安全類自癒＋資料語意類告警待授權） |

**新增流程**：事故 →（1）修復＋固化檢查項 →（2）本表記錄根因與固化位置 →（3）
若屬新檢查類別，同步 qa_checks.json 與 qa_gate.py。已知外部限制（如摩根
持股家用 IP 限定）不新增檢查項，記入 quality_sentinel.py 的 health_summary。

### 2026-11-25~26 失敗班總盤點（8 班 6 根因，全數閉合）

| 班號 | job | 根因 | 固化為 |
|---|---|---|---|
| #233 (11-02) | indices | `^TWIIE/^TWIIF` 假 ticker 404 | 指數清單清理（後續班成功實證） |
| #247 (11-04) | weekly-roe | sources meta 過期 vs 實際陣列 | P1-1 meta 一律重算 |
| #303 (11-20) | official-fundamentals | NEG_EPS_PE 26 檔假 PE | 寧缺勿假清理＋data_rules 檢查 |
| #308 (11-23) | daily | fetch_etf_nav `import requests` runner 沒裝 | requirements.txt 登記＋QA「第三方依賴全登記」檢查 |
| #311 (11-24) | sec-edgar | ROOT 路徑少一層 | `2e017313` 路徑修正 |
| #313 (11-24) | daily | meta 鍵型 'null' vs None | qa_gate 鍵型正規化（見上表首行） |
| #317/#319 (11-25) | daily | 契約精確總數 vs 條件式項浮動（67/68≠69） | `521f0ba6` 範圍下限契約＋`dc034d91` 上限撤除 |

## 條件式檢查項登記制（2026-11-26 起）

「只在特定資料條件下出現」的檢查項會讓 QA 執行數自然浮動（例如 TWSE_T_MINUS_1
只在 TWSE 落後 TPEX 時出現）。**規範**：

1. 新增條件式檢查項時，**必須**同步登記於 `skills/qa-gate/qa_checks.json` 的
   `conditional_checks` 陣列（名稱、出現條件、等級）。
2. `conditional_check_slack`（現值 3）= 契約允許的執行數下浮餘裕——
   qa_gate 只驗下限 `executed >= TOTAL - slack`（防漏跑，fail closed），上限不設
   （資料品質規則拆動態名屬合法增加，交由 verdict 判定 BLOCK）。
3. **禁止**把條件式項列入 `required_checks`（名稱不恆定）。
4. slack 不足以涵蓋新登記的條件式項時，調高 `conditional_check_slack`。

## 失敗班自動重試分級（P2，2026-11-26 起）

daily-update.yml 新增 `retry-or-report` job（needs 全部 job、if: always()）：

- **有 job 失敗且本次非重試** → 自動重觸發自身一次（`retry=1`）
- **重試後仍失敗** → 不再重試（防循環），發 `::warning::` 交人工檢查
- **資料類失敗**（QA 擋下）：重試後仍會被同一關卡擋下、同樣只重試一次——
  行為安全，不會重複推送壞資料（推送前一律過 QA 閘門）
- 業務結果告警仍由 telegram-notify 監聽器負責（不重複通知）
