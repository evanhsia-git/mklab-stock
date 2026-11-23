#!/usr/bin/env python3
"""把 ETF 週邊資料整合進 stocks.json（冪等，可每日重跑）。

補齊欄位（缺值不補 0、不造假——來源沒有就留 null）：
  1. custody_fee          保管費% ← data/etf-fees.csv 的 current_cust（MoneyDJ 實抓）
  2. holdings_date        持股資料基準日 ← data/etf-holdings.json 的 asof
  3. holdings_total_count 持股總數 ← etf-holdings.json 的 n（官方/解析總數），
     缺時退回 n_listed（清單可見檔數），兩者皆無則留 null

來源優先序與「寧缺勿假」原則見 skill taiwan-etf-holdings/references/issuer-sources.md。
執行：/root/venvs/quant/bin/python3 skills/data/integrate_etf_extras.py
"""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STOCKS = os.path.join(ROOT, "data", "stocks.json")
HOLDINGS = os.path.join(ROOT, "data", "etf-holdings.json")
FEES = os.path.join(ROOT, "data", "etf-fees.csv")


def load_fees():
    if not os.path.exists(FEES):
        return {}
    with open(FEES, encoding="utf-8-sig") as f:
        return {r["sym"]: r for r in csv.DictReader(f) if r.get("sym")}


def main():
    with open(STOCKS, encoding="utf-8") as f:
        doc = json.load(f)
    stocks = doc["stocks"]
    hold = {}
    if os.path.exists(HOLDINGS):
        with open(HOLDINGS, encoding="utf-8") as f:
            hold = json.load(f).get("holdings", {})
    fees = load_fees()

    n_custody = n_hdate = n_hcount = 0
    for r in stocks:
        if r.get("security_type") != "etf":
            continue
        sym = r["sym"]
        # 1) 保管費（MoneyDJ 實抓；已有值不覆蓋——手動核實優先）
        fr = fees.get(sym)
        if fr and r.get("custody_fee") is None:
            try:
                cust = float(fr.get("current_cust") or "") if fr.get("current_cust") not in ("", None) else None
            except ValueError:
                cust = None
            if cust is not None:
                r["custody_fee"] = cust
                r["custody_fee_src"] = fr.get("note", "moneydj") or "moneydj"
                n_custody += 1
        # 2/3) 持股基準日與總數（每日隨 etf-holdings 更新——直接覆寫為最新值）
        # 誠實語義：holdings_total_count 只認官方完整清單的 n。CMoney/YFinance 來源的
        # n 是「前 10 大樣本數」（例 0050 n=10 但實際持股上百檔），填進 total_count 會誤導。
        e = hold.get(sym) or {}
        if e.get("asof"):
            if r.get("holdings_date") != e["asof"]:
                n_hdate += 1
            r["holdings_date"] = e["asof"]
        src = (e.get("src") or "")
        is_official = bool(src) and "CMONEY" not in src and src != "YFINANCE"
        if is_official and e.get("n") is not None:
            n_val = int(e["n"])
            if r.get("holdings_total_count") != n_val:
                n_hcount += 1
            r["holdings_total_count"] = n_val
        elif r.get("holdings_total_count") is not None:
            # 來源退回非官方清單時移除舊值（避免殘留過期/樣本數）
            r.pop("holdings_total_count", None)
            n_hcount += 1

    tmp = STOCKS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, STOCKS)
    print(f"[integrate_etf_extras] 保管費 +{n_custody}、holdings_date 更新 {n_hdate}、holdings_total_count 更新 {n_hcount}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
