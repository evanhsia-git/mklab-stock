#!/usr/bin/env python3
"""一次性清理：把既有資料收斂到「上市一般股票 + 上市 ETF + 上櫃 ETF」。

為什麼需要：每日排程只會處理新資料；套用新版程式後，repo 裡已經存在的舊資料
（上櫃一般股票、權證、特別股、DR、受益證券、ETN）、舊的歷史快照、K 線檔，
以及過期的 ROE/ROA/EPS 殘值，需要用這支腳本清一次。可重複執行（idempotent）。

用法（在 repo 根目錄）：
    python3 scripts/purge_out_of_scope_data.py --dry-run   # 只統計，不改檔
    python3 scripts/purge_out_of_scope_data.py             # 實際執行

步驟：
 1. 從目前 data/stocks.json 找出「範圍外」代號（上櫃非 ETF、security_type=other）
 2. 依序重跑 integrate_official_company → import_official_fundamentals → compute_indicators
    → compute_industry → build_digest（與排程用的是同一批腳本）
 3. 從 data/history/*.json 移除範圍外代號；刪除 data/kline/<代號>.json
執行完請跑 tests 與 QA Gate 再 commit。
"""
import json, os, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DRY = "--dry-run" in sys.argv


def load_stocks():
    with open(os.path.join(ROOT, "data", "stocks.json"), encoding="utf-8") as f:
        return json.load(f)["stocks"]


def out_of_scope(rows):
    return {r["sym"] for r in rows
            if r.get("security_type") == "other"
            or (r.get("source") == "TPEX" and r.get("security_type") not in ("etf", "unverified"))}


def main():
    removed = out_of_scope(load_stocks())
    print(f"[purge] stocks.json 內範圍外證券：{len(removed)} 筆（上櫃一般股票／權證／特別股／DR／受益證券／ETN）")
    hist_dir = os.path.join(ROOT, "data", "history")
    kline_dir = os.path.join(ROOT, "data", "kline")
    n_files = n_rows = 0
    plan = []
    for fn in sorted(os.listdir(hist_dir)):
        if not fn.endswith(".json"):
            continue
        p = os.path.join(hist_dir, fn)
        raw = open(p, encoding="utf-8").read()
        d = json.loads(raw)
        keep = [r for r in d.get("stocks", []) if r.get("stock_id") not in removed]
        if len(keep) != len(d.get("stocks", [])):
            plan.append((p, raw, d, keep))
            n_files += 1
            n_rows += len(d["stocks"]) - len(keep)
    klines = [f for f in os.listdir(kline_dir) if f.endswith(".json") and f[:-5] in removed] if os.path.isdir(kline_dir) else []
    print(f"[purge] history：{n_files} 份快照共 {n_rows} 筆待移除；kline：{len(klines)} 個檔案待刪除")
    if DRY:
        print("[purge] --dry-run：不修改任何檔案")
        return
    for script in ("integrate_official_company", "import_official_fundamentals", "compute_indicators", "compute_industry", "build_digest"):
        print(f"[purge] 執行 {script}.py")
        subprocess.run([sys.executable, os.path.join(ROOT, "skills", "data", script + ".py")], cwd=ROOT, check=True)
    for p, raw, d, keep in plan:
        d["stocks"] = keep
        if "count" in d:
            d["count"] = len(keep)
        compact = "\n" not in raw.strip()
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, separators=(",", ":") if compact else None)
    for fn in klines:
        os.remove(os.path.join(kline_dir, fn))
    left = out_of_scope(load_stocks())
    print(f"[purge] 完成：stocks.json 範圍外證券剩 {len(left)} 筆（應為 0）")
    sys.exit(0 if not left else 1)


if __name__ == "__main__":
    main()
