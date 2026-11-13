#!/usr/bin/env python3
"""
sanitize_snapshot.py — 對既有快照套用 data_rules 的單位/一致性修正（一次性修復 + 可重複執行）

用法：
  python3 skills/data/sanitize_snapshot.py            # 就地修正 data/stocks.json、data/us/*.json
  python3 skills/data/sanitize_snapshot.py --dry-run  # 只列出會改什麼

設計：
  - 只做「確定性」修正（EPS≤0 的 PE → null、美股 ytd ×100 還原、殖利率/淨值比超範圍 → null）。
  - 不做任何猜測性填值。股本為 0 無法在此修正，必須重新抓 TWSE 資產負債表（fetch_data.py）。
  - 冪等：重複執行結果不變。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import data_rules  # noqa: E402

TARGETS = {
    "stocks": os.path.join(ROOT, "data", "stocks.json"),
    "us_stocks": os.path.join(ROOT, "data", "us", "us-stocks.json"),
    "us_etfs": os.path.join(ROOT, "data", "us", "us-etfs.json"),
}


def main(dry_run=False):
    total = 0
    for name, path in TARGETS.items():
        if not os.path.exists(path):
            print(f"[skip] {name}: {path} 不存在")
            continue
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        doc = json.loads(raw)
        if name == "stocks":
            notes = []
            for rec in doc.get("stocks", []):
                n = data_rules.sanitize_stock_record(rec)
                if n:
                    notes.append((rec.get("sym"), n))
        elif name == "us_stocks":
            notes = [(None, [x]) for x in data_rules.sanitize_us_stocks_doc(doc)]
        else:
            notes = [(None, [x]) for x in data_rules.sanitize_us_etfs_doc(doc)]
        print(f"[{name}] 修正 {len(notes)} 項")
        for sym, n in notes[:8]:
            print(f"    {sym + ': ' if sym else ''}{'; '.join(n)}")
        if len(notes) > 8:
            print(f"    ...（其餘 {len(notes) - 8} 項略）")
        total += len(notes)
        if notes and not dry_run:
            # 保留原檔格式（避免整檔 diff）：pretty 檔用 indent=2 + 結尾換行；compact 檔用緊湊格式無結尾換行
            pretty = raw.startswith("{\n")
            text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n" if pretty \
                else json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
    print(("[dry-run] " if dry_run else "") + f"合計 {total} 筆")
    return 0


if __name__ == "__main__":
    sys.exit(main(dry_run="--dry-run" in sys.argv))
