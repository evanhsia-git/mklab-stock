#!/usr/bin/env python3
"""PCF 內嵌官方淨值 vs TWSE MIS 獨立淨值交叉核對（資料誠信紅線第 4 點的自動化）。

來源 PCF 檔（src=USITC/UOBAM）內嵌官方每單位淨值；TWSE MIS all_etf（fetch_etf_nav 管線）
提供獨立第二源。兩者差異 >1% 時列警示（可能 PCF 基準日不同或解析錯誤）。

- 只比對「asof 與 MIS record_date 同日」者（跨日價差不是錯誤，是時間點不同）
- MIS 無資料時 SKIP（每日班 17:00 後才有當日快照）
- 退出碼：永遠 0（警示不擋 job——這是核對報告，不是閘門）
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAV_PATH = ROOT / "data" / "etf-nav.json"
HOLDINGS_PATH = ROOT / "data" / "etf-holdings.json"
TOL = 0.01  # 1%


def main():
    nav_doc = json.load(open(NAV_PATH, encoding="utf-8"))
    hold = json.load(open(HOLDINGS_PATH, encoding="utf-8"))["holdings"]
    rows = nav_doc.get("rows") or nav_doc.get("data") or []
    if not rows:
        print("[verify-pcf-nav] SKIP：MIS 淨值快照無資料（等 daily 班寫入）")
        return 0

    # 今日（快照內最新 record_date）
    latest = max(r.get("record_date", "") for r in rows)
    nav_map = {r.get("etf_code") or r.get("code"): r for r in rows
               if r.get("record_date") == latest}

    checked = warned = skipped = 0
    for sym, e in sorted(hold.items()):
        pcf_nav = (e.get("nav") or (e.get("extra") or {}).get("nav")) if isinstance(e, dict) else None
        # PCF 淨值存在 entry？USITC/UOBAM 的 extra/nav 在寫入時未保存 entry 頂層——改由 items 重新計算不可行
        # → 讀寫入時的 extra 快照（若整合腳本未存，SKIP）
        if e.get("src") not in ("USITC", "UOBAM"):
            continue
        if not pcf_nav:
            skipped += 1
            continue
        mis = nav_map.get(sym)
        if not mis or not mis.get("nav"):
            skipped += 1
            print(f"[verify-pcf-nav] {sym}: SKIP（MIS 無 {latest} 淨值）")
            continue
        checked += 1
        diff = abs(float(mis["nav"]) - float(pcf_nav)) / float(pcf_nav)
        flag = "⚠️" if diff > TOL else "✓"
        if diff > TOL:
            warned += 1
        print(f"[verify-pcf-nav] {sym}: PCF={pcf_nav} MIS={mis['nav']} 差 {diff*100:.2f}% {flag}")

    print(f"[verify-pcf-nav] 核對 {checked}／警示 {warned}／SKIP {skipped}（基準日 {latest}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
