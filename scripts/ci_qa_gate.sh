#!/usr/bin/env bash
# MKLAB-STOCK QA gate v2.1 — fail closed.
# 保留 qa-result.json 與既有 verdict / known-errors 介面。
# 預設拒絕掃描器非零退出；確認退出碼契約後才可明確允許特定退出碼。
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
# Optional, exact scanner status only; never bypass verdict or tests.
# Leave unset unless the scanner's documented contract has been verified.
ALLOWED=${QA_SCANNER_REPORT_EXIT_CODE:-0}
[[ "$ALLOWED" =~ ^(0|[1-9][0-9]?)$ ]] || die 'Invalid QA_SCANNER_REPORT_EXIT_CODE (expected 0-99)'
rm -f -- "$REPORT" || die 'Cannot remove stale QA report'
[[ ! -e "$REPORT" && ! -L "$REPORT" ]] || die 'Stale QA report remains'
log '1/4 Generate QA report'
scan_rc=0
python3 skills/qa-gate/qa_gate.py --json "$REPORT" || scan_rc=$?
[[ -f "$REPORT" && ! -L "$REPORT" && -s "$REPORT" ]] || die "Missing, empty or unsafe QA report (scanner exit $scan_rc)"
log '2/4 Validate JSON report'
python3 - "$REPORT" <<'PY' || die 'Invalid QA JSON report'
import json
import sys

def reject_constant(value):
    raise ValueError(f'Invalid JSON constant: {value}')

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result

with open(sys.argv[1], encoding='utf-8') as stream:
    report = json.load(stream, parse_constant=reject_constant, object_pairs_hook=unique_object)
if not isinstance(report, dict) or not report:
    raise ValueError('Expected a nonempty JSON object')
PY
log '3/4 Evaluate QA verdict'
python3 scripts/ci_qa_verdict.py "$REPORT" || { rc=$?; log "BLOCK: verdict exit $rc" >&2; exit "$rc"; }
if (( scan_rc != 0 )); then
    [[ "$scan_rc" == "$ALLOWED" ]] || die "Scanner exited $scan_rc despite passing verdict; refusing publication"
    log "WARNING: scanner exit $scan_rc explicitly permitted; verdict passed"
fi
log '4/4 Run known-error regression tests'
python3 tests/test_known_errors.py || { rc=$?; log "BLOCK: regression tests exit $rc" >&2; exit "$rc"; }
log 'QA gate passed'
