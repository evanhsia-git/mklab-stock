#!/usr/bin/env python3
"""
ETF 經理費 / 總管理費用全量抓取腳本。
來源：MoneyDJ ETF 基本資料頁 Basic0004（結構化表格，可解析）。

使用方法：
    python3 skills/data/fetch_etf_fees.py [--data data/stocks.json] [--out data/etf-fees.csv] [--limit N]

輸出欄位：
    sym, name, issuer, aum_100m, current_mgmt, current_cust, current_total,
    moneydj_mgmt, moneydj_total, moneydj_other_incl_custody,
    mgmt_raw, total_raw（頁面原始格文字，供稽核）,
    status(match / conflict / pending / error), note

口徑原則（v2，2026-11-22）：
- 列錨定解析：<th>經理費(%)</th> 後「同一列」緊跟的 <td>，禁止跨列跳抓
  （v1 用 DOTALL 寬鬆匹配，當格值為空時會誤抓下一列的殖利率/報酬率）。
- 格值為空字串或「—」→ None（MoneyDJ 該欄無資料），不得推補。
- total < mgmt 視為 MoneyDJ 內部矛盾 → status=error，進人工複核，不得寫入。
- MoneyDJ 僅提供「經理費」與「總管理費用」；保管費為推算值（總-經理，含手續費/稅/其他），
  屬混合口徑，不得當作官方保管費寫入 custody_fee。
- 不覆寫 stocks.json。只輸出對照 CSV 供人工複核。
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

# 列錨定：th 後同一列緊跟 td，擷取 td 內完整原文
RE_MGMT = re.compile(r"<th[^>]*>\s*經理費\(%\)\s*</th>\s*<td[^>]*>(.*?)</td>", re.DOTALL)
RE_TOTAL = re.compile(r"<th[^>]*>\s*總管理費用\(%\)\s*</th>\s*<td[^>]*>(.*?)</td>", re.DOTALL)
RE_NUM = re.compile(r"^([\d.]+)")
RE_OTHER = re.compile(r"含\s*([\d.]+)\s*非管理費用")


def parse_cell(raw_html):
    """td 原文 → (值, 非管理費用, 清洗後文字)。空格/無數字 → (None, None, 文字)。"""
    text = re.sub(r"<[^>]+>", "", raw_html or "").strip()
    if text in ("", "—", "－", "-"):
        return None, None, text
    m = RE_NUM.match(text)
    val = float(m.group(1)) if m else None
    m2 = RE_OTHER.search(text)
    other = float(m2.group(1)) if m2 else None
    return val, other, text


def fetch_moneydj(sym):
    """抓取 MoneyDJ Basic0004。
    回傳 (mgmt, total, other, err, mgmt_raw, total_raw)。"""
    url = BASE_URL.format(sym=sym)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=40) as f:
            html = f.read().decode("utf-8", "ignore")
    except Exception as e:
        return None, None, None, f"ERROR:{type(e).__name__}:{e}", "", ""

    m1 = RE_MGMT.search(html)
    mgmt, _, mgmt_raw = parse_cell(m1.group(1)) if m1 else (None, None, "TH_NOT_FOUND")
    m2 = RE_TOTAL.search(html)
    total, other, total_raw = parse_cell(m2.group(1)) if m2 else (None, None, "TH_NOT_FOUND")

    # 若格內未標非管理費用且兩值俱在，以 total-mgmt 推算（僅供參考，非官方保管費）
    if other is None and total is not None and mgmt is not None:
        other = round(total - mgmt, 6)

    return mgmt, total, other, None, mgmt_raw, total_raw


def main():
    parser = argparse.ArgumentParser(description="ETF 經理費/總管理費用全量抓取（MoneyDJ 來源）")
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
        mgmt, total, other, err, mgmt_raw, total_raw = fetch_moneydj(sym)

        status = "pending"
        note = ""
        if err:
            status = "error"
            note = err
        elif mgmt is None and total is None:
            status = "error"
            note = "MoneyDJ 無費率資料（格值空/—）"
        elif mgmt is not None and total is not None and total + 1e-9 < mgmt:
            status = "error"
            note = f"MoneyDJ 內部矛盾 total({total})<mgmt({mgmt})，進人工複核"
        else:
            diffs = []
            if mgmt is not None and cur_mgmt is not None:
                diffs.append("mgmt=match" if abs(mgmt - cur_mgmt) <= 0.005
                             else f"mgmt=DIFF({mgmt}vs{cur_mgmt})")
            if total is not None and cur_total is not None:
                diffs.append("total=match" if abs(total - cur_total) <= 0.01
                             else f"total=DIFF({total}vs{cur_total})")
            if mgmt is None:
                diffs.append("mgmt缺(MoneyDJ無資料)")
            if total is None:
                diffs.append("total缺(MoneyDJ無資料)")
            if any("DIFF" in d for d in diffs):
                status = "conflict"
            elif any("match" in d for d in diffs):
                status = "match"
            else:
                status = "pending"
            note = "; ".join(diffs)

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
            "mgmt_raw": mgmt_raw,
            "total_raw": total_raw,
            "status": status,
            "note": note,
        })

        if i % 50 == 0 or i == len(etfs):
            print(f"  [{i}/{len(etfs)}] ...done, stats={stats}")
        time.sleep(INTERVAL)

    fieldnames = ["sym", "name", "issuer", "aum_100m", "current_mgmt", "current_cust",
                  "current_total", "moneydj_mgmt", "moneydj_total",
                  "moneydj_other_incl_custody", "mgmt_raw", "total_raw", "status", "note"]
    with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[fetch_etf_fees] ✅ 輸出 CSV: {args.out}（{len(rows)} 筆）")
    print(f"  狀態統計: {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
