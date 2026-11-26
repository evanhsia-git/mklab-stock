# QA_ARCHITECTURE_CONSOLIDATION — 七檔整合為四檔交付報告

> 2026-11-26 完成。本地 commit `0400ac43`＋`7e22f1e5`，**未 push**（待人工驗收）。
> 基準 commit：`84b04ef9`。本輪授權範圍：盤點/整合/隔離測試/本地 commit。

## 1. 六（七）檔現行架構（整合前）

| 檔案 | 行數 | 職責 | 呼叫者 |
|---|---|---|---|
| scripts/ci_commit_push.sh | 112 | Git 推送守門 v2.1 | daily-update.yml ×10 |
| scripts/ci_data_freshness.py | 175 | 資料新鮮度守門 v2.1 | ci_commit_push.sh |
| scripts/ci_qa_gate.sh | 47 | QA 編排 v2.2 | daily-update.yml ×10、quality_sentinel、push 腳本 |
| scripts/ci_qa_verdict.py | 139 | 契約真值判定 v2.1 | ci_qa_gate.sh、qa-gate.yml |
| skills/qa-gate/qa_gate.py | 980 | 69 項檢查掃描器 | ci_qa_gate.sh、qa-gate.yml |
| skills/qa-gate/qa_checks.json | 37 | 契約單一真相源 | verdict、qa_gate 各自讀取 |
| tests/test_known_errors.py | 938 | 回歸 163 項＋Git 注入 | ci_qa_gate.sh |

## 2. 四檔整合架構（整合後）

| 檔案 | 行數 | 職責 |
|---|---|---|
| scripts/ci_commit_push.sh | 113 | Git 推送守門（呼叫 qa_gate.py --recover／--gate） |
| scripts/ci_qa_verdict.py | 175 | 契約單一真相源（_CONTRACT）＋獨立最終判定 |
| skills/qa-gate/qa_gate.py | 1194 | 掃描器＋freshness＋流程編排（統一 CLI 入口） |
| tests/test_known_errors.py | 1116 | 回歸 181 項（含契約一致性 18 情境＋Git 注入） |

核心檔案 **7→4（−42.9%）**；總行數 2,428→2,598（+170＝一致性測試 72＋CLI/遷移註解 ~100−舊檔註解）。**行數增加是刻意保留全部防護＋新增 18 項一致性測試**，非膨脹。

## 3. 函式遷移對照

| 原位置 | 新位置 | 狀態 |
|---|---|---|
| freshness：normalize_date／extract_date／plan_recovery／apply_recovery／DATE_FIELDS／3 個日期 regex | qa_gate.py（原樣遷移，_check_path 改局部 import 修 NameError） | ✓ 行為等價 |
| gate.sh：清舊報告→scan→verdict→regression 的編排 | qa_gate.py `_run_gate()`（scanner 改子進程 self-invoke，崩潰隔離與原版等價） | ✓ |
| qa_checks.json 全內容 | ci_qa_verdict.py `_CONTRACT` dict＋6 個模組級常數 | ✓ |
| qa_gate 讀 json 契約 | `from ci_qa_verdict import ...`（sys.path 插 ROOT/scripts；verdict 不 import qa_gate，無循環） | ✓ |

## 4. 統一執行入口（qa_gate.py）

| 模式 | 行為 | 讀/寫 | 呼叫者 |
|---|---|---|---|
| `--json <path>` | 唯讀掃描＋產報告（原行為） | 讀 | qa-gate.yml（不需改） |
| `--gate` | 完整閘門：清舊報告→scan→verdict→回歸，任一失敗即擋 | 讀＋寫 qa-result.json | daily-update ×10、quality_sentinel、push 腳本 |
| `--freshness [p..]` | 唯讀日期防回退判定 | **只讀** | 手動測試 |
| `--recover [p..]` | 兩階段恢復（預檢→寫入＋stage） | **寫入**（授權流程限定） | ci_commit_push.sh |

## 5. 消除的重複

