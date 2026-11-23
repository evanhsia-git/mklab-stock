#!/usr/bin/env bash
# 提交前 QA 閘門（P0-6）：資料 job 在 commit/push「之前」執行。
# 任何 Critical ERROR 都會讓 job 失敗，錯誤資料不會被推上 main（舊版是先推上去、再由另一個 workflow 檢查）。
set -uo pipefail
python3 skills/qa-gate/qa_gate.py --json qa-result.json || true   # 報告寫入 qa-result.json，判定交給 verdict
python3 scripts/ci_qa_verdict.py qa-result.json
# 2026-11-23：加跑已知錯誤防錯測試（P0-1 分類一致性、核心 ETF 存在性等 150+ 項只在此層）。
# 2026-11-22 etf-meta 班曾把缺 0050 的 stocks.json 推上 main 而本閘門無感（僅 push 後的
# qa-gate.yml 才跑 test_known_errors）——排程 job 的閘門必須與 push 閘門同級。
if [ -f tests/test_known_errors.py ]; then
  python3 tests/test_known_errors.py || exit 1
fi
