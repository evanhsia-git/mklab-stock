# WORKFLOW_CONSOLIDATION_ANALYSIS — GitHub Actions Jobs 五組整合：Phase 1 盤點＋Phase 2 方案

> 2026-11-26。**本報告僅為分析，未經確認不重構、不 push。**
> 基準：commit `b7124a5c`（v2.2 四檔 QA 架構已上線，qa-gate workflow 首跑 success）。

---

## 一、現況全景（Phase 1）

### 1.1 Workflow 檔案（5 個，共 631 行）

| 檔案 | 行數 | 職責 |
|---|---|---|
| daily-update.yml | 381 | 11 jobs（10 資料＋1 失敗重試）、10 crons |
| qa-gate.yml | 61 | push/PR 觸發的 QA 閘門（唯讀，不推資料） |
| telegram-notify.yml | 47 | CI 結果告警 |
| lkg-promote.yml | 36 | LKG 升級（本輪不動） |
| telegram-test.yml | 106 | 測試（本輪不動） |

### 1.2 daily-update 現有 Jobs 與 Cron（UTC→台北）

| Job | Cron (UTC) | 台北時間 | 頻率 | push 白名單 |
|---|---|---|---|---|
| daily | `0 9 * * 1-5`＋`0 13 * * 1-5` | 17:00／21:00 一~五 | 每日×2 | data/ rss.xml |
| weekly-roe | `0 10 * * 6` | 18:00 六 | 每週 | data/ |
| indices | `30 9 * * 1-5` | 17:30 一~五 | 每日 | data/ |
| us-market | `0 22 * * 1-5` | 06:00 週二~六 | 每日 | data/us/ |
| sec-edgar | `0 22 * * 1-5`（與 us-market **同 cron**） | 06:00 週二~六 | 每日 | data/us/ |
| global-history | `30 22 * * 1-5` | 06:30 週二~六 | 每日 | data/us-history-* data/global-history-* |
| index-holdings | `45 22 2 * *` | 06:45 每月2日 | 每月 | data/index-holdings/ |
| official-fundamentals | `0 10 20 * *` | 18:00 每月20日 | 每月 | data/ data/raw/official/ |
| etf-meta | `0 10 * * 0` | 18:00 日 | 每週 | data/etf-meta.json etf-classified.json stocks.json raw/twse_etf.csv |
| etf-qa | `0 9 * * 1` | 17:00 一 | 每週 | data/ |
| retry-or-report | needs 全部 | — | 失敗時重觸發一次（retry=1 防循環） | — |

### 1.3 Job × 資料檔寫入矩陣（精確到腳本驗證）

