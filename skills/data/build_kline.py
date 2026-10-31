#!/usr/bin/env python3
"""
個股 K 線小檔產生（Build-Time）：為 data/stocks.json 內每檔股票輸出 data/kline/{代號}.json。
來源：data/history/ 近約一年的日快照（已套用離群值過濾）。格式：{"sym","asof","fields","rows":[[日期,開,高,低,收],...]}
缺高低價或開盤價的日子，以收盤價補值（不推測其他數字）。
"""
import datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compute_indicators import load_series
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "kline")
os.makedirs(OUT, exist_ok=True)
doc = json.load(open(os.path.join(ROOT, "data", "stocks.json"), encoding="utf-8"))
asof = doc["meta"]["as_of"]
series = load_series()
n = 0; total = 0
for s in doc["stocks"]:
    rows = series.get(s["sym"])
    if not rows:
        continue
    last = dt.datetime.strptime(rows[-1][0], "%Y%m%d").date()
    cutoff = last - dt.timedelta(days=366)
    out = []
    for d, o, h, l, c in rows:
        if dt.datetime.strptime(d, "%Y%m%d").date() <= cutoff:
            continue
        out.append([f"{d[:4]}-{d[4:6]}-{d[6:8]}", o if o is not None else c, h if h is not None else c, l if l is not None else c, c])
    if not out:
        continue
    with open(os.path.join(OUT, f"{s['sym']}.json"), "w", encoding="utf-8") as f:
        json.dump({"sym": s["sym"], "asof": asof, "fields": ["date", "open", "high", "low", "close"], "rows": out}, f, ensure_ascii=False, separators=(",", ":"))
    n += 1; total += len(out)
print(f"個股 K 線檔 {n} 檔，共 {total} 筆（資料日 {asof}）")
