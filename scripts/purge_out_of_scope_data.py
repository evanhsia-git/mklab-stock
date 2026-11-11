#!/usr/bin/env python3
"""清理：把既有資料收斂到「上市一般股票 + 上市 ETF + 上櫃 ETF」。

為什麼需要：每日排程只會處理新資料；套用新版程式後，repo 裡已經存在的舊資料、
舊的歷史快照、K 線檔、以及各衍生 store 裡的範圍外代號，需要用這支腳本清一次。
可重複執行（idempotent）。

用法（在 repo 根目錄）：
    python3 scripts/purge_out_of_scope_data.py --dry-run   # 只統計，不改檔
    python3 scripts/purge_out_of_scope_data.py             # 實際執行

範圍規則的唯一來源：skills/data/scope_rules.py 的 in_scope()（勿在本檔另寫一份）。

步驟：
 1. 用 in_scope() 掃出範圍外代號
 2. 依序重跑 integrate_official_company → import_official_fundamentals → compute_indicators
    → compute_industry → build_digest（與排程用的是同一批腳本）
 3. 清 data/history/*.json、刪 data/kline/<代號>.json
 4. 清衍生 store 的範圍外鍵：data/etf-shares.json、data/official-fundamentals.json
 5. 修 data/digest/*.json 榜單裡的範圍外代號（能忠實驗證就重算，否則只移除）

執行完請跑 tests 與 QA Gate 再 commit。

2026-11-10/11 修（這支腳本原本完全無效，三個缺陷）：
 ① 舊版只用 stocks.json 的 security_type=="other" 推導清單 → 對「被錯誤分類成 stock 的
    DR（9103/9105/9110/9136）」無效。用同一個出錯的欄位判斷，必然漏（dry-run 回報 0 筆）。
 ② 舊版只清「stocks.json 裡還在」的代號 → 早已被移出的特別股（2891C／6592B）、受益證券
    （01001T）、ETN（0200xx）永遠留在 history／kline（實測 317/321 份殘留 20,419 列、kline 12 檔）。
 ③ 舊版不碰衍生 store 與 digest 榜單 → official-fundamentals.json 的 .dividend 每次由官方
    t187ap45 重建（該檔含特別股），28 個特別股死鍵反覆長回來；etf-shares.json 留著 14 個；
    digest 榜單還會把 ETN（02001L）或 DR 列給使用者看。
"""
import json, os, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "skills", "data"))
from scope_rules import in_scope  # noqa: E402  # type: ignore[import-not-found]

DRY = "--dry-run" in sys.argv
HIST_DIR = os.path.join(ROOT, "data", "history")
KLINE_DIR = os.path.join(ROOT, "data", "kline")
DIGEST_DIR = os.path.join(ROOT, "data", "digest")
# 以代號為鍵的衍生 store（寫入端都必須過 in_scope，否則範圍外證券會慢慢長回來）
STORES = (("data/etf-shares.json", ("etf",)),
          ("data/official-fundamentals.json", ("financial", "dividend")))
RANK_KEYS = ("top_gainers", "top_losers", "top_score")


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def dump_json(path, obj, compact=None):
    if compact is None:
        compact = "\n" not in open(path, encoding="utf-8").read().strip()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False,
                  separators=(",", ":") if compact else None,
                  indent=None if compact else 2)


def out_of_scope_in_stocks():
    """stocks.json 內的範圍外代號：形狀不符，或上櫃且非 ETF（上櫃一般股票不收）。"""
    doc = load_json(os.path.join(ROOT, "data", "stocks.json"), {})
    bad = set()
    for r in doc.get("stocks", []):
        s = str(r.get("sym", ""))
        if not in_scope(s):
            bad.add(s)
        elif r.get("source") == "TPEX" and r.get("security_type") not in ("etf", "unverified"):
            bad.add(s)
    return bad


def digest_bad_syms():
    """回傳 {digest檔路徑: [範圍外代號]}。"""
    out = {}
    if not os.path.isdir(DIGEST_DIR):
        return out
    for fn in sorted(os.listdir(DIGEST_DIR)):
        if not fn.endswith(".json") or fn == "index.json":
            continue
        p = os.path.join(DIGEST_DIR, fn)
        d = load_json(p, {})
        bad = sorted({x.get("sym") for k in RANK_KEYS for x in (d.get(k) or [])
                      if not in_scope(x.get("sym"))})
        if bad:
            out[p] = bad
    return out


