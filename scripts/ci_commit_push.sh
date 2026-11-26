#!/usr/bin/env bash
# MKLAB-STOCK CI publisher v2.2 — fail closed, no force push.
# Usage: bash scripts/ci_commit_push.sh "<message>" <path> [<path>...]
#
# 發布範圍（白名單）：data/ 與 rss.xml。其他路徑一律拒絕（與 daily-update.yml 的呼叫端一致）。
#
# 流程：stage 候選 → commit → fetch → 合併遠端（衝突即中止，不自動挑版本）
#       → --recover（日期防回退）→ --gate（完整 QA）→ push（非快進會被拒）→ 驗證遠端＝HEAD
#       被插隊時重試最多 5 次；每次重試都重新合併並重跑 QA。
#
# v2.2 變更（相對 v2.1）：
# - 新增發布路徑白名單（data/、rss.xml）；原文件宣稱有白名單但腳本未實作。
# - 本次無新變更時，仍會發布先前失敗遺留的本機 commit（原版會靜默 exit 0）。
# - 推送成功後以 ls-remote 驗證遠端 main 確實指向本機 HEAD。
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

QA_CORE=skills/qa-gate/qa_gate.py
[[ -f "$QA_CORE" ]] || die "Missing QA core: $QA_CORE"

git diff --cached --quiet || die 'Pre-existing staged changes; refusing mixed commit'
[[ -z $(git ls-files -u) ]] || die 'Unmerged paths exist'
for state in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply; do
    [[ ! -e $(git rev-parse --git-path "$state") ]] || die "Git operation in progress: $state"
done

git config user.name 'github-actions[bot]'
git config user.email 'github-actions[bot]@users.noreply.github.com'

# 路徑白名單（fail closed）：只允許 data/ 與 rss.xml；拒絕絕對路徑、上層跳脫、選項式參數。
allowed_path() {
    case "$1" in
        rss.xml|data|data/*) ;;
        *) return 1 ;;
    esac
    case "$1" in
        /*|*..*|-*) return 1 ;;
    esac
    return 0
}

paths=()
for p in "$@"; do
    allowed_path "$p" || die "Path outside publish whitelist (data/, rss.xml): $p"
    if [[ -e "$p" || -L "$p" ]] || [[ -n $(git ls-files -- "$p") ]]; then
        paths+=("$p")
    else
        die "Path not found (neither on disk nor tracked): $p"
    fi
done

fetch_main() {
    git fetch --no-tags origin refs/heads/main:refs/remotes/origin/main
}

git add -- "${paths[@]}"
if ! git diff --cached --quiet; then
    # 與本次候選無關的未暫存修改會讓 QA 檢查的對象不明確，拒絕。
    git diff --quiet || die 'Unstaged tracked changes remain; refusing ambiguous candidate'
    git commit -m "$MSG"
fi

# 本機是否有待發布的 commit（含先前失敗遺留者）；沒有才是真正的「無變更」。
fetch_main || die 'Fetch failed; remote baseline unavailable'
if (( $(git rev-list --count refs/remotes/origin/main..HEAD) == 0 )); then
    log 'No changes to publish'
    exit 0
fi

validate() {
    # 日期防回退（可能暫存較新的有效副本）。
    python3 "$QA_CORE" --recover data/stocks.json data/industry.json || die 'Freshness guard failed'
    git diff --quiet || die 'Freshness guard left unstaged tracked changes'
    if ! git diff --cached --quiet; then
        # 獨立 commit 保留自動修正的稽核軌跡。
        git commit -m 'ci: apply freshness guard corrections'
    fi

    local checked
    checked=$(git rev-parse HEAD)
    python3 "$QA_CORE" --gate || die 'Post-merge QA failed'
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
        # 不加 -X 策略參數：內容衝突即中止，不靜默保留任一方資料。
        if ! git merge --no-edit "$remote"; then
            git merge --abort || log 'Merge abort failed; inspect local checkout'
            die 'Merge conflict with remote; no automatic resolution, no push attempted'
        fi
    fi

    validate
    git merge-base --is-ancestor "$remote" HEAD || die 'Candidate does not contain fetched remote baseline'

    # 非快進推送由伺服器原子拒絕。
    if git push origin HEAD:refs/heads/main; then
        remote_now=$(git ls-remote --heads origin main | awk '{print $1}')
        [[ "$remote_now" == "$(git rev-parse HEAD)" ]] \
            || die "Post-push verification failed: remote main=$remote_now, local HEAD=$(git rev-parse HEAD)"
        log "Published $(git rev-parse HEAD)"
        exit 0
    fi
    if (( attempt < 5 )); then
        log "Push failed; retry after $((attempt * 5)) seconds"
        sleep $((attempt * 5))
    fi
done

die 'Push failed after 5 attempts; local commits retained for inspection'
