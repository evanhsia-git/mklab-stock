#!/usr/bin/env python3
"""防回歸測試：偵測 data/history/ 與 data/kline/ 是否含有偽造補值列。

判定規則：連續 ≥3 天 open=high=low=close 且成交量固定（與首列相同） → 視為偽造。

執行：python3 tests/test_fake_data_regression.py
或：pytest tests/test_fake_data_regression.py -v
"""
import glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

def check(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"{status:4}  {name}  {detail}")
    return ok

def main():
    all_ok = True

    # --- History: 前導同價同量 ---
    snaps = {}
    for fp in sorted(glob.glob("data/history/*.json")):
        d = json.load(open(fp, encoding="utf-8"))
        stocks = d.get("stocks", [])
        for r in stocks:
            sym = str(r.get("stock_id"))
            snaps.setdefault(sym, []).append((os.path.basename(fp), r))

    hpad = []
    for sym, items in snaps.items():
        items.sort(key=lambda x: x[0])
        if len(items) < 3:
            continue
        c0, v0 = items[0][1].get("close"), items[0][1].get("volume")
        n = 0
        for _, r in items:
            flat = r.get("open") == r.get("high") == r.get("low") == r.get("close")
            same = r.get("close") == c0 and r.get("volume") == v0
            if flat and same:
                n += 1
            else:
                break
        if n >= 3:
            hpad.append((sym, n))

    all_ok &= check("History 無前導同價同量補值列", not hpad, f"{len(hpad)} 檔: {hpad[:5]}")

    # --- Kline: 前導同價 (kline 無 volume 欄，只能用價格形狀) ---
    kpad = []
    for fp in sorted(glob.glob("data/kline/*.json")):
        rows = json.load(open(fp, encoding="utf-8")).get("rows", [])
        if len(rows) < 3:
            continue
        c0 = rows[0][4]
        n = 0
        for r in rows:
            if r[1] == r[2] == r[3] == r[4] == c0:
                n += 1
            else:
                break
        if n >= 3:
            kpad.append((os.path.basename(fp)[:-5], n))

    all_ok &= check("Kline 無前導同價補值列", not kpad, f"{len(kpad)} 檔: {kpad[:5]}")

    # --- 快照檔：不得有 2025-07-14 ~ 07-31 這 14 份全假快照 ---
    fake_dates = [f for f in sorted(glob.glob("data/history/*.json"))
                  if "20250714" <= os.path.basename(f)[:8] <= "20250731"]
    all_ok &= check("無 2025-07-14~07-31 全假快照檔", len(fake_dates) == 0, f"殘留 {len(fake_dates)} 檔")

    # --- 009816 特例：kline 必須從 2026-02-03 真實首日開始 ---
    d = json.load(open("data/kline/009816.json", encoding="utf-8"))
    first = d["rows"][0]
    all_ok &= check("009816 kline 首列為 2026-02-03 close=10.27",
                    first[0] == "2026-02-03" and abs(first[4] - 10.27) < 0.01,
                    f"實際: {first}")

    print(f"\n合計: {'全部通過' if all_ok else '有失敗'}")
    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()