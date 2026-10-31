#!/usr/bin/env python3
"""
整合官方公司基本資料（TWSE t187ap03_L）到 data/stocks.json，並依範圍規則排除 TPEx 非 ETF 列。

範圍（使用者指定）：TWSE 一般股票、TWSE ETF、上櫃（TPEx）標準 ETF。不收 TPEx 一般股票。
- TPEx 列：只保留官方 ETF 清單（data/etf-meta.json）內的代號，其餘移除。
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
    raise SystemExit("找不到 t187ap03_L CSV")
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
etf_off = {e["sym"] for e in json.load(open(os.path.join(ROOT, "data", "etf-meta.json"), encoding="utf-8")).get("etfs", [])}
p = os.path.join(ROOT, "data", "stocks.json")
doc = json.load(open(p, encoding="utf-8"))
before = len(doc["stocks"])
removed_tpex = [s["sym"] for s in doc["stocks"] if s.get("source") == "TPEX" and s["sym"] not in etf_off]
doc["stocks"] = [s for s in doc["stocks"] if not (s.get("source") == "TPEX" and s["sym"] not in etf_off)]
filled = 0
for s in doc["stocks"]:
    if s.get("security_type") == "stock" and s["sym"] in ap:
        a = ap[s["sym"]]
        if a["ind"]: s["ind"] = a["ind"]
        s["listing_date"] = a["listing"]
        s["company_short"] = a["short"]
        s["ind_src"] = f"TWSE_t187ap03_L（出表 {a['asof']}）"
        filled += 1
doc["meta"]["count"] = len(doc["stocks"])
src = {}
for s in doc["stocks"]:
    src[s.get("source")] = src.get(s.get("source"), 0) + 1
doc["meta"]["sources"] = src
doc["meta"]["integration"] = {
    "integrated_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
    "scope": "TWSE 一般股票 + TWSE ETF + TPEx 標準 ETF（不含 TPEx 一般股票）",
    "tpex_removed": removed_tpex, "rows_before": before, "rows_after": len(doc["stocks"]),
    "company_info_matched": filled,
}
json.dump(doc, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(f"移除 TPEx 非 ETF {len(removed_tpex)} 筆：{removed_tpex}")
print(f"股票 {before} → {len(doc['stocks'])}；公司基本資料對應 {filled} 檔")
