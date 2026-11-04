#!/usr/bin/env python3
"""
整合官方公司基本資料（TWSE t187ap03_L）到 data/stocks.json，並依實際陣列重算 meta。

範圍（P0-1 修正後）：TWSE／TPEx 一般股票與 ETF 皆納入。本腳本不再刪除任何上櫃列（舊版會把上櫃一般股票每日刪掉）。
- meta（count / sources / price_asof_counts）每次都依實際陣列重算，不沿用舊值（P1-1）。
- 一般股票（security_type=stock）：以 t187ap03_L 補上 產業（ind）、上市日期（listing_date）、公司簡稱（company_short）。
  官方產業代碼 → 名稱依 data/industry-codes.json；代碼 91 為存託憑證，不在 33 類內，單獨命名。
用法：python3 skills/data/integrate_official_company.py
"""
import csv, datetime as dt, glob, json, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CODES = json.load(open(os.path.join(ROOT, "data", "industry-codes.json"), encoding="utf-8"))["codes"]
CODES = dict(CODES); CODES["91"] = "存託憑證"
SRC = glob.glob(os.path.join(ROOT, "data", "raw", "official", "t187ap03_L*.csv"))
if not SRC:
    print("[integrate] 找不到 t187ap03_L CSV，略過公司基本資料整合（不中斷排程）")
    raise SystemExit(0)
rows = list(csv.reader(open(SRC[0], encoding="utf-8-sig")))
h = rows[0]
ci = {k: h.index(k) for k in ["公司代號", "公司簡稱", "產業別", "上市日期", "出表日期"]}
ap = {}
for r in rows[1:]:
    if not r: continue
    code = r[ci["產業別"]].strip().zfill(2)
    d = r[ci["上市日期"]].strip()
    iso = f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 and d.isdigit() else None
    ap[r[ci["公司代號"]].strip()] = {"short": r[ci["公司簡稱"]].strip(), "ind": CODES.get(code), "listing": iso, "asof": r[ci["出表日期"]].strip()}
p = os.path.join(ROOT, "data", "stocks.json")
doc = json.load(open(p, encoding="utf-8"))
before = len(doc["stocks"])
filled = 0
for s in doc["stocks"]:
    if s.get("security_type") == "stock" and s["sym"] in ap:
        a = ap[s["sym"]]
        if a["ind"]: s["ind"] = a["ind"]
        s["listing_date"] = a["listing"]
        s["company_short"] = a["short"]
        s["ind_src"] = f"TWSE_t187ap03_L（出表 {a['asof']}）"
        filled += 1
# P0-6：修正既有資料的市值 0（缺漏應為 null）。一般股票：收盤 × 股本 ÷ 面值10；無股本則設 null
for s_ in doc["stocks"]:
    if s_.get("market_cap") == 0:
        cs = s_.get("capital_stock")
        px = s_.get("price")
        if s_.get("security_type") == "stock" and cs and px and px > 0:
            s_["market_cap"] = round(px * cs / 10)
        else:
            s_["market_cap"] = None

# P1-1：meta 一律由實際陣列重算（count / sources / price_asof_counts），不沿用舊值
doc["meta"]["count"] = len(doc["stocks"])
src = {}
pa = {}
for s in doc["stocks"]:
    src[s.get("source")] = src.get(s.get("source"), 0) + 1
    k = s.get("price_asof")
    pa[k] = pa.get(k, 0) + 1
doc["meta"]["sources"] = src
doc["meta"]["price_asof_counts"] = pa
doc["meta"]["integration"] = {
    "integrated_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
    "scope": "TWSE／TPEx 一般股票 + TWSE／TPEx ETF（TPEx 一般股票於 P0-1 起納入）",
    "rows_before": before, "rows_after": len(doc["stocks"]),
    "company_info_matched": filled,
}
json.dump(doc, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(f"股票 {before} → {len(doc['stocks'])}；公司基本資料對應 {filled} 檔")
