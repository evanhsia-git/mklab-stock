#!/usr/bin/env python3
"""LKG (Last Known Good) manager v1.1 — 同 SHA 驗證＋晉升 dry-run/apply.

設計約束（Data Protection v2.1）：
- QA run、Pages deployment、線上資料、Tag、Manifest 必須對應同一 commit SHA。
- 晉升證據由本腳本自行驗證（gh api 查 run/deployment），不信任外部傳入旗標。
- 線上資料從候選 SHA 讀取核心檔案計算 SHA256，與線上下載內容逐一比較（有限重試）。
- Git Tag 不得強制覆蓋（tag 已存在→跳過晉升）。
- Manifest 存獨立 metadata 分支（refs/heads/ci-metadata），不觸發網站部署。
- 不複製大型 JSON：manifest 只記 sha256/size/records/asof。
- 舊 workflow 晚完成不得覆蓋較新 LKG：non-fast-forward push＋祖先檢查雙重鎖。
- Tag 已存在但 Manifest 缺失/不一致 → 不視為完整可用 LKG（--status 判定）。
- 預設 dry-run：任何寫入（tag/manifest/push）需 --apply。
"""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request

SCHEMA_VERSION = "1.1"
METADATA_BRANCH = "ci-metadata"
ONLINE_FILES = (
    "data/stocks.json",
    "data/industry.json",
    "data/etf-holdings.json",
    "data/digest/index.json",
    "data/us/us-stocks.json",
)
RECORDS_KEYS = {
    "data/stocks.json": "stocks",
    "data/industry.json": "industries",
    "data/etf-holdings.json": "holdings",
    "data/digest/index.json": None,
    "data/us/us-stocks.json": None,
}
BASE_URL = os.environ.get("MKLAB_ONLINE_BASE", "https://evanhsia-git.github.io/mklab-stock/")
ONLINE_RETRY = 3


def sh(*args, cwd=None, check=True, input=None):
    r = subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, input=input)
    if check and r.returncode:
        raise RuntimeError(f"{' '.join(args[:2])}: {r.stderr.strip()}")
    return r


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True)


def sha256_raw(raw):
    return hashlib.sha256(raw).hexdigest()


def records_of(rel, doc):
    key = RECORDS_KEYS.get(rel)
    if key is None:
        return len(doc) if isinstance(doc, (list, dict)) else None
    v = doc.get(key)
    return len(v) if isinstance(v, (list, dict)) else None


def verify_evidence(sha):
    """晉升證據自驗：QA run 與 Pages deployment 的 SHA 必須與候選一致且成功。

    Returns dict(evidence_ok, qa_run_id, pages_id, pages_sha, details)。
    """
    ev = {"qa_ok": False, "pages_ok": False, "details": []}
    # 1) QA run：qa-gate workflow 對本 SHA 最新一次 conclusion=success
    r = gh("run", "list", "--workflow=qa-gate.yml", "--limit", "20", "--json",
           "headSha,conclusion,databaseId,status")
    if r.returncode == 0 and r.stdout.strip():
        runs = [x for x in json.loads(r.stdout) if x.get("headSha") == sha]
        good = [x for x in runs if x.get("conclusion") == "success"]
        if good:
            ev["qa_ok"] = True
            ev["qa_run_id"] = good[0]["databaseId"]
        else:
            ev["details"].append(f"qa-gate run for {sha[:12]}: no successful run ({len(runs)} found)")
    else:
        ev["details"].append(f"gh run list failed: {r.stderr.strip()[:120]}")
    # 2) Pages deployment：最新部署的 source SHA 必須等於候選
    r = gh("api", "repos/{owner}/{repo}/deployments", "-X", "GET",
           "-f", "environment=github-pages", "-f", "per_page=5",
           "--jq", '[.[] | {sha: .sha, id: .id}]')
    if r.returncode == 0 and r.stdout.strip():
        deploys = json.loads(r.stdout)
        if deploys:
            latest = deploys[0]
            ev["pages_id"] = latest["id"]
            ev["pages_sha"] = latest["sha"]
            ev["pages_ok"] = latest["sha"] == sha
            if not ev["pages_ok"]:
                ev["details"].append(f"pages source {latest['sha'][:12]} != candidate {sha[:12]}")
    else:
        ev["details"].append(f"gh api deployments failed: {r.stderr.strip()[:120]}")
    ev["evidence_ok"] = ev["qa_ok"] and ev["pages_ok"]
    return ev