| 資料檔 | 寫入者 Job | 衝突 |
|---|---|---|
| **data/stocks.json** | daily、weekly-roe、official-fundamentals、etf-meta | ⚠️ 4 寫入者（跨日期序列化，靠 mklab-git-push 排隊） |
| data/history/*、data/kline/* | daily | — |
| data/industry.json | daily | — |
| data/etf-nav.json | daily（fetch_etf_nav） | — |
| data/etf-holdings.json、etf-holdings-history/* | daily（投信持股） | — |
| data/etf-meta.json、etf-classified.json | etf-meta | — |
| data/market-extras.json、corporate-actions-*.json | daily | — |
| data/digest/*、rss.xml | daily | — |
| data/fetch-log.json | daily | — |
| data/us/us-stocks.json | us-market（fetch_us_data＋returns） | — |
| data/us/us-etfs.json | us-market（fetch_us_data） | — |
| data/us/us-edgar.json | sec-edgar（**明確不動 us-stocks.json**，註解「us-market 班地盤不動，避免撞班」） | — |
| data/indices.json、twii-long.json | indices | — |
| data/us-history-*、global-history-* | global-history | — |
| data/index-holdings/* | index-holdings | — |
| data/raw/official/* | official-fundamentals | — |

### 1.4 共用機制現況

- **QA Gate**：每 job 結尾 `qa_gate.py --gate`（v2.2 統一入口，10 job × 1 次＝每天最多 10 輪 QA）
- **Push**：`ci_commit_push.sh` v2.2（路徑白名單、衝突中止、重試 5 次、push 後 ls-remote 驗證）
- **序列化**：job 層 `mklab-git-push` group（10 job 同組，`queue: max`）；workflow 層 `data-update` group（`single`——新 run 取代排隊中的舊 run）
- **checkout**：全 job `fetch-depth: 0`（v2.1 教訓）
- **失敗重試**：retry-or-report（gh api 查失敗 job→重觸發一次）；另有 21:00 cron 重跑 daily
- **狀態紀錄**：`data/fetch-log.json`（daily 班抓取記錄）；**無跨 job 統一到期/最後成功狀態檔**——到期判斷以「cron 表＋日期條件」硬編在 workflow（投信持股 1/16 即此模式）
- **pip install**：每 job 一次＝10 job 10 次（pip cache 已開，重複成本主要是 runner 時間）
- **requirements.txt**：單一真相源（QA 檢查未登記依賴）

---

## 二、耦合分析（決定分組方式的 3 個關鍵事實）

| # | 事實（腳本級驗證） | 對分組的影響 |
|---|---|---|
| 1 | `fetch_data.py daily` 一次抓 TWSE/TPEx 全市場（個股+ETF 同請求），寫入單一 stocks.json | 台股**個股與 ETF 行情不可拆**（拆＝重複 TWSE 請求，違反規範第 7 節）——**但 ETF 淨值/持股是獨立腳本**（見#2#3） |
| 2 | `fetch_etf_nav.py` 走 **TWSE MIS `all_etf.txt` 單一請求**（與 daily 的 STOCK_DAY_ALL 不同來源），只寫 etf-nav.json，**不碰 stocks.json** | tw-stock 與 tw-etf 拆分**不會重複請求** ✓ |
| 3 | `fetch_us_data.py` 有 `stocks`／`etfs`／`all` 三個子命令（不同 ticker 集合，無重複 yfinance 呼叫）；`fetch_sec_edgar.py` 明確不動 us-stocks.json | us-stock 與 us-etf 拆分**可行且無重複** ✓ |
| 4 | `build_digest.py` 只讀 stocks/indices/industry（「靜態優先」），不依賴 etf-nav | digest 歸 tw-stock 無時序耦合 ✓ |
| 5 | 週日 etf-meta 的 compute_indicators＋integrate_etf_extras 會寫 stocks.json；週六 ROE 也寫 stocks.json | 與 tw-stock（一~五）**不同日**執行，無同日衝突；多寫入者仍靠 push 序列化 |

**結論：五組架構可行，無重複抓取衝突。**

---

## 三、Phase 2：五組重構方案（最小修改）

**設計原則：只動 `daily-update.yml` 的 job 定義與排程，Python/Shell 腳本零變更**（回退＝`git revert` workflow 一個 commit）。

### 3.1 五個 Job 定義

**1️⃣ tw-stock**（台北 17:30 一~五｜週六 18:30 ROE｜月 20 日 18:00 財報）

| 觸發 | 執行腳本（全部沿用現有） |
|---|---|
| 每日 17:30 | fetch_data daily → sanitize_snapshot → repair_history → detect_corporate_actions → compute_indicators → integrate_official_company → fetch/integrate_market_extras → fetch_split_schedule --register → build_kline → compute_industry → build_digest → QA → push（data/ rss.xml） |
| 週六 18:30 | fetch_data weekly（ROE/ROA 補值）→ QA → push |
| 月 20 日 18:00 | fetch_official_fundamentals → import_official_fundamentals → integrate_official_company → QA → push（data/ data/raw/official/） |

寫入：stocks.json、history/*、kline/*、industry.json、market-extras.json、corporate-actions-*、digest/*、rss.xml、raw/official/*（月）

**2️⃣ tw-etf**（台北 17:30 一~五｜週日 18:30 meta｜週一 etf-qa 併 17:30 班）

| 觸發 | 執行腳本 |
|---|---|
| 每日 17:30 | fetch_etf_nav（MIS 獨立請求）→（1/16 條件）投信持股 5 支 → accumulate_etf_holdings_history → verify_pcf_nav → QA → push（etf-nav.json etf-holdings.json etf-holdings-history/ raw/） |
| 週日 18:30 | fetch_etf_meta → classify_etf → compute_indicators → integrate_etf_extras → QA → push |
| 週一 17:30 | qa_phase4（唯讀稽核）→ QA → push（no-op 時不出 commit） |

寫入：etf-nav.json、etf-holdings.json、etf-holdings-history/*、etf-meta.json、etf-classified.json、stocks.json（僅週日）

**3️⃣ us-stock**（台北 06:30 週二~六＝UTC 22:30 一~五）

- `fetch_us_data.py stocks`（個股 531 檔）→ `fetch_us_returns.py` → `fetch_sec_edgar.py` → QA → push（data/us/）
- 寫入：us/us-stocks.json、us/us-edgar.json

**4️⃣ us-etf**（台北 06:30 週二~六｜月 2 日加跑成分股）

- 每日：`fetch_us_data.py etfs`（ETF 120 檔）→ QA → push（data/us/）
- 月 2 日：加跑 `fetch_index_holdings.py` → push（data/index-holdings/）
- 寫入：us/us-etfs.json、index-holdings/*
- **拆分收益**：us-stock／us-etf 各跑各的 ticker 集（無重複 yfinance 呼叫），兩 job 可並行、push 各自獨立白名單

**5️⃣ global-market**（台北 17:30 一~五＋06:30 週二~六，同一 job 兩時段分流）

- 17:30 班：`fetch_data.py indices`＋`fetch_data.py twii` → QA → push（indices.json、twii-long.json）
- 06:30 班：`fetch_global_history.py` → QA → push（us-history-*/global-history-*）
- 寫入：indices.json、twii-long.json、us-history-*、global-history-*
- job 內以 `github.event.schedule` 條件分流（現有 if 模式），時段錯開不會互撞

