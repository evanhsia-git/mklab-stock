#!/usr/bin/env python3
"""ETF 換股比對（CLI）：比較某檔 ETF 在兩個持股基準日之間的成份股增減與權重變動。

v2（2026-11-22）：加入「申贖分離」校正（學自 nctuwanglin/active-etf 的 diffengine）——
ETF 被申購/贖回時全部持股會等比例增減（資金流，非經理人操作）：
    scale = 全體共同持股「股數比值」的真中位數（偶數筆取左右中央平均，取右側會漏判）
    adjusted_delta = 本期股數 − 前期股數 × scale
事件判定雙門檻：校正後股數變化 ≥5%「且」欄位權重變化 ≥0.1pp。
common <3 或 scale 超出 [0.2, 5] → quality=insufficient_scale，校正欄位歸 null（寧缺勿假）。
缺股數（舊 3 欄快照）→ 退回純權重比對並標註「無法分離申購贖回」。

資料源：data/etf-holdings-history/YYYY-MM.tsv
    欄位：record_date, etf_code, stock_code, stock_name, weight, shares（shares 可為空）。

用法：
    python3 skills/data/etf_holdings_diff.py 00878                # 列出該檔可用的快照日期
    python3 skills/data/etf_holdings_diff.py 00878 2026-11-05 2026-11-20
"""
import csv
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HIST_DIR = ROOT / "data" / "etf-holdings-history"
SHARES_THR = 0.05   # 校正後股數變化 ≥5%
WEIGHT_THR = 0.1    # 且權重變化 ≥0.1 個百分點
MIN_COMMON = 3


def load_etf_rows(etf_code):
    """跨月檔收集該 ETF 的持股列 → {record_date: {stock_code: (name, weight, shares|None)}}。"""
    if not HIST_DIR.exists():
        return {}
    by_date = {}
    for path in sorted(HIST_DIR.glob("*.tsv")):
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            next(reader, None)
            for row in reader:
                if len(row) >= 5 and row[1] == etf_code:
                    shares = None
                    if len(row) >= 6 and row[5] not in ("", "None"):
                        try:
                            shares = int(float(row[5]))
                        except ValueError:
                            shares = None
                    by_date.setdefault(row[0], {})[row[2]] = (row[3], float(row[4]), shares)
    return by_date


def compute_scale(h1, h2):
    """共同持股（兩期股數皆 >0）的股數比值真中位數。回 (scale|None, common_count)。"""
    common = [c for c in h2 if c in h1 and h1[c][2] and h2[c][2] and h1[c][2] > 0 and h2[c][2] > 0]
    if len(common) < MIN_COMMON:
        return None, len(common)
    ratios = [h2[c][2] / h1[c][2] for c in common]
    # 真中位數：偶數筆取左右中央平均（取右側中央值曾造成 1 筆漏判——active-etf 的實測教訓）
    return statistics.median(ratios), len(common)


def valid_scale(scale, common_count):
    return common_count >= MIN_COMMON and scale is not None and 0.2 <= scale <= 5


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

    scale, common_n = compute_scale(h1, h2)
    quality = "ok" if valid_scale(scale, common_n) else "insufficient_scale"
    all_codes = set(h1) | set(h2)
    has_shares = all(h1.get(c, (None, None, None))[2] is not None
                     and h2.get(c, (None, None, None))[2] is not None for c in all_codes)
    print(f"\n═══ {etf} 換股比對：{d1} → {d2} ═══")
    print(f"快照規模：{len(h1)} 檔 → {len(h2)} 檔")
    if has_shares and scale is not None:
        print(f"規模校正：scale={scale:.4f}（共同持股 {common_n} 檔，品質={quality}）")
    elif has_shares:
        print(f"規模校正：共同持股僅 {common_n} 檔（<3）→ 不校正，事件判定僅供參考")
    else:
        print("⚠️ 快照缺股數（權重-only）→ 無法分離申購贖回，比對結果含資金流噪音")

    added = sorted(c for c in h2 if c not in h1)
    removed = sorted(c for c in h1 if c not in h2)
    print(f"\n[+] 新增 {len(added)} 檔：")
    for c in added:
        s = h2[c][2]
        print(f"  + {c} {h2[c][0]}（權重 {h2[c][1]:.2f}%，股數 {s if s is not None else '—'}）")
    print(f"\n[-] 移除 {len(removed)} 檔：")
    for c in removed:
        s = h1[c][2]
        print(f"  - {c} {h1[c][0]}（原權重 {h1[c][1]:.2f}%，原股數 {s if s is not None else '—'}）")

    events = []
    for c in sorted(set(h1) & set(h2)):
        n2, w2, s2 = h2[c]
        _, w1, s1 = h1[c]
        dw = w2 - w1
        if has_shares and quality == "ok" and s1 and s2:
            adj = s2 / (s1 * scale) - 1.0
            if adj >= SHARES_THR and dw >= WEIGHT_THR:
                events.append(("INCREASE", c, n2, w1, w2, dw, s1, s2, int(round(s2 - s1 * scale))))
            elif adj <= -SHARES_THR and dw <= -WEIGHT_THR:
                events.append(("DECREASE", c, n2, w1, w2, dw, s1, s2, int(round(s2 - s1 * scale))))
    events.sort(key=lambda x: -abs(x[8]))
    if events:
        print(f"\n[Δ] 主動加減碼事件 {len(events)} 檔（校正後股數 ≥5% 且權重 ≥0.1pp）：")
        for typ, c, n2, w1, w2, dw, s1, s2, adj in events[:30]:
            arrow = "▲" if typ == "INCREASE" else "▼"
            print(f"  {arrow} {c} {n2}: 權重 {w1:.2f}% → {w2:.2f}%（{dw:+.2f}pp），"
                  f"校正後 {adj:+,} 股（原差 {s2 - s1:+,}）")
        if len(events) > 30:
            print(f"  …另有 {len(events) - 30} 檔未列出")
    else:
        print("\n[Δ] 無跨門檻的主動加減碼事件")

    print("\n註：快照來源為投信官方／CMoney 前 10 大等，權重基準日不同時請留意可比性。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
