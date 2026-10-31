#!/usr/bin/env python3
"""
TWSE 公司基本資料（t187ap03_L）產業別匯入：只補「一般股票」中產業空白的代號，不覆蓋已有的值。
產業代碼 → 名稱 依 data/industry-codes.json。
用法：放入 data/raw/official/t187ap03_L_*.csv 後執行 python3 skills/data/import_company_industry.py
"""
import csv, datetime as dt, glob, json, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = glob.glob(os.path.join(ROOT, "data", "raw", "official", "t187ap03_L*.csv"))
codes = json.load(open(os.path.join(ROOT, "data", "industry-codes.json"), encoding="utf-8"))["codes"]
if not SRC:
    raise SystemExit("找不到 t187ap03_L CSV")
with open(SRC[0], encoding="utf-8-sig") as f:
    rows = list(csv.reader(f))
h = rows[0]
i_sym, i_code, i_date = h.index("公司代號"), h.index("產業別"), h.index("出表日期")
ap = {r[i_sym].strip(): (codes.get(r[i_code].strip().zfill(2)), r[i_date].strip()) for r in rows[1:] if r}
p = os.path.join(ROOT, "data", "stocks.json")
doc = json.load(open(p, encoding="utf-8"))
filled = []
for s in doc["stocks"]:
    if s.get("security_type") == "stock" and not s.get("ind") and s["sym"] in ap and ap[s["sym"]][0]:
        s["ind"] = ap[s["sym"]][0]
        s["ind_src"] = f"TWSE_t187ap03_L（出表 {ap[s['sym']][1]}）"
        filled.append(s["sym"])
json.dump(doc, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(f"補上產業 {len(filled)} 檔：{filled}")
