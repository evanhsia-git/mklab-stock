#!/usr/bin/env python3
"""清理：把既有資料收斂到「上市一般股票 + 上市 ETF + 上櫃 ETF」。

為什麼需要：每日排程只會處理新資料；套用新版程式後，repo 裡已經存在的舊資料
（上櫃一般股票、權證、特別股、DR、受益證券、ETN）、舊的歷史快照、K 線檔，
以及過期的 ROE/ROA/EPS 殘值，需要用這支腳本清一次。可重複執行（idempotent）。

用法（在 repo 根目錄）：
    python3 scripts/purge_out_of_scope_data.py --dry-run   # 只統計，不改檔
    python3 scripts/purge_out_of_scope_data.py             # 實際執行

步驟：
 1. 用「形狀規則」in_scope() 找出範圍外代號
 2. 依序重跑 integrate_official_company → import_official_fundamentals → compute_indicators
    → compute_industry → build_digest（與排程用的是同一批腳本）
 3. 從 data/history/*.json 移除範圍外代號；刪除 data/kline/<代號>.json
執行完請跑 tests 與 QA Gate 再 commit。

2026-11-10 修（原本這支腳本有兩個讓它無效的缺陷）：
 ① 舊版只用 stocks.json 的 security_type=="other" 推導範圍外清單 → 對「被錯誤分類成
    stock 的 DR（9103/9105/9110/9136）」完全無效。用同一個出錯的欄位來判斷，必然漏掉，
    實測 dry-run 會回報「0 筆」。
 ② 舊版只清「stocks.json 裡還在」的代號 → 早就被移出 stocks.json、卻仍殘留 history／kline
    的特別股（2891C、6592B）、受益證券（01001T）、ETN（0200xx）永遠清不掉
    （實測 317/321 份快照殘留 20,419 列、kline 12 檔）。
 現在改成：範圍判斷只看代號形狀（唯一來源 in_scope()），且對 stocks.json／history／kline
 各自獨立掃描，不再依賴任何可能出錯的分類欄位。
"""
import json, os, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DRY = "--dry-run" in sys.argv


def in_scope(sym):
    """本站範圍：上市一般股票（4 碼純數字、非 91xx）＋ ETF（00 開頭，允許字母尾碼如 00631L／00981A）。
    其餘（特別股 2881A、權證 72996U、DR 91xx、受益證券 01001T、ETN 0200xx）一律不收。

    ⚠️ 必須與 skills/data/fetch_data.py 的 classify_security()、skills/data/compute_indicators.py
    的分類段落同源；tests/test_known_errors.py 有跨檔一致性檢查，改一處就要改三處。
    """
    s = str(sym or "")
    if s.startswith("00"):
        return True
    return len(s) == 4 and s.isdigit() and not s.startswith("91")


def load_stocks():
    with open(os.path.join(ROOT, "data", "stocks.json"), encoding="utf-8") as f:
        return json.load(f)["stocks"]


def out_of_scope(rows):
    """stocks.json 內的範圍外代號：形狀不符，或上櫃且非 ETF（上櫃一般股票不收）。"""
    bad = set()
    for r in rows:
        s = str(r["sym"])
        if not in_scope(s):
            bad.add(s)
        elif r.get("source") == "TPEX" and r.get("security_type") not in ("etf", "unverified"):
            bad.add(s)
    return bad


def main():
    rows = load_stocks()
    removed = out_of_scope(rows)
    print(f"[purge] stocks.json 內範圍外證券：{len(removed)} 筆"
          f"（上櫃一般股票／權證／特別股／DR／受益證券／ETN）")

    hist_dir = os.path.join(ROOT, "data", "history")
    kline_dir = os.path.join(ROOT, "data", "kline")
    n_files = n_rows = 0
    other_syms = set()
    plan = []
    for fn in sorted(os.listdir(hist_dir)):
        if not fn.endswith(".json"):
            continue
        p = os.path.join(hist_dir, fn)
        raw = open(p, encoding="utf-8").read()
        d = json.loads(raw)
        before = d.get("stocks", [])
        keep = [r for r in before if in_scope(r.get("stock_id"))]
        if len(keep) != len(before):
            plan.append((p, raw, d, keep))
            n_files += 1
            n_rows += len(before) - len(keep)
            other_syms |= {str(r.get("stock_id")) for r in before if not in_scope(r.get("stock_id"))}

    klines = ([f for f in os.listdir(kline_dir) if f.endswith(".json") and not in_scope(f[:-5])]
              if os.path.isdir(kline_dir) else [])
    print(f"[purge] history：{n_files} 份快照共 {n_rows} 筆待移除；kline：{len(klines)} 個檔案待刪除")
    if other_syms:
        extra = sorted(other_syms - removed)
        print(f"[purge] 其中 {len(extra)} 個是「早已不在 stocks.json、卻仍殘留在 history／kline」"
              f"的代號，前 10 個：{extra[:10]}")
    if DRY:
        print("[purge] --dry-run：不修改任何檔案")
        return

    for script in ("integrate_official_company", "import_official_fundamentals", "compute_indicators",
                   "compute_industry", "build_digest"):
        print(f"[purge] 執行 {script}.py")
        subprocess.run([sys.executable, os.path.join(ROOT, "skills", "data", script + ".py")],
                       cwd=ROOT, check=True)

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