def online_with_retry(rel):
    last = None
    for attempt in range(1, ONLINE_RETRY + 1):
        try:
            url = BASE_URL + rel + f"?cb={time.time_ns()}"
            with urllib.request.urlopen(url, timeout=30) as resp:
                return resp.read()
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
            if attempt < ONLINE_RETRY:
                time.sleep(2 * attempt)
    raise RuntimeError(f"online fetch failed after {ONLINE_RETRY} tries: {rel} ({last})")


def verify_online(sha):
    """線上資料驗證：從候選 SHA 讀核心檔，計算 SHA256，與線上下載內容比較。"""
    files, ok = {}, True
    for rel in ONLINE_FILES:
        entry = {}
        local = sh("git", "show", f"{sha}:{rel}", check=False)
        if local.returncode or not local.stdout:
            files[rel] = {"readable": False, "error": f"not in commit {sha[:12]}"}
            ok = False
            continue
        local_sha = sha256_raw(local.stdout.encode("utf-8"))
        try:
            online_raw = online_with_retry(rel)
            online_sha = sha256_raw(online_raw)
            same = local_sha == online_sha
            entry = {"readable": True, "same_sha256": same,
                     "sha256": online_sha, "size": len(online_raw)}
            if not same:
                ok = False
            try:
                doc = json.loads(online_raw.decode("utf-8"))
                entry["asof"] = (doc.get("meta") or {}).get("as_of") or doc.get("date") or doc.get("month")
                entry["records"] = records_of(rel, doc)
            except ValueError:
                entry["readable"] = False
                entry["error"] = "online content not valid JSON"
                ok = False
        except RuntimeError as exc:
            entry = {"readable": False, "error": str(exc)}
            ok = False
        files[rel] = entry
    return ok, files


