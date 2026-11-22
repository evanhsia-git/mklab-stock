#!/usr/bin/env python3
"""Read TWSE / TPEx ETF holdings CSV (with_holdings) and update
stocks.json 中 is_etf 記錄的 `holdings` 欄位（前 N 大成分股、權重）。

不修改正式程式，只更新 data/stocks.json 資料。
"""

import csv, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root
DATA = ROOT / "data"
RAW = DATA / "raw"
STOCKS = DATA / "stocks.json"

CSV_TWSE = RAW / "twse_etf_20261105_with_holdings.csv"
CSV_TPEX = RAW / "tpex_etf_20261105_with_holdings.csv"
MAX_HOLDINGS = 10  # 只保留前 10 大，避免檔案過大

def _clean_sym(sym: str) -> str:
    sym = sym.strip()
    if sym.startswith("="):
        sym = sym[1:]
    return sym.strip('"').strip()

def _read_csv(path: Path):
    rows = []
    if not path.exists():
        print(f"⚠️ 找不到 {path}，跳過", file=sys.stderr)
        return rows
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            sym = _clean_sym(r.get("股票代號", ""))
            name = r.get("ETF名稱", "").strip()
            if not sym:
                continue
            holdings = []
            for i in range(1, MAX_HOLDINGS + 1):
                code_key = f"成份股{i}代號"
                name_key = f"成份股{i}名稱"
                weight_key = f"成份股{i}權重%"
                code = r.get(code_key, "").strip()
                hname = r.get(name_key, "").strip()
                weight = r.get(weight_key, "").strip()
                if not code:
                    continue
                try:
                    w = float(weight.replace("%", "").replace(",", "").strip())
                except ValueError:
                    w = None
                holdings.append({
                    "code": code,
                    "name": hname or None,
                    "weight_pct": w,
                })
            rows.append({
                "sym": sym,
                "name": name,
                "holdings": holdings,
                "holdings_count": r.get("成份股數量", "").strip() or None,
                "holdings_source": r.get("成份股來源", "").strip() or None,
                "holdings_date": r.get("成份股資料日", "").strip() or None,
            })
    return rows

def main():
    twse_rows = _read_csv(CSV_TWSE)
    tpex_rows = _read_csv(CSV_TPEX)
    all_rows = twse_rows + tpex_rows
    holdings_by_sym = {r["sym"]: r for r in all_rows}
    print(f"讀取 TWSE holdings {len(twse_rows)} 檔，TPEx {len(tpex_rows)} 檔，共 {len(all_rows)} 檔")

    with open(STOCKS, "r", encoding="utf-8") as f:
        data = json.load(f)
    stocks = data.get("stocks", [])
    updated = 0
    for rec in stocks:
        if not rec.get("is_etf"):
            continue
        sym = rec.get("sym")
        if not sym:
            continue
        row = holdings_by_sym.get(sym)
        if row:
            rec["holdings"] = row["holdings"]
            rec["holdings_count"] = row["holdings_count"]
            rec["holdings_source"] = row["holdings_source"]
            rec["holdings_date"] = row["holdings_date"]
            updated += 1
        else:
            # 若沒找到 holdings，保留現有值或設為 null（不自動填 0）
            rec.setdefault("holdings", None)

    # minified JSON 寫回
    with open(STOCKS, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"✅ 已更新 {updated} 筆 ETF holdings，寫回 {STOCKS}")

if __name__ == "__main__":
    main()