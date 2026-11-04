#!/usr/bin/env python3
"""
整合官方公司基本資料（TWSE t187ap03_L）到 data/stocks.json，並依實際陣列重算 meta。

範圍（P0-1 修正後）：TWSE／TPEx 一般股票與 ETF 皆納入。本腳本不再刪除任何上櫃列（舊版會把上櫃一般股票每日刪掉）。
- meta（count / sources / price_asof_counts）每次都依實際陣列重算，不沿用舊值（P1-1）。
- 一般股票（security_type=stock）補上 產業（ind）、上市／上櫃日期（listing_date）、公司簡稱（company_short）：
  - 上市：TWSE t187ap03_L（中文欄位），為主要來源（可覆寫既有值）
  - 上櫃：TPEx t187ap03_O（英文欄位，mopsfin_t187ap03_O），只補缺不覆寫
  官方產業代碼 → 名稱依 data/industry-codes.json；代碼 91 為存託憑證，不在 33 類內，單獨命名。
  日期欄位同時支援民國（1151103）與西元（20150925）兩種格式。
用法：python3 skills/data/integrate_official_company.py
"""
import csv, datetime as dt, glob, json, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_IC = json.load(open(os.path.join(ROOT, "data", "industry-codes.json"), encoding="utf-8"))
CODES = dict(_IC["codes"])
CODES["91"] = "存託憑證"                      # 存託憑證不在 33 類內，單獨命名
IND_FALLBACK = _IC.get("fallback", "其他等")  # 來源出現未收錄代碼時（如新增類股）不得留空


def ind_of(raw):
    """官方產業代碼 → 產業名稱；未收錄或空白一律回退 fallback，避免留下空的 ind。"""
    code = str(raw or "").strip().zfill(2)
    return CODES.get(code) or IND_FALLBACK


def _roc_iso(d):
    """官方日期欄位轉 YYYY-MM-DD：'1151103'（民國）與 '20150925'（西元）皆支援。"""
    d = str(d or "").strip()
    if len(d) != 8 or not d.isdigit():
        return None
    y = int(d[:4])
    if y < 1911:
        y += 1911
    return f"{y}-{d[4:6]}-{d[6:8]}"


def _read(path_glob, cols):
    """讀官方 CSV（utf-8-sig），回傳 {公司代號: {欄位: 值}}。"""
    files = glob.glob(path_glob)
    if not files:
        return {}
    rows = list(csv.reader(open(files[0], encoding="utf-8-sig")))
    if not rows:
        return {}
    h = rows[0]
    idx = {k: h.index(k) for k in cols if k in h}
    if len(idx) != len(cols):
        print(f"[integrate] {os.path.basename(files[0])} 欄位不足，略過（有 {h[:6]}）")
        return {}
    out = {}
    for r in rows[1:]:
        if not r:
            continue
        out[r[idx[cols[0]]].strip()] = {k: (r[idx[k]].strip() if idx[k] < len(r) else "") for k in cols}
    return out


# 上市：TWSE t187ap03_L（中文欄位）；上櫃：TPEx t187ap03_O（英文欄位）
ap_l = {}
for code_key, row in _read(os.path.join(ROOT, "data", "raw", "official", "t187ap03_L*.csv"),
                           ["公司代號", "公司簡稱", "產業別", "上市日期", "出表日期"]).items():
    ap_l[code_key] = {"short": row["公司簡稱"], "ind": ind_of(row["產業別"]),
                      "listing": _roc_iso(row["上市日期"]), "asof": row["出表日期"]}
ap_o = {}
for code_key, row in _read(os.path.join(ROOT, "data", "raw", "official", "t187ap03_O*.csv"),
                           ["SecuritiesCompanyCode", "CompanyAbbreviation", "SecuritiesIndustryCode",
                            "DateOfListing", "Date"]).items():
    ap_o[code_key] = {"short": row["CompanyAbbreviation"],
                      "ind": ind_of(row["SecuritiesIndustryCode"]),
                      "listing": _roc_iso(row["DateOfListing"]), "asof": row["Date"]}
if not ap_l and not ap_o:
    print("[integrate] 找不到 t187ap03_L／t187ap03_O CSV，略過公司基本資料整合（不中斷排程）")
    raise SystemExit(0)
p = os.path.join(ROOT, "data", "stocks.json")
doc = json.load(open(p, encoding="utf-8"))
before = len(doc["stocks"])
filled = 0
filled_o = 0
for s in doc["stocks"]:
    if s.get("security_type") != "stock":
        continue
    sym = s["sym"]
    if sym in ap_l:                      # 上市：t187ap03_L 為主要來源（可覆寫）
        a = ap_l[sym]
        if a["ind"]: s["ind"] = a["ind"]
        s["listing_date"] = a["listing"]
        s["company_short"] = a["short"]
        s["ind_src"] = f"TWSE_t187ap03_L（出表 {a['asof']}）"
        filled += 1
    elif sym in ap_o:                    # 上櫃：t187ap03_O 只補缺，不覆寫既有值
        b = ap_o[sym]
        if b["ind"] and not s.get("ind"): s["ind"] = b["ind"]
        if b["listing"] and not s.get("listing_date"): s["listing_date"] = b["listing"]
        if b["short"]: s["company_short"] = b["short"]
        s["ind_src"] = f"TPEx_t187ap03_O（出表 {b['asof']}）"
        filled_o += 1
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
    "company_info_matched_tpex": filled_o,
}
json.dump(doc, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(f"股票 {before} → {len(doc['stocks'])}；公司基本資料對應 上市 {filled} 檔 + 上櫃 {filled_o} 檔")