def promote(sha, apply_mode):
    tag = f"lkg/{sha[:12]}"
    steps = []
    # 1) 晉升證據自驗（QA＋Pages 同 SHA 且成功）
    ev = verify_evidence(sha)
    steps.append(("evidence_qa_pages_same_sha", ev["evidence_ok"]))
    if not ev["evidence_ok"]:
        return {"promoted": False, "reason": "evidence verification failed",
                "evidence": ev, "steps": steps}
    # 2) 線上資料＝候選 SHA 內容（SHA256 逐檔比較，有限重試）
    online_ok, files = verify_online(sha)
    steps.append(("online_matches_commit", online_ok))
    if not online_ok:
        return {"promoted": False, "reason": "online content does not match candidate commit",
                "evidence": ev, "files": files, "steps": steps}
    # 3) Tag 不強制覆蓋
    exists = sh("git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}", check=False).returncode == 0
    steps.append(("tag_exists", exists))
    if exists:
        return {"promoted": False, "reason": f"tag {tag} already exists (no force)",
                "evidence": ev, "files": files, "steps": steps}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "lkg": {"sha": sha, "tag": tag,
                "verified_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                "promoted_at": None,
                "qa_run_id": ev.get("qa_run_id"),
                "pages_deployment_id": ev.get("pages_id"),
                "pages_source_sha": ev.get("pages_sha")},
        "verify": {"online_json": online_ok, "files": files},
    }
    result = {"promoted": False, "tag": tag, "manifest": manifest, "dry_run": not apply_mode,
              "evidence": ev, "files": files, "steps": steps}
    if not apply_mode:
        result["would"] = [f"git tag {tag} {sha}",
                           f"manifest commit → push refs/heads/{METADATA_BRANCH} (non-fast-forward)"]
        return result
    # 4) 建立本地 tag（rev-parse 已確認不存在；絕不 -f）
    sh("git", "tag", tag, sha)
    manifest["lkg"]["promoted_at"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    blob = sh("git", "hash-object", "-w", "--stdin",
              input=json.dumps(manifest, ensure_ascii=False, indent=2)).stdout.strip()
    tree = sh("git", "mktree", input=f"100644 blob {blob}\tlkg-manifest.json\n").stdout.strip()
    # 5) Manifest → metadata 分支：以 remote 頂端為基底；祖先檢查（舊 job 晚完成防護）
    parent = []
    base_ref = sh("git", "rev-parse", "-q", "--verify", f"refs/remotes/origin/{METADATA_BRANCH}", check=False)
    if base_ref.returncode == 0:
        parent = [base_ref.stdout.strip()]
        try:
            current = json.loads(sh("git", "show", f"{parent[0]}:lkg-manifest.json").stdout)
            cur_sha = (current.get("lkg") or {}).get("sha")
            if cur_sha and cur_sha != sha and sh("git", "merge-base", "--is-ancestor", sha, cur_sha, check=False).returncode == 0:
                sh("git", "tag", "-d", tag)
                result["reason"] = f"newer LKG {cur_sha[:12]} already recorded; stale job aborts"
                result["steps"].append(("optimistic_lock", False))
                return result
        except RuntimeError:
            pass
    result["steps"].append(("optimistic_lock", True))
    commit_args = ["git", "commit-tree", tree, "-m", f"ci: promote LKG {tag}"]
    if parent:
        commit_args += ["-p", parent[0]]
    commit = sh(*commit_args, input="").stdout.strip()
    result["manifest_commit"] = commit
    # 6) 原子推送（non-fast-forward：並行晉升時後到者被 git 拒絕→重試一次→放棄）
    pushed = []
    for spec in (f"refs/tags/{tag}", f"{commit}:refs/heads/{METADATA_BRANCH}"):
        if sh("git", "push", "origin", spec, check=False).returncode != 0:
            sh("git", "fetch", f"+refs/heads/{METADATA_BRANCH}:refs/remotes/origin/{METADATA_BRANCH}", check=False)
            if sh("git", "push", "origin", spec, check=False).returncode != 0:
                result["reason"] = f"push rejected (non-fast-forward / concurrent promotion): {spec}"
                result["promoted"] = False
                result["pushed"] = pushed
                result["steps"].append(("atomic_push", False))
                return result
        pushed.append(spec)
    result["pushed"] = pushed
    result["steps"].append(("atomic_push", True))
    result["promoted"] = True
    return result


def status():
    """判定現行 LKG 是否完整可用：tag 存在＋manifest 完整＋兩者 SHA 一致＋線上驗證通過。"""
    mref = sh("git", "rev-parse", "-q", "--verify", f"refs/remotes/origin/{METADATA_BRANCH}", check=False)
    if mref.returncode != 0:
        return {"usable": False, "reason": f"no {METADATA_BRANCH} branch"}
    m = json.loads(sh("git", "show", f"{mref.stdout.strip()}:lkg-manifest.json").stdout)
    l = m.get("lkg") or {}
    sha, tag = l.get("sha"), l.get("tag")
    if not (m.get("schema_version") and sha and tag and (m.get("verify") or {}).get("online_json") is True):
        return {"usable": False, "reason": "manifest incomplete"}
    if sh("git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}", check=False).returncode != 0:
        return {"usable": False, "reason": f"tag {tag} missing (manifest alone is not a usable LKG)"}
    if sh("git", "rev-parse", f"refs/tags/{tag}^{{commit}}").stdout.strip() != sha:
        return {"usable": False, "reason": "tag SHA != manifest sha"}
    ok, files = verify_online(sha)
    if not ok:
        return {"usable": False, "reason": "online content no longer matches LKG commit"}
    return {"usable": True, "lkg": l, "files": files}


def main(argv=None):
    ap = argparse.ArgumentParser(description="LKG manager v1.1")
    ap.add_argument("--sha", default=os.environ.get("GITHUB_SHA") or sh("git", "rev-parse", "HEAD").stdout.strip())
    ap.add_argument("--apply", action="store_true", help="實際建立 tag 與 manifest（預設 dry-run）")
    ap.add_argument("--verify-only", action="store_true", help="僅執行線上資料驗證")
    ap.add_argument("--status", action="store_true", help="判定現行 LKG 是否完整可用")
    args = ap.parse_args(argv)
    if args.verify_only:
        ok, files = verify_online(args.sha)
        print(json.dumps({"online_ok": ok, "files": files}, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    if args.status:
        out = status()
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out.get("usable") else 1
    out = promote(args.sha, args.apply)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("promoted") or out.get("dry_run") else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
