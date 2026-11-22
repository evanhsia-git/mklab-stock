#!/usr/bin/env python3
"""
ETF 經理費 / 保管費（管理費）全量抓取腳本。
來源：MoneyDJ ETF 基本資料頁 Basic0004（結構化表格，可解析）。

使用方法：
    python3 skills/data/fetch_etf_fees.py [--data data/stocks.json] [--out data/etf-fees.csv]

輸出欄位：
    sym, name, issuer, aum_100m, current_mgmt, current_cust, current_total,
    moneydj_mgmt, moneydj_total, moneydj_other(總管理費用-經理費), aum_source,
    status(match / conflict / pending / error), note

原則：
- 不覆寫 stocks.json。只輸出對照 CSV 供人工複核。
- 無法抓取 → status=error，記錄原因。
- 級距/推算出來的「保管費」在 moneydj_other 標明為推算值，不當作官方保管費。
- 不得猜測：MoneyDJ 僅提供「經理費」與「總管理費用」；保管費需由總管理費用減經理費推算，
  輸出時明確標註為推算值（非官方保管費）。
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STOCKS_JSON = os.path.join(ROOT, "data", "stocks.json")
OUT_CSV = os.path.join(ROOT, "data", "etf-fees.csv")

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
BASE_URL = "https://www.moneydj.com/ETF/X/Basic/Basic0004.xdjhtm?etfid={sym}.TW"
INTERVAL = 0.35  # 禮貌間隔（秒）


def fetch_moneydj(sym):
    """抓取 MoneyDJ Basic0004，回傳 (mgmt_pct, total_pct, other_pct, raw_total_text)。"""
    url = BASE_URL.format(sym=sym)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=40) as f:
            html = f.read().decode("utf-8", "ignore")
    except Exception as e:
        return None, None, None, f"ERROR:{type(e).__name__}:{e}"

    # 經理費(%)
    m = re.search(r"經理費\(%\).*?<td[^>]*>([\d.]+)</td>", html, re.DOTALL)
    mgmt = float(m.group(1)) if m else None

    # 總管理費用(%)  例如「0.22 (含 0.07 非管理費用)」
    m2 = re.search(r"總管理費用\(%\).*?<td[^>]*>([\d.]+)", html, re.DOTALL)
    total = float(m2.group(1)) if m2 else None

    # 非管理費用（保管費+其他）括號內數值，若存在
    m3 = re.search(r"總管理費用\(%\).*?含\s*([\d.]+)\s*非管理費用", html, re.DOTALL)
    other = float(m3.group(1)) if m3 else None

    # 若 total 有抓但 m3 沒抓到，用 total - mgmt 推算（標記為推算）
    if other is None and total is not None and mgmt is not None:
        other = round(total - mgmt, 6)

    return mgmt, total, other, None


def main():
    parser = argparse.ArgumentParser(description="ETF 經理費/保管費全量抓取（MoneyDJ 來源）")
    parser.add_argument("--data", default=STOCKS_JSON, help="stocks.json 路徑")
    parser.add_argument("--out", default=OUT_CSV, help="output CSV 路徑")
    parser.add_argument("--limit", type=int, default=0, help="限制筆數（0=全部，測試用）")
    args = parser.parse_args()

    with open(args.data, "r", encoding="utf-8") as f:
        data = json.load(f)

    etfs = [r for r in data.get("stocks", []) if r.get("is_etf")]
    if args.limit > 0:
        etfs = etfs[:args.limit]
    print(f"[fetch_etf_fees] 待處理 ETF: {len(etfs)} 筆")

    rows = []
    stats = {"match": 0, "conflict": 0, "pending": 0, "error": 0}
    for i, r in enumerate(etfs, 1):
        sym = r["sym"]
        cur_mgmt = r.get("management_fee")
        cur_cust = r.get("custody_fee")
        cur_total = r.get("total_fee")
        mgmt, total, other, err = fetch_moneydj(sym)

        # 判斷狀態：與現值比對（容差 0.005）
        status = "pending"
        note = ""
        if err:
            status = "error"
            note = err
        elif mgmt is None and total is None:
            status = "error"
            note = "MoneyDJ 無費率資料"
        else:
            # 與現值比對
            diffs = []
            if mgmt is not None and cur_mgmt is not None:
                if abs(mgmt - cur_mgmt) <= 0.005:
                    diffs.append("mgmt=match")
                else:
                    diffs.append(f"mgmt=DIFF({mgmt}vs{cur_mgmt})")
            if total is not None and cur_total is not None:
                if abs(total - cur_total) <= 0.01:
                    diffs.append("total=match")
                else:
                    diffs.append(f"total=DIFF({total}vs{cur_total})")
            if any("DIFF" in d for d in diffs):
                status = "conflict"
                note = "; ".join(diffs)
            elif diffs:
                status = "match"
                note = "; ".join(diffs)
            else:
                status = "pending"
                note = "現值缺失無法比對" if not diffs else "; ".join(diffs)

        stats[status] = stats.get(status, 0) + 1
        rows.append({
            "sym": sym,
            "name": r.get("name"),
            "issuer": r.get("issuer"),
            "aum_100m": r.get("net_assets_100m"),
            "current_mgmt": cur_mgmt,
            "current_cust": cur_cust,
            "current_total": cur_total,
            "moneydj_mgmt": mgmt,
            "moneydj_total": total,
            "moneydj_other_incl_custody": other,
            "status": status,
            "note": note,
        })

        if i % 50 == 0 or i == len(etfs):
            print(f"  [{i}/{len(etfs)}] ...done, stats={stats}")
        time.sleep(INTERVAL)

    fieldnames = ["sym", "name", "issuer", "aum_100m", "current_mgmt", "current_cust",
                  "current_total", "moneydj_mgmt", "moneydj_total", "moneydj_other_incl_custody",
                  "status", "note"]
    with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[fetch_etf_fees] ✅ 輸出 CSV: {args.out}（{len(rows)} 筆）")
    print(f"  狀態統計: {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())