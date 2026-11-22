#!/usr/bin/env python3
"""全市場 ETF 每日淨值／收盤／折溢價採集（TWSE MIS 反向 API）。

來源：`https://mis.twse.com.tw/stock/data/all_etf.txt`（單一請求、免 key，
需 Referer: mis.twse.com.tw/stock/etf_nav.jsp）。
實測 2026-11-22：一個請求回 359 檔；0050 NAV=84.68、市價=84.45、折溢價=−0.27%（日期 20261120）。
欄位對照：a=代號、b=名稱、i=資料日期(YYYYMMDD)、f=每單位淨值、e=收盤市價、g=折溢價%、h=前日淨值。

⚠️ API 只給「最新一筆」，歷史由本腳本每日盤後排程累積：
  1. data/etf-nav.json                  — 最新快照（前端折溢價欄用）
  2. data/etf-nav-history/YYYY-MM.csv   — 月檔累積（唯一鍵 record_date+etf_code，重跑去重冪等）

用法：/root/venvs/quant/bin/python3 skills/data/fetch_etf_nav.py [--dry-run]
"""
import csv
import json
import sys
import datetime as dt
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
NAV_JSON = ROOT / "data" / "etf-nav.json"
HISTORY_DIR = ROOT / "data" / "etf-nav-history"
URL = "https://mis.twse.com.tw/stock/data/all_etf.txt"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Referer": "https://mis.twse.com.tw/stock/etf_nav.jsp",
}
COLS = ["record_date", "etf_code", "nav", "close", "premium_discount_pct", "prev_nav"]


def _num(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def fetch_all():
    """回 {sym: {...}}；失敗回 {}。"""
    r = requests.get(URL, headers=HEADERS, timeout=20)
    if r.status_code != 200:
        print(f"[etf-nav] MIS API HTTP {r.status_code}", file=sys.stderr)
        return {}
    d = r.json()
    out = {}
    for group in d.get("a1", []):
        for it in group.get("msgArray", []):
            sym = (it.get("a") or "").strip().upper()
            nav = _num(it.get("f"))
            if not sym or nav is None:
                continue  # 無淨值不收（寧缺勿假）
            raw_date = (it.get("i") or "").strip()
            try:
                rec = dt.datetime.strptime(raw_date, "%Y%m%d").date().isoformat()
            except ValueError:
                rec = dt.date.today().isoformat()
            out[sym] = {
                "nav": nav,
                "close": _num(it.get("e")),
                "premium_discount_pct": _num(it.get("g")),
                "prev_nav": _num(it.get("h")),
                "record_date": rec,
            }
    return out


def upsert_history(records):
    """月檔累積：讀當月既有 CSV → 依 (record_date, etf_code) 合併 → 寫回。"""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    by_month = {}
    for sym, r in records.items():
        month = r["record_date"][:7]
        by_month.setdefault(month, []).append([r["record_date"], sym, r["nav"], r["close"],
                                               r["premium_discount_pct"], r["prev_nav"]])
    written = []
    for month, new_rows in sorted(by_month.items()):
        path = HISTORY_DIR / f"{month}.csv"
        existing = {}
        if path.exists():
            with open(path, newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    existing[(row["record_date"], row["etf_code"])] = [
                        row["record_date"], row["etf_code"],
                        _num(row.get("nav")), _num(row.get("close")),
                        _num(row.get("premium_discount_pct")), _num(row.get("prev_nav"))]
        for row in new_rows:
            existing[(row[0], row[1])] = row  # 新資料覆蓋同鍵舊值
        rows = sorted(existing.values(), key=lambda x: (x[0], x[1]))
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(COLS)
            w.writerows(rows)
        written.append(f"{path.name}（{len(rows)} 列）")
    return written


def main():
    dry = "--dry-run" in sys.argv
    records = fetch_all()
    if not records:
        print("[etf-nav] ❌ 未取得資料")
        return 1
    dates = sorted({r["record_date"] for r in records.values()})
    print(f"[etf-nav] 取得 {len(records)} 檔，record_date={dates}")

    if dry:
        s = records.get("0050")
        print(f"[etf-nav] 0050: {s}")
        print("[etf-nav] --dry-run：未寫入")
        return 0

    # 1) 最新快照 JSON（前端用）
    doc = {
        "meta": {
            "as_of": dates[-1],
            "record_dates": dates,
            "count": len(records),
            "source": URL,
            "source_note": "TWSE MIS 反向 API（Referer: mis.twse.com.tw/stock/etf_nav.jsp）；"
                           "最新一筆，歷史由每日盤後排程累積於 data/etf-nav-history/。",
            "premium_discount_note": "折溢價%＝(市價−淨值)/淨值；正值溢價、負值折價。",
        },
        "navs": records,
    }
    NAV_JSON.write_bytes(json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    # 2) 歷史月檔累積
    written = upsert_history(records)
    size = NAV_JSON.stat().st_size
    print(f"[etf-nav] ✅ {NAV_JSON.name}（{size/1024:.0f} KB）＋ 歷史 {', '.join(written)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
