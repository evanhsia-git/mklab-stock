#!/usr/bin/env python3
"""
歷史快照修復（一次性）：刪除「高低價整日缺失」的快照檔。

這類檔案是休市日或來源不完整時寫入的（TWSE 回傳舊資料、缺 high/low，收盤值錯誤），
不是真實交易日，會造成回測與指標的單點離群值。判定規則：high 缺失超過 50% 即刪除。
刪除清單與原因寫入 data/history-repair-log.json，供追溯。
"""
import datetime as dt
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HIST = os.path.join(ROOT, "data", "history")
LOG = os.path.join(ROOT, "data", "history-repair-log.json")

removed = []
for fp in sorted(glob.glob(os.path.join(HIST, "*.json"))):
    d = json.load(open(fp, encoding="utf-8"))
    rows = d.get("stocks", [])
    if not rows:
        continue
    miss = sum(1 for r in rows if r.get("high") is None)
    if miss / len(rows) > 0.5:
        removed.append({"file": os.path.basename(fp), "rows": len(rows), "missing_high_low": miss})
        os.remove(fp)

log = {
    "repaired_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
    "rule": "high 缺失超過 50% 的快照視為非交易日或來源不完整，予以刪除",
    "removed_count": len(removed),
    "removed": removed,
}
json.dump(log, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"已刪除 {len(removed)} 個無效快照，紀錄於 {LOG}")
