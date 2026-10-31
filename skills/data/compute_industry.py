#!/usr/bin/env python3
"""
產業聚合重算（每次行情更新後執行）。來源：data/stocks.json（最新行情）與 data/history/（歷史收盤）。
不使用舊的 industry.json 當輸入；沒有有效最新資料時不寫入，避免舊統計冒充最新。
各區間報酬 = 該產業內有資料的一般股票（不含 ETF、unverified）等權平均。
"""
import datetime as dt
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compute_indicators import load_series  # 已套用離群值過濾

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STOCKS = os.path.join(ROOT, "data", "stocks.json")
OUT = os.path.join(ROOT, "data", "industry.json")


def ret_since(rows, days=None, ytd=False):
    """rows 依日期排序 (date, o, h, l, close)。回傳最新收盤相對於基準日收盤的報酬(%)。"""
    if not rows:
        return None
    latest_d = dt.datetime.strptime(rows[-1][0], "%Y%m%d").date()
    if ytd:
        target = dt.date(latest_d.year, 1, 1) - dt.timedelta(days=1)
    else:
        target = latest_d - dt.timedelta(days=days)
    base = None
    for r in rows:
        if dt.datetime.strptime(r[0], "%Y%m%d").date() <= target:
            base = r[4]
    if base in (None, 0):
        return None
    return (rows[-1][4] - base) / base * 100


def main():
    doc = json.load(open(STOCKS, encoding="utf-8"))
    as_of = doc.get("meta", {}).get("as_of")
    stocks = [s for s in doc["stocks"] if s.get("security_type", "stock") == "stock" and s.get("ind")]
    if not as_of or not stocks:
        print("[compute_industry] 無有效最新資料，不寫入 industry.json"); return
    series = load_series()
    by = {}
    for s in stocks:
        by.setdefault(s["ind"], []).append(s)

    rows = []
    for nm, members in sorted(by.items()):
        chgs = [m["chg"] for m in members if m.get("chg") is not None]
        if not chgs:
            continue
        def avg_of(fn):
            vals = [v for v in (fn(m["sym"]) for m in members) if v is not None]
            return round(statistics.mean(vals), 2) if vals else None
        rows.append({
            "nm": nm,
            "chg": round(statistics.mean(chgs), 2),
            "cnt": len(members),
            "top": round(max(chgs), 2),
            "w1": avg_of(lambda sym: ret_since(series.get(sym), days=7)),
            "m1": avg_of(lambda sym: ret_since(series.get(sym), days=30)),
            "m3": avg_of(lambda sym: ret_since(series.get(sym), days=91)),
            "m6": avg_of(lambda sym: ret_since(series.get(sym), days=182)),
            "ytd": avg_of(lambda sym: ret_since(series.get(sym), ytd=True)),
            "y1": avg_of(lambda sym: ret_since(series.get(sym), days=365)),
            "y5": None,
        })
    out = {
        "meta": {
            "as_of": as_of,
            "source": "calculated-from-stocks-and-history（每日行情更新後重算）",
            "schema_version": "1.0.0",
            "count": len(rows),
            "generated_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
        },
        "industry": rows,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[compute_industry] ✅ {len(rows)} 個產業，資料日 {as_of}")


if __name__ == "__main__":
    main()