**6️⃣ retry-or-report**：保留（needs 改為 5 個 job）

### 3.2 新 Cron 表（8 條，現 10 條）

| Cron (UTC) | 台北 | 服務 job（if 條件） |
|---|---|---|
| `30 9 * * 1-5` | 17:30 一~五 | tw-stock、tw-etf、global-market(indices) |
| `22 30 * * 1-5`（即 `30 22 * * 1-5`） | 06:30 週二~六 | us-stock、us-etf、global-market(history) |
| `30 10 * * 6` | 18:30 六 | tw-stock(ROE) |
| `30 10 * * 0` | 18:30 日 | tw-etf(meta) |
| `0 13 * * 1-5` | 21:00 一~五 | 補跑班（mode=retry-failed/due-only，見 3.4） |
| `45 22 2 * *` | 06:45 月2日 | us-etf(index-holdings) |
| `0 10 20 * *` | 18:00 月20日 | tw-stock(財報) |

**SEC EDGAR 時區檢查**：現 `0 22 * * 1-5`（台北 06:00 週二~六）→ 新 `30 22 * * 1-5`（台北 06:30）——**僅平移 30 分鐘，週期不變**（美股週一~五收盤後、台北週二~六早上）——無日期邊界變化。

### 3.3 手動觸發（Phase 4 設計）

```yaml
workflow_dispatch:
  inputs:
    group:
      type: choice
      options: [all, tw-stock, tw-etf, us-stock, us-etf, global-market]
      default: all
    mode:
      type: choice
      options: [due-only, force, retry-failed, dry-run]
      default: due-only
```

| 模式 | 行為 | 安全邊界 |
|---|---|---|
| due-only | 各 job 先跑到期檢查（資料檔日期 vs 今天；如 index-holdings 檔案月份≠本月、投信持股距上次≥15 天），到期才執行 | 預設值，最省 |
| force | 跳過到期檢查直接執行 | **QA Gate、push 白名單、衝突中止照常**（不繞任何安全機制） |
| retry-failed | 對照上個 run 的 gh api 結果，只執行上次失敗的 job | — |
| dry-run | 全部腳本執行＋QA（唯讀報告），**最後跳過 ci_commit_push.sh** | runner workspace 隔離，不 commit、不 push、不碰正式資料 |

job 的 if 條件（手動）：`inputs.group == 'all' || inputs.group == '<組名>'`；到期檢查以 job 內 shell 條件實作（沿用投信持股 1/16 的成熟模式），**不新增 Python/Shell 檔案**。

### 3.4 到期判斷與狀態（回應第 5 節）

- **優先重用既有紀錄**：資料檔本身的日期（stocks.json meta.as_of、index-holdings 檔名月份、etf-holdings 的 holdings_asof）＋ GitHub run 結果（retry-or-report 既有機制）
- **不新增統一狀態檔**——評估結論：跨 job 需要的資訊（各組最後成功/資料日期）已經能從①資料檔日期②gh run api 兩個既有來源取得；新增狀態檔反而引入「狀態檔與實際資料不一致」的新同步問題
- **失敗原因紀錄**：ci_commit_push.sh 已輸出詳細 stderr＋retry-or-report 列出失敗 job 名＋telegram-notify 告警——鏈路已完整

### 3.5 Concurrency 安全改善（回應第 7 節）

**現況風險**：workflow 層 `data-update` 用 `single`（新 run 取代排隊中的舊 run）——若 17:30 run 因 job 層排隊還沒跑完（或還在排），21:00 補跑 run 會**把它整個取消**→當日資料漏跑。

