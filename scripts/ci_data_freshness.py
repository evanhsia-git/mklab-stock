#!/usr/bin/env python3
"""資料新鮮度守門（由 ci_commit_push.sh 在「合併後、推送前」呼叫）。

為什麼需要：
  多個 job 都會整檔重寫 data/stocks.json、data/industry.json，而 `git merge -X theirs`
  只認「合併當下的遠端」，**不比較資料日期**。2026-11-03 的事故就是這樣發生的：
  daily job 已把 stocks.json 推到 2026-11-02（history/industry 也已是 11-02），
  但另一個 job 的合併把較舊的 2026-10-30 版本選成結果 → 價格倒退一天，
  網站出現「stocks.json 說 10-30、industry.json 說 11-02」的不一致，5 項測試轉紅。

做法：
  對每個檔案比較三個候選的日期欄位（meta.as_of / as_of / date / last_updated）：
    1. working  目前工作檔（合併後的結果）
    2. HEAD@{1} 合併前的本機版本（本次 job 自己算出來的資料）
    3. origin/main 遠端版本
  若最新版本不是目前的工作檔，就改用最新版本（staged，由呼叫端 amend 進本次 commit）。
  只會讓資料前進，不會後退；無法解析日期的檔案一律不動。

用法：python3 scripts/ci_data_freshness.py data/stocks.json data/industry.json
"""
import json
import subprocess
import sys

DATE_FIELDS = ("as_of", "date", "last_updated", "updated")


def _date(text):
    if not text:
        return None
    try:
        doc = json.loads(text)
    except Exception:
        return None
    meta = doc.get("meta", doc) if isinstance(doc, dict) else {}
    if not isinstance(meta, dict):
        return None
    for k in DATE_FIELDS:
        v = meta.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _show(ref, path):
    r = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def main(paths):
    replaced = 0
    for p in paths:
        try:
            with open(p, encoding="utf-8") as f:
                working = f.read()
        except OSError:
            continue
        candidates = {"working": working}
        for ref in ("HEAD@{1}", "origin/main"):
            text = _show(ref, p)
            if text:
                candidates[ref] = text
        dates = {ref: _date(text) for ref, text in candidates.items()}
        dated = {ref: d for ref, d in dates.items() if d}
        if not dated:
            continue
        best = max(dated, key=lambda ref: dated[ref])
        if best == "working":
            print(f"[freshness] ✅ {p} 目前版本 {dated['working']} 已是最新"
                  + (f"（其他候選：{ {k: v for k, v in dated.items() if k != 'working'} }）" if len(dated) > 1 else ""))
            continue
        print(f"[freshness] ⚠️ {p} 目前版本 {dates.get('working')} 較舊 → 改用 {best} 的 {dated[best]}")
        subprocess.run(["git", "checkout", best, "--", p], check=True)
        replaced += 1
    if replaced:
        print(f"[freshness] 已回退 {replaced} 個會被資料倒退覆蓋的檔案（呼叫端需 amend 進本次 commit）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["data/stocks.json", "data/industry.json"]))
