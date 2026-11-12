#!/usr/bin/env python3
"""歷史快照修復：刪除無效快照檔，並清掉「上市前／來源缺漏時的補值列」。

兩類問題（皆為實測發現）：

A. 「高低價整日缺失」的快照檔（檔案層規則，既有）
   休市日或來源不完整時寫入（TWSE 回傳舊資料、缺 high/low）→ 不是真實交易日，
   會造成回測與指標的單點離群值。判定：high 缺失超過 50% → 整檔刪除。

B. 「前導補值列」（2026-11-12 新增，列層規則）
   實測：14 份快照（2025-07-14 ~ 2025-07-31）有 1309/1311 列是 `o=h=l=c`，
   且**成交量與該代號首列一字不差** → 是偽造補值，不是真實平盤
   （真實一字漲跌停的量仍會變動）。另有 73 檔 ETF／個股在「上市前」被補了
   最多 226 天的同價同量列（例：009816 凱基台灣TOP50 於 2026-02-03 才掛牌，
   卻有 142 天 close=15.0 且量固定 367,256,179 的假資料，導致 research 頁
   YTD 基準價算成 15 元）。
   判定：某代號「開頭連續 ≥3 天」同時滿足 ①o=h=l=c ②volume 與該代號首列相同
        → 視為補值，**逐列**刪除。
   ⚠️ 不可整檔刪除：實測同一份假快照裡仍有 2 檔（2380、6806 森崴能源）是真實資料。
   ⚠️ 必須同時看「量」：2026-07-13 整檔 o=h=l=c 但量各不相同（1307 種不同值），
      那是「OHLC 用 close 回填」的既有設計、**收盤價是真的** → 不可刪。

修完請重跑 build_kline.py 與 compute_indicators.py（kline 與 MA/RSI/MACD/KD 都由此衍生）。
紀錄寫入 data/history-repair-log.json。
"""
import datetime as dt
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HIST = os.path.join(ROOT, "data", "history")
LOG = os.path.join(ROOT, "data", "history-repair-log.json")
PAD_MIN_RUN = 3          # 連續幾天同價同量才視為補值


def load_all():
    snaps = []
    for fp in sorted(glob.glob(os.path.join(HIST, "*.json"))):
        d = json.load(open(fp, encoding="utf-8"))
        snaps.append((fp, d, d.get("stocks", [])))
    return snaps


def find_padded_rows(snaps):
    """回傳 {(日期, 代號)} = 屬於「前導補值」的列。"""
    by_sym = {}
    for fp, d, rows in snaps:
        date = os.path.basename(fp)[:-5]
        for r in rows:
            by_sym.setdefault(str(r.get("stock_id")), []).append((date, r))
    marked, detail = set(), []
    for sym, items in by_sym.items():
        items.sort(key=lambda x: x[0])
        if len(items) < PAD_MIN_RUN:
            continue
        c0, v0 = items[0][1].get("close"), items[0][1].get("volume")
        run = 0
        for date, r in items:
            flat = r.get("open") == r.get("high") == r.get("low") == r.get("close")
            same = r.get("close") == c0 and r.get("volume") == v0
            if flat and same:
                run += 1
            else:
                break
        if run >= PAD_MIN_RUN:
            for date, r in items[:run]:
                marked.add((date, sym))
            detail.append({
                "sym": sym,
                "name": items[0][1].get("stock_name"),
                "padded_days": run,
                "first_padded": items[0][0],
                "last_padded": items[run - 1][0] if run <= len(items) else None,
                "first_real": items[run][0] if run < len(items) else None,
                "first_real_close": items[run][1].get("close") if run < len(items) else None,
                "padded_close": c0, "padded_volume": v0,
            })
    return marked, sorted(detail, key=lambda x: -x["padded_days"])


def main():
    dry = "--dry-run" in sys.argv
    snaps = load_all()
    print(f"[repair] 載入 {len(snaps)} 份快照")

    # ---- A. 整檔無效（high 缺失 > 50%）----
    dead = []
    for fp, d, rows in snaps:
        if rows and sum(1 for r in rows if r.get("high") is None) / len(rows) > 0.5:
            dead.append({"file": os.path.basename(fp), "rows": len(rows)})

    # ---- B. 前導補值列 ----
    marked, detail = find_padded_rows(snaps)
    print(f"[repair] A 類（整檔無效）：{len(dead)} 檔")
    print(f"[repair] B 類（前導補值）：{len(marked)} 列，涉及 {len(detail)} 檔標的")
    for x in detail[:8]:
        print(f"   {x['sym']:<8} 補值 {x['padded_days']:>3} 天 "
              f"({x['first_padded']}~{x['last_padded']}) close={x['padded_close']} "
              f"→ 真實首日 {x['first_real']} close={x['first_real_close']}")
    if len(detail) > 8:
        print(f"   …另有 {len(detail) - 8} 檔")

    if dry:
        print("[repair] --dry-run：不修改任何檔案")
        return

    for fp, d, rows in snaps:
        if os.path.basename(fp) in {x["file"] for x in dead}:
            os.remove(fp)
            continue
        date = os.path.basename(fp)[:-5]
        keep = [r for r in rows if (date, str(r.get("stock_id"))) not in marked]
        if len(keep) != len(rows):
            d["stocks"] = keep
            if "count" in d:
                d["count"] = len(keep)
            raw = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
            with open(fp, "w", encoding="utf-8") as f:
                f.write(raw)

    log = {
        "repaired_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
        "rules": {
            "A": "high 缺失超過 50% 的快照視為非交易日或來源不完整，整檔刪除",
            "B": "代號開頭連續 >=3 天 o=h=l=c 且 volume 與首列相同 → 視為上市前／來源缺漏的補值，逐列刪除",
        },
        "removed_files": len(dead),
        "files": dead,
        "removed_padded_rows": len(marked),
        "padded_symbols": len(detail),
        "padded_detail": detail,
    }
    json.dump(log, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[repair] 完成：刪除 {len(dead)} 檔、{len(marked)} 列補值；紀錄於 {LOG}")
    print("[repair] 請接著重跑 build_kline.py 與 compute_indicators.py")


if __name__ == "__main__":
    main()
