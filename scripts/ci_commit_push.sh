#!/usr/bin/env bash
# MKLAB-STOCK CI publisher v2.1 — fail closed, no force push.
# Usage: bash scripts/ci_commit_push.sh "<message>" <path> [<path>...]
#
# 變更（相對 v2.0）：
# - QA 閘門固定為 scripts/ci_qa_gate.sh，移除 QA_GATE_PATH 覆寫（避免以替代腳本繞過 QA）。
# - 指定的路徑若不存在且未被 Git 追蹤，直接失敗（原本靜默略過會讓管線假成功）。
# - 合併遠端衝突時不再使用 -X theirs 自動挑選版本（會靜默丟棄本次新產生的資料），
#   改為中止並失敗，由人工或重新執行排程處理。
# - 空白 commit message 直接拒絕。
set -euo pipefail
export GIT_TERMINAL_PROMPT=0

log() { printf '[ci-push] %s\n' "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }
trap 'log "ERROR: command failed at line $LINENO" >&2' ERR

(( $# >= 2 )) || die 'Usage: ci_commit_push.sh "<message>" <path> [<path>...]'
MSG=$1
shift
[[ -n "${MSG//[[:space:]]/}" ]] || die 'Commit message must not be empty'

ROOT=$(git rev-parse --show-toplevel)
[[ "$(pwd -P)" == "$(cd "$ROOT" && pwd -P)" ]] || die 'Run from repository root'

FRESH=scripts/ci_data_freshness.py
QA=scripts/ci_qa_gate.sh
[[ -f "$FRESH" ]] || die "Missing freshness guard: $FRESH"
[[ -f "$QA" ]] || die "Missing QA gate: $QA"

git diff --cached --quiet || die 'Pre-existing staged changes; refusing mixed commit'
[[ -z $(git ls-files -u) ]] || die 'Unmerged paths exist'
for state in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply; do
    [[ ! -e $(git rev-parse --git-path "$state") ]] || die "Git operation in progress: $state"
done

git config user.name 'github-actions[bot]'
git config user.email 'github-actions[bot]@users.noreply.github.com'

# Every requested path must exist on disk or be tracked. Silent skipping would
# let a broken pipeline look successful.
paths=()
for p in "$@"; do
    if [[ -e "$p" || -L "$p" ]] || [[ -n $(git ls-files -- "$p") ]]; then
        paths+=("$p")
    else
        die "Path not found (neither on disk nor tracked): $p"
    fi
done

git add -- "${paths[@]}"
if git diff --cached --quiet; then
    log 'No changes to publish'
    exit 0
fi
# Unrelated unstaged edits would make the QA-checked candidate ambiguous.
git diff --quiet || die 'Unstaged tracked changes remain; refusing ambiguous candidate'
git commit -m "$MSG"

fetch_main() {
    git fetch --no-tags origin refs/heads/main:refs/remotes/origin/main
}

validate() {
    [[ -f "$FRESH" && -f "$QA" ]] || die 'Required guard missing after merge'

    # The freshness guard may stage corrections (restoring a newer valid copy).
    python3 "$FRESH" data/stocks.json data/industry.json || die 'Freshness guard failed'
    git diff --quiet || die 'Freshness guard left unstaged tracked changes'
    if ! git diff --cached --quiet; then
        # Separate commit keeps the audit trail for automatic corrections.
        git commit -m 'ci: apply freshness guard corrections'
    fi

    local checked
    checked=$(git rev-parse HEAD)
    bash "$QA" || die 'Post-merge QA failed'
    [[ $(git rev-parse HEAD) == "$checked" ]] || die 'QA changed HEAD'
    git diff --quiet && git diff --cached --quiet || die 'QA modified tracked files'
    [[ -z $(git ls-files -u) ]] || die 'Unmerged paths after QA'
}

for ((attempt = 1; attempt <= 5; attempt++)); do
    log "Attempt $attempt/5"
    fetch_main || die 'Fetch failed; remote baseline unavailable'
    remote=$(git rev-parse refs/remotes/origin/main)

    if ! git merge-base --is-ancestor "$remote" HEAD; then
        log 'Remote advanced; merging'
        # No -X strategy option: a content conflict aborts the run rather than
        # silently keeping one side's data.
        if ! git merge --no-edit "$remote"; then
            git merge --abort || log 'Merge abort failed; inspect local checkout'
            die 'Merge conflict with remote; no automatic resolution, no push attempted'
        fi
    fi

    validate
    git merge-base --is-ancestor "$remote" HEAD || die 'Candidate does not contain fetched remote baseline'

    # Non-fast-forward pushes are rejected atomically by the server.
    if git push origin HEAD:refs/heads/main; then
        log "Published $(git rev-parse HEAD)"
        exit 0
    fi
    if (( attempt < 5 )); then
        log "Push failed; retry after $((attempt * 5)) seconds"
        sleep $((attempt * 5))
    fi
done

die 'Push failed after 5 attempts; local commits retained for inspection'
