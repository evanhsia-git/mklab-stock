#!/usr/bin/env bash
# 提交前 QA 閘門（P0-6）：資料 job 在 commit/push「之前」執行。
# 任何 Critical ERROR 都會讓 job 失敗，錯誤資料不會被推上 main（舊版是先推上去、再由另一個 workflow 檢查）。
set -uo pipefail
python3 skills/qa-gate/qa_gate.py --json qa-result.json || true   # 報告寫入 qa-result.json，判定交給 verdict
python3 scripts/ci_qa_verdict.py qa-result.json
