#!/usr/bin/env bash
# CI 專用：提交並推送資料變更。
# daily-update.yml 的 8 個 job 共用這一份，避免每個 job 各寫一套、下次修正又只改到一半。
#
# 用法：bash scripts/ci_commit_push.sh "<commit message>" <path> [<path>...]
#
# 為什麼不能只寫 git pull --no-rebase origin main -X ours：
#   1. 本 job 的 checkout 可能在資料抓取期間就過時了。例如 weekly-roe 要跑約 64 分鐘，
#      期間 daily job 早已把新資料推上去；如果舊 checkout 的檔案版本勝出，就會把
#      較新的遠端資料覆蓋回舊的 —— 2026-11-02 就是這樣讓 stocks.json 的
#      as_of 由 10-30（bot daily 07:02 推的）退回 10-27（weekly-roe 08:03 推的）。
#   2. 所以合併遠端時，衝突一律取「遠端」(theirs)。遠端是較晚寫入的版本；最壞情況
#      只是本輪這個 job 的更新被捨棄（下一輪會重算），但資料永遠不會倒退。
#   3. push 之間仍可能被其他 job 插隊 → 重試 5 次（遞增等待），每次重試前重新合併遠端。
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo '用法：bash scripts/ci_commit_push.sh "<commit message>" <path> [<path>...]' >&2
  exit 2
fi
MSG="$1"
shift

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

# 只加入實際存在的路徑：glob（如 data/us-history-*）沒有匹配時會保留字面字串，git add 會直接失敗
paths=()
for p in "$@"; do
  if compgen -G "$p" > /dev/null || [ -e "$p" ]; then paths+=("$p"); fi
done
if [ "${#paths[@]}" -eq 0 ]; then
  echo "no paths to add (全部路徑不存在)"
  exit 0
fi
git add -- "${paths[@]}"
if git diff --cached --quiet; then
  echo "no changes"
  exit 0
fi
git commit -m "$MSG"

# 資料新鮮度守門（必須放在「合併後、推送前」）：
#   -X theirs 只認「合併當下的遠端」，不比較資料日期 → 較舊的整檔重寫可能勝出。
#   2026-11-03 事故：official-fundamentals job 的 stocks.json（as_of 10-30）在合併時
#   勝過 daily job 已推上去的 11-02，導致價格倒退一天、與 history/industry 不一致。
#   這裡比較 working／HEAD@{1}（合併前本機）／origin/main 三者的日期，只採最新版本。
guard_freshness() {
  [ -f scripts/ci_data_freshness.py ] || return 0
  python3 scripts/ci_data_freshness.py data/stocks.json data/industry.json || true
  if ! git diff --cached --quiet; then
    git commit --amend --no-edit >/dev/null
    echo "[freshness] 已把最新版本併回本次 commit"
  fi
}

git fetch origin main   # 一定要先 fetch，否則本機的 origin/main 參照是舊的，會誤判成「遠端沒新東西」
if git merge-base --is-ancestor origin/main HEAD; then
  : # 遠端沒有新東西
else
  echo "遠端領先（其他 job 先推了），合併 origin/main：衝突取遠端較新版本"
  if ! git merge --no-edit -X theirs origin/main; then
    git merge --abort || true
    echo "❌ 合併 origin/main 失敗（非內容衝突，可能是檔案刪改衝突），本次放棄推送" >&2
    exit 1
  fi
fi
guard_freshness

n=0
until [ "$n" -ge 5 ]; do
  if git push origin HEAD:main; then
    echo "✅ 已推送 $(git rev-parse --short HEAD)"
    exit 0
  fi
  n=$((n + 1))
  echo "⚠️ push 失敗，重試 $n/5（等 $((n * 5)) 秒後重新合併遠端）"
  sleep $((n * 5))
  git pull --no-rebase origin main -X theirs --no-edit || true
  guard_freshness
done

echo "❌ push 連續失敗 5 次" >&2
exit 1