**建議**：**移除 workflow 層 concurrency**，理由：
1. job 層 `mklab-git-push`（queue: max）已完整序列化所有 git push——多 run 並存時 job 依序推，不衝突
2. **due-only 到期判斷**天然防止重複執行（資料已是今天的組別直接 skip）——比「取消整個 run」精確
3. 補跑場景（21:00）不會誤殺還在排隊的 17:30 run

**保留 `mklab-git-push` job 層序列化不動**（符合規範「除非完整測試證明，否則不得解除」）。

---

## 四、前後比較預估（實測待重構後補）

| 指標 | 現況 | 重構後 | 變化 |
|---|---|---|---|
| 資料 Jobs | 10 | 5 | −50% |
| Jobs 總數（含 retry） | 11 | 6 | −45% |
| Cron 數 | 10 | 7 | −30% |
| pip install 輪數 | 10/全日 | 5~7/全日 | −30~50%（runner 時間各省 ~40s） |
| QA Gate 全鏈輪數 | 每日最多 10 | 每日 5~7 | −30~50%（每輪 ~18s） |
| 每日 git push | 最多 4 班（tw/indices/us/edgar） | 3~4 班（tw-stock、tw-etf、us×2） | 持平或略減 |
| YAML 行數 | 381 | 預估 ~300 | −20%（待實測） |
| Python/Shell 檔案 | 0 增減 | **0 增減** | 腳本層零變更 |
| 資料欄位/Schema | — | **完全不變** | 前端零影響 |

**執行時間**：各組腳本與現況相同（不重複抓取）；總 CI 時間因 pip/QA 輪數減少而下降（預估每日省 3~5 分鐘，重構後實測）。

---

## 五、風險與回退

| # | 風險 | 緩解 |
|---|---|---|
| 1 | tw-stock job 龐大（12 腳本、~20 分） | 與現 daily 相同腳本序列，執行時間不變；失敗定位靠 step name |
| 2 | tw-etf 週日班寫 stocks.json（indicators/extras），與 tw-stock 不同日 | 跨日無同時寫入；push 序列化兜底 |
| 3 | us 拆分後兩 job 並行 06:30 | 不同檔（us-stocks vs us-etfs）、不同白名單、push 序列化 |
| 4 | workflow 層移除 concurrency 後 run 疊積 | due-only 判斷讓重複 run 快速跳過；job 層序列化保 push 安全 |
| 5 | 月任務（2/20 日）cron 失敗 | 21:00 補跑班 due-only 檢查資料檔日期→未完成即補 |
| 6 | 全部舊 cron 突然改表 | 新舊並行觀察一期不可行（cron 會重複跑）→改表後第一天盯 CI＋telegram 告警 |

**回退方案**：重構僅改 `daily-update.yml` 一個檔案（腳本零變更）→ `git revert <commit>` 即完整回到現架構；資料檔因 schema/路徑不變，新舊架構產物完全等價。

---

## 六、測試驗收計畫（Phase 2 確認後執行）

按規範第 8 節逐項：YAML 語法（actionlint）→ 五組獨立 workflow_dispatch 觸發 → all 觸發 → dry-run 無寫入驗證（比對 runner 前後 git status）→ 排程模擬（act 或本地 cron 條件單測）→ UTC/台北邊界 → 週末休市 → cron 遺漏補跑 → 冪等性（同組重複觸發第二次全 skip）→ 網路失敗注入 → Git 衝突/白名單（既有 test_known_errors 5 組注入測試）→ LKG 防回退 → 新舊輸出等價性（相同輸入比對 data/ tree hash）→ 前端健康檢查。

---

## 七、待您確認的決策點

| # | 決策 | Agent 建議 |
|---|---|---|
| D1 | global-market 一個 job 兩時段（17:30 indices／06:30 history）分流？ | ✓ 建議合併（同類資料、if 分流成熟） |
| D2 | etf-qa 週一班併入 tw-etf 17:30（星期條件分流）？ | ✓ 建議併入（cron 再少一條） |
| D3 | 移除 workflow 層 concurrency（改靠 due-only＋job 序列化）？ | ✓ 建議移除（消除補跑誤殺） |
| D4 | 新增 composite action（`.github/actions/setup/`）統一 checkout+python+pip 三步？ | 可選：YAML 再省 ~60 行，但多一個檔案——**傾向不加**（維持「不新增檔案」原則） |
| D5 | us-etf 每日 06:30 跑 etfs（現 us-market 一起跑）——維持每日頻率？ | ✓ 建議維持（Ivan 規劃 us-etf 每日行情+規模） |

**確認後進入 Phase 3/4 實作**（改 daily-update.yml＋本地測試＋report 更新），未經確認不 push。