def fix_digest(point, hist_snap, days):
    """修一份 digest 的榜單，回傳說明字串。

    能忠實驗證就重算：非範圍外項目必須與原檔逐值一致（容差 0.01）才寫入。
    為什麼不能一律重算 —— 原值是用 stocks.json 的 TWSE 官方 chg 算的，而 history 沒有 chg 欄；
    實測重算會有 0.06 級差異（電機機械 1.38 vs 原 1.32），那種情況只能移除、不可回填推測值。
    """
    dt = os.path.basename(point)[:-5]
    if dt not in days:
        return f"{dt}: history 無此日 → 只移除"
    i = days.index(dt)
    pv, cur = hist_snap[days[i - 1]], hist_snap[dt]
    rows = [{"sym": s, "chg": round((c - pv[s]) / pv[s] * 100, 2)}
            for s, c in cur.items()
            if in_scope(s) and not str(s).startswith("00")
            and isinstance(c, (int, float)) and isinstance(pv.get(s), (int, float)) and pv[s]]
    d = load_json(point, {})
    notes = []
    for key, rev in (("top_gainers", True), ("top_losers", False), ("top_score", None)):
        items = d.get(key) or []
        bad = [x.get("sym") for x in items if not in_scope(x.get("sym"))]
        if not bad:
            continue
        if rev is not None and dt in days:
            orig = {x["sym"]: x.get("chg") for x in items if in_scope(x.get("sym"))}
            new = {x["sym"]: x["chg"] for x in sorted(rows, key=lambda r: r["chg"], reverse=rev)[:5]}
            if set(orig) <= set(new) and all(abs(new[k] - v) < 0.011 for k, v in orig.items()):
                nm = {str(r["stock_id"]): r.get("stock_name")
                      for r in load_json(os.path.join(HIST_DIR, dt + ".json"), {}).get("stocks", [])}
                d[key] = [{"sym": x["sym"], "name": nm.get(x["sym"]), "chg": x["chg"]}
                          for x in sorted(rows, key=lambda r: r["chg"], reverse=rev)[:5]]
                notes.append(f"{key} 重算（驗證通過，{bad} → 由下一名遞補）")
                continue
        d[key] = [x for x in items if in_scope(x.get("sym"))]
        notes.append(f"{key} 只移除 {bad}（無法忠實驗證，不回填推測值）")
    dump_json(point, d, compact=False)
    return f"{dt}: " + "；".join(notes)


def main():
    removed = out_of_scope_in_stocks()
    print(f"[purge] stocks.json 內範圍外證券：{len(removed)} 筆"
          f"（上櫃一般股票／權證／特別股／DR／受益證券／ETN）")

    # ---- history / kline ----
    n_files = n_rows = 0
    other_syms, plan = set(), []
    for fn in sorted(os.listdir(HIST_DIR)):
        if not fn.endswith(".json"):
            continue
        p = os.path.join(HIST_DIR, fn)
        raw = open(p, encoding="utf-8").read()
        d = json.loads(raw)
        before = d.get("stocks", [])
        keep = [r for r in before if in_scope(r.get("stock_id"))]
        if len(keep) != len(before):
            plan.append((p, raw, d, keep))
            n_files += 1
            n_rows += len(before) - len(keep)
            other_syms |= {str(r.get("stock_id")) for r in before if not in_scope(r.get("stock_id"))}
    klines = ([f for f in os.listdir(KLINE_DIR) if f.endswith(".json") and not in_scope(f[:-5])]
              if os.path.isdir(KLINE_DIR) else [])
    print(f"[purge] history：{n_files} 份快照共 {n_rows} 筆待移除；kline：{len(klines)} 個檔案待刪除")
    if other_syms:
        extra = sorted(other_syms - removed)
        print(f"[purge] 其中 {len(extra)} 個是「早已不在 stocks.json、卻仍殘留在 history／kline」的"
              f"代號，前 10 個：{extra[:10]}")

    # ---- 衍生 store ----
    store_plan = []
    for rel, secs in STORES:
        p = os.path.join(ROOT, rel)
        d = load_json(p)
        if not d:
            continue
        for sec in secs:
            sub = d.get(sec)
            if isinstance(sub, dict):
                bad = sorted(k for k in sub if not in_scope(k))
                if bad:
                    store_plan.append((p, d, sec, bad))
                    print(f"[purge] {rel} .{sec}：{len(bad)} 個範圍外鍵待移除"
                          f"（{bad[:6]}{'…' if len(bad) > 6 else ''}）")

    # ---- digest ----
    dig_bad = digest_bad_syms()
    for p, bad in dig_bad.items():
        print(f"[purge] {os.path.relpath(p, ROOT)}：榜單含範圍外代號 {bad}")

    if DRY:
        print("[purge] --dry-run：不修改任何檔案")
        return

    # ---- 先重跑管線（與排程同一批） ----
    for script in ("integrate_official_company", "import_official_fundamentals", "compute_indicators",
                   "compute_industry", "build_digest"):
        print(f"[purge] 執行 {script}.py")
        subprocess.run([sys.executable, os.path.join(ROOT, "skills", "data", script + ".py")],
                       cwd=ROOT, check=True)

    # ---- history / kline ----
    for p, raw, d, keep in plan:
        d["stocks"] = keep
        if "count" in d:
            d["count"] = len(keep)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False,
                      separators=(",", ":") if "\n" not in raw.strip() else None)
    for fn in klines:
        os.remove(os.path.join(KLINE_DIR, fn))

    # ---- 衍生 store ----
    for p, d, sec, bad in store_plan:
        for k in bad:
            del d[sec][k]
        dump_json(p, d)

    # ---- digest ----
    hist_snap = {fn[:-5]: {str(r["stock_id"]): r.get("close")
                           for r in load_json(os.path.join(HIST_DIR, fn), {}).get("stocks", [])}
                 for fn in sorted(os.listdir(HIST_DIR)) if fn.endswith(".json")}
    days = sorted(hist_snap)
    for p in dig_bad:
        print(f"[purge] digest {fix_digest(p, hist_snap, days)}")

    # ---- 收尾驗證 ----
    left = out_of_scope_in_stocks()
    left_store = []
    for rel, secs in STORES:
        d = load_json(os.path.join(ROOT, rel)) or {}
        for sec in secs:
            if isinstance(d.get(sec), dict):
                left_store += [k for k in d[sec] if not in_scope(k)]
    left_dig = [s for bad in digest_bad_syms().values() for s in bad]
    print(f"[purge] 完成：stocks.json 剩 {len(left)}、衍生 store 剩 {len(left_store)}、"
          f"digest 剩 {len(left_dig)}（三者皆應為 0）")
    sys.exit(0 if not (left or left_store or left_dig) else 1)


if __name__ == "__main__":
    main()
