#!/usr/bin/env bash
# MKLAB-STOCK CI publisher — fail closed, no force push.
# Usage: bash scripts/ci_commit_push.sh "<message>" <path> [<path>...]
# QA_GATE_PATH may override the default repository-relative QA entrypoint.
# Freshness guard retains its existing two-file interface until its implementation is audited.
set -euo pipefail
export GIT_TERMINAL_PROMPT=0
log() { printf '[ci-push] %s\n' "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }
trap 'log "ERROR: command failed at line $LINENO" >&2' ERR
(( $# >= 2 )) || die 'Usage: ci_commit_push.sh "<message>" <path> [<path>...]'
MSG=$1; shift
ROOT=$(git rev-parse --show-toplevel)
[[ "$PWD" == "$ROOT" ]] || die 'Run from repository root'
FRESH=scripts/ci_data_freshness.py
QA=${QA_GATE_PATH:-scripts/ci_qa_gate.sh}
[[ -f "$FRESH" ]] || die "Missing freshness guard: $FRESH"
[[ -f "$QA" ]] || die "Missing QA gate: $QA"
git diff --cached --quiet || die 'Pre-existing staged changes; refusing mixed commit'
[[ -z $(git ls-files -u) ]] || die 'Unmerged paths exist'
for state in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply; do
  [[ ! -e $(git rev-parse --git-path "$state") ]] || die "Git operation in progress: $state"
done
git config user.name 'github-actions[bot]'
git config user.email 'github-actions[bot]@users.noreply.github.com'
paths=()
for p in "$@"; do
  # Include tracked deletions and Git pathspec matches; never expand via eval.
  if [[ -e "$p" || -L "$p" ]] || [[ -n $(git ls-files -- "$p") ]]; then
    paths+=("$p")
  else
    log "Unmatched path skipped: $p"
  fi
done
(( ${#paths[@]} > 0 )) || { log 'No matching paths'; exit 0; }
git add -- "${paths[@]}"
git diff --cached --quiet && { log 'No changes'; exit 0; }
# Unrelated tracked changes could affect QA without being published.
git diff --quiet || die 'Unstaged tracked changes remain; refusing ambiguous candidate'
git commit -m "$MSG"
fetch_main() {
  git fetch --no-tags origin refs/heads/main:refs/remotes/origin/main
}
validate() {
  [[ -f "$FRESH" && -f "$QA" ]] || die 'Required guard missing after merge'
  # Existing guard may stage corrected data. Preserve that contract.
  python3 "$FRESH" data/stocks.json data/industry.json || die 'Freshness guard failed'
  git diff --quiet || die 'Freshness guard left unstaged tracked changes'
  if ! git diff --cached --quiet; then
    # Separate commit preserves merge ancestry and audit trail.
    git commit -m 'ci: apply freshness guard corrections'
  fi
  local checked
  checked=$(git rev-parse HEAD)
  bash "$QA" || die 'Post-merge QA failed'
  [[ $(git rev-parse HEAD) == "$checked" ]] || die 'QA changed HEAD'
  git diff --quiet && git diff --cached --quiet || die 'QA modified tracked data'
  [[ -z $(git ls-files -u) ]] || die 'Unmerged paths after QA'
}
for ((attempt=1; attempt<=5; attempt++)); do
  log "Attempt $attempt/5"
  fetch_main || die 'Fetch failed; remote baseline unavailable'
  remote=$(git rev-parse refs/remotes/origin/main)
  if ! git merge-base --is-ancestor "$remote" HEAD; then
    log 'Remote advanced; merging with remote preference on content conflicts'
    if ! git merge --no-edit -X theirs "$remote"; then
      git merge --abort || log 'Merge abort failed; inspect local checkout'
      die 'Merge failed; no push attempted'
    fi
  fi
  validate
  git merge-base --is-ancestor "$remote" HEAD || die 'Candidate does not contain fetched remote baseline'
  # Normal push rejects a concurrent non-fast-forward update atomically.
  if git push origin HEAD:refs/heads/main; then
    log "Published $(git rev-parse HEAD)"
    exit 0
  fi
  if (( attempt < 5 )); then
    log "Push failed; retry after $((attempt * 5)) seconds"
    sleep "$((attempt * 5))"
  fi
done
die 'Push failed after 5 attempts; local commits retained for inspection'