- **契約三處→一處**：qa_checks.json＋verdict 讀檔＋qa_gate 讀檔 → verdict 模組常數單一來源（「修了 scanner 漏 verdict」類事故從結構上絕跡）
- **schema/required/總數常數**：兩端各 10 處引用改為同源 import
- **JSON 重複讀取**：freshness 的 extract_date 只解析候選檔 meta（本就最小化）；qa_gate scan 階段的多次 json.load 屬不同檔案不同目的（stocks/industry/etf-holdings/...），未發現同檔重讀
- **py_compile 兩輪**：未合併——檢視後確認兩輪分別驗 syntax 與不同檔案集合（合併會弱化每檔逐一歸因），保留

## 6. 保留的全部安全防護（逐項）

衝突中止不靜默挑版本 ✓／路徑白名單 fail closed ✓／有限重試 5 次 ✓／每次合併後完整 QA ✓／freshness 兩階段預檢 ✓／日期防回退 ✓／舊報告清除 ✓／scanner 非零一律拒（報告看起來有效也擋）✓／verdict 契約真值比對＋統計交叉重算 ✓／必要檢查漏跑防護（範圍下限 69−3）✓／MANUAL/WARNING 合法狀態不誤擋 ✓／QA 核心 QA_CORE 固定路徑不可覆寫 ✓／序列化 queue:max ✓／無 force push ✓

## 7. 契約一致性測試（方案 B，18 項新增）

契約同源斷言（is 同一物件）＋17 情境（各有獨立預期結果，非互相比對）：
ALLOW 類 5（69 全 PASS／WARNING-only／含 MANUAL／67 項下限內／71 項動態名合法）
BLOCK 類 12（ERROR 報告／偽造縮減 required／偽造 expected_checks／重複檢查名／統計不一致／allow_deploy 不一致／schema 錯／未知 status／65 項低於下限／報告損壞／重複 JSON key／NaN 常數）

教訓固化：合成報告必須含 required_checks 真實名稱（否則「必要檢查漏跑」攔截全部合成報告——開發時實證）。

## 8. 新舊 QA 結果比較（相同資料）

- 整合前（84b04ef9）：QA gate passed，回歸 163/163
- 整合後（7e22f1e5）：`--gate` 全鏈 passed，回歸 **181/181**（163 原有＋18 一致性）
- freshness 判定對照：stocks.json/industry.json 三候選日期比對結果一致（working 11-25 勝出、0 修正）
- Git 注入 5 組全過：恢復取最新／衝突中止無 MERGE_HEAD 殘留／重試 Attempt 2/5／未授權路徑拒推

## 9. 效能實測（本地，非 CI）

- `--gate` 全鏈（scan+verdict+回歸 181 項）：**18.1s**
- Python 程序啟動：--gate 模式 4 個（主體＋scanner self-invoke＋verdict＋regression；原 gate.sh 版同為 4 個——**持平**）
- JSON 載入：freshness 每候選 1 次（3 檔×3 候選）＝契約檔讀取 2 次歸零（原 verdict+qa_gate 各讀一次）
- stocks.json 容量：不變（1,363KB／此重構不觸資料）
- UNKNOWN：CI runner 上的時間（未 push，待部署後量測）

## 10. 剩餘風險

1. **workflows 本地改但未 push**——push 後第一次 CI 為真實驗收點
2. **quality_sentinel（本機哨兵）** 已改新入口——今晚 22:00 值哨即實證
3. **qa_gate.py 1194 行**接近單檔上限——後續 G01-G15 應以函式+data_rules 擴充，不再加檔案
4. **README／QA_CHECK_COVERAGE.md 仍引用舊檔名**（文檔層）——push 前更新

## 11. 正式部署建議

1. 人工 review `git show 0400ac43 --stat` 與 `7e22f1e5`
2. 授權 push →觀察 CI qa-gate run（新入口首跑）
3. 觀察 17:00 daily 班（10 job 全走 --gate）
4. 綠燈 24h 後本報告轉為正式架構記錄
