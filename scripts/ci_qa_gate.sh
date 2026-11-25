#!/usr/bin/env bash
# MKLAB-STOCK QA gate v2.2 — fail closed.
# 保留 qa-result.json 與既有 verdict / known-errors 介面。
#
# 變更（相對 v2.1）：
# - 移除 QA_SCANNER_REPORT_EXIT_CODE 放行機制：掃描器非零退出一律拒絕發布，
#   不再允許以環境變數降低驗證標準。
# - 移除重複的 JSON 解析步驟；ci_qa_verdict.py 已做嚴格解析（重複 key、NaN/Infinity）。
# - 掃描器退出碼與 verdict 的先後順序：先由 verdict 給出阻擋原因，再檢查退出碼。
set -Eeuo pipefail

log() { printf '[qa-gate] %s\n' "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }
trap 'rc=$?; log "ERROR: unexpected failure at line $LINENO (exit $rc)" >&2; exit "$rc"' ERR

command -v git >/dev/null || die 'Missing git'
command -v python3 >/dev/null || die 'Missing python3'
ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || die 'Not inside a git repository'
[[ "$(pwd -P)" == "$(cd "$ROOT" && pwd -P)" ]] || die "Run from repository root ($ROOT)"

for script in skills/qa-gate/qa_gate.py scripts/ci_qa_verdict.py tests/test_known_errors.py; do
    [[ -f "$script" && -r "$script" ]] || die "Missing or unreadable $script"
done

REPORT=qa-result.json
rm -f -- "$REPORT" || die 'Cannot remove stale QA report'
[[ ! -e "$REPORT" && ! -L "$REPORT" ]] || die 'Stale QA report remains'

log '1/3 Generate QA report'
scan_rc=0
python3 skills/qa-gate/qa_gate.py --json "$REPORT" || scan_rc=$?
[[ -f "$REPORT" && ! -L "$REPORT" && -s "$REPORT" ]] \
    || die "Missing, empty or unsafe QA report (scanner exit $scan_rc)"

log '2/3 Evaluate QA verdict'
python3 scripts/ci_qa_verdict.py "$REPORT" || { rc=$?; log "BLOCK: verdict exit $rc" >&2; exit "$rc"; }

# The verdict only inspects the report. A nonzero scanner exit still means the
# scanner did not complete cleanly, so it must block even if the report looks valid.
if (( scan_rc != 0 )); then
    die "Scanner exited $scan_rc despite a passing verdict; refusing publication"
fi

log '3/3 Run known-error regression tests'
python3 tests/test_known_errors.py || { rc=$?; log "BLOCK: regression tests exit $rc" >&2; exit "$rc"; }

log 'QA gate passed'
