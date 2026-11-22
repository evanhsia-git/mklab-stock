#!/usr/bin/env python3
"""ETF 持股歷史累積：把 data/etf-holdings.json 的當前快照併入月檔 TSV，供換股比對（diff）。

設計（學自 dj8111/taiwan-etf-holdings 的 record_date 累積概念，改用我們的輕量檔案制）：
  - data/etf-holdings-history/YYYY-MM.tsv
    欄位（TSV，避免名稱含逗號的引號問題）：record_date, etf_code, stock_code, stock_name, weight
    唯一鍵 (record_date, etf_code, stock_code)：同鍵重跑＝覆蓋（冪等），不會重複計入。
  - data/etf-holdings-history/index.json：{updated, months:[...]}，前端據此抓檔。
  - record_date 取每檔自身的 asof（來源基準日），非處理日。

用法：/root/venvs/quant/bin/python3 skills/data/accumulate_etf_holdings_history.py [--dry-run]
時機：每次持股來源更新後（目前掛在 official-fundamentals 月更 job，每月 20 日）。
"""
import csv
import json
import sys
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOLDINGS_PATH = ROOT / "data" / "etf-holdings.json"
HIST_DIR = ROOT / "data" / "etf-holdings-history"
COLS = ["record_date", "etf_code", "stock_code", "stock_name", "weight", "shares"]


def main():
    dry = "--dry-run" in sys.argv
    doc = json.loads(HOLDINGS_PATH.read_text(encoding="utf-8"))
    holdings = doc.get("holdings") or {}

    # 1) 當前快照 → (month → rows)
    by_month = {}
    skipped = []
    for sym, e in sorted(holdings.items()):
        asof = (e or {}).get("asof")
        items = (e or {}).get("items") or []
        if not asof or not items:
            skipped.append(sym)
            continue
        try:
            rec = dt.datetime.strptime(asof, "%Y-%m-%d").date().isoformat()
        except ValueError:
            skipped.append(sym)
            continue
        month = rec[:7]
        for it in items:
            code, name, weight = (it + [None, None, None])[:3]
            shares = it[3] if len(it) >= 4 else None  # 2026-11-22 起含股數（供 scale 校正）
            if code in (None, ""):
                continue
            by_month.setdefault(month, []).append(
                [rec, sym, str(code), str(name or ""), weight,
                 "" if shares in (None, "") else shares])

    if not by_month:
        print("[holdings-history] ❌ 快照中沒有可累積的持股（asof/items 缺失）")
        return 1

    # 2) 逐月 upsert（唯一鍵 record_date+etf_code+stock_code）
    HIST_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for month in sorted(by_month):
        path = HIST_DIR / f"{month}.tsv"
        existing = {}
        if path.exists():
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter="\t")
                next(reader, None)  # header
                for row in reader:
                    if len(row) >= 5:
                        existing[(row[0], row[1], row[2])] = row
        for row in by_month[month]:
            existing[(row[0], row[1], row[2])] = row
        rows = sorted(existing.values(), key=lambda x: (x[0], x[1], x[2]))
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow(COLS)
            w.writerows(rows)
        written.append(f"{month}.tsv（{len(rows)} 列）")

    # 3) index.json（前端換股比對的檔案清單）
    months = sorted(p.stem for p in HIST_DIR.glob("*.tsv"))
    index = {
        "updated": dt.date.today().isoformat(),
        "months": months,
        "columns": COLS,
        "note": "每月一檔；唯一鍵 record_date+etf_code+stock_code；來源為 data/etf-holdings.json 快照累積。",
    }
    if not dry:
        (HIST_DIR / "index.json").write_bytes(
            json.dumps(index, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    print(f"[holdings-history] 快照來源 {len(holdings) - len(skipped)} 檔"
          + (f"（跳過 asof/items 缺失 {len(skipped)} 檔）" if skipped else ""))
    print(f"[holdings-history] ✅ 已累積：{', '.join(written)}"
          + (f"＋index.json（months={months}）" if not dry else "（--dry-run：index 未寫入）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
