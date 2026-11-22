#!/usr/bin/env python3
"""ETF 換股比對（CLI）：比較某檔 ETF 在兩個持股基準日之間的成份股增減與權重變動。

資料源：data/etf-holdings-history/YYYY-MM.tsv（由 accumulate_etf_holdings_history.py 累積）。

用法：
    python3 skills/data/etf_holdings_diff.py 00878                # 列出該檔可用的快照日期
    python3 skills/data/etf_holdings_diff.py 00878 2026-11-05 2026-11-20
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HIST_DIR = ROOT / "data" / "etf-holdings-history"


def load_etf_rows(etf_code):
    """跨月檔收集該 ETF 的持股列 → {record_date: {stock_code: (name, weight)}}。"""
    if not HIST_DIR.exists():
        return {}
    by_date = {}
    for path in sorted(HIST_DIR.glob("*.tsv")):
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            next(reader, None)
            for row in reader:
                if len(row) >= 5 and row[1] == etf_code:
                    by_date.setdefault(row[0], {})[row[2]] = (row[3], float(row[4]))
    return by_date


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    etf = sys.argv[1].strip().upper()
    by_date = load_etf_rows(etf)
    dates = sorted(by_date)
    if not dates:
        print(f"❌ 歷史資料中沒有 {etf} 的持股快照（data/etf-holdings-history/）")
        return 1
    if len(sys.argv) < 4:
        print(f"{etf} 可用快照日期：{dates}")
        print(f"用法：python3 {sys.argv[0]} {etf} <舊日期> <新日期>（皆為 YYYY-MM-DD）")
        return 0
    d1, d2 = sys.argv[2], sys.argv[3]
    for d in (d1, d2):
        if d not in by_date:
            print(f"❌ {etf} 沒有 {d} 的快照。可用：{dates}")
            return 1
    h1, h2 = by_date[d1], by_date[d2]

    added = sorted(set(h2) - set(h1))
    removed = sorted(set(h1) - set(h2))
    changed = []
    for code in sorted(set(h1) & set(h2)):
        n1, w1 = h1[code]
        n2, w2 = h2[code]
        if abs(w2 - w1) >= 0.01:
            changed.append((code, n2, w1, w2, w2 - w1))
    changed.sort(key=lambda x: -abs(x[4]))

    print(f"\n═══ {etf} 換股比對：{d1} → {d2} ═══")
    print(f"快照規模：{len(h1)} 檔 → {len(h2)} 檔")
    print(f"\n[+] 新增 {len(added)} 檔：")
    for c in added:
        print(f"  + {c} {h2[c][0]}（權重 {h2[c][1]:.2f}%）")
    print(f"\n[-] 移除 {len(removed)} 檔：")
    for c in removed:
        print(f"  - {c} {h1[c][0]}（原權重 {h1[c][1]:.2f}%）")
    print(f"\n[Δ] 權重變動 {len(changed)} 檔（|Δ|≥0.01pp，依變動量排序，最多列 30）：")
    for c, name, w1, w2, delta in changed[:30]:
        print(f"  Δ {c} {name}: {w1:.2f}% → {w2:.2f}%（{delta:+.2f}pp）")
    if len(changed) > 30:
        print(f"  …另有 {len(changed) - 30} 檔未列出")
    print("\n註：快照來源為投信官方／CMoney 前 10 大等，權重基準日不同時請留意可比性。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
