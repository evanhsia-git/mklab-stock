# Fake Data Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all fake/padded data from history/kline/stocks.json, recompute indicators, add regression test to prevent recurrence, and verify frontend "listedBase" marker works correctly.

**Architecture:** Three-phase pipeline: (1) repair_history.py removes fake rows from history/*.json and deletes 14 fake snapshot files (2025-07-14~07-31); (2) build_kline.py rebuilds kline files with strip_padded_prefix(); (3) compute_indicators.py recalculates MA/RSI/MACD/KD/returns. New test validates no fake data exists.

**Tech Stack:** Python 3, existing skills/data scripts, pytest for tests, Node.js for JS syntax checks.

## Global Constraints

- Data integrity: never fabricate data; missing values stay null (display "—" or "資料不足")
- tw_stock_all.db is READ-ONLY (never modify)
- Pre-op git commit already done (813288df)
- 1440 in-scope securities only (TWSE stock + TWSE ETF + TPEX ETF)
- Fake detection: ≥3 consecutive days with open=high=low=close AND same volume as first row
- 009816 special case: 142 fake rows (close=15.0, vol=367256179) from 2025-07-14 to 2026-02-04 → remove all, keep from 2026-02-03 (close=10.27)
- Frontend: mklab-returns.js already has `listedBase` and `(上市首日)` marker for when base date < first trading day

---

### Task 1: Run repair_history.py to clean history/*.json

**Files:**
- Modify: `skills/data/repair_history.py` (already has logic, just execute)
- Modify: `data/history/*.json` (14 fake snapshots deleted, padded rows removed)
- Test: `tests/test_known_errors.py` (existing checks will pass)

**Interfaces:**
- Consumes: data/history/*.json (323 files)
- Produces: cleaned history/*.json, data/history-repair-log.json

- [ ] **Step 1: Run repair_history.py (dry-run first to verify)**

```bash
cd /root/mklab-stock && python3 skills/data/repair_history.py --dry-run
```

Expected: Lists ~14 dead files (2025-07-14~07-31), ~73 symbols with padded rows, ~26,905 padded rows to remove.

- [ ] **Step 2: Run repair_history.py (actual execution)**

```bash
cd /root/mklab-stock && python3 skills/data/repair_history.py
```

Expected: Deletes 14 fake snapshot files, removes padded rows from remaining files, writes history-repair-log.json.

- [ ] **Step 3: Verify history cleanup**

```bash
cd /root/mklab-stock && python3 -c "
import glob, json, os
# Verify 14 fake files gone
fake_files = [f for f in sorted(glob.glob('data/history/*.json')) if '20250714' <= os.path.basename(f)[:8] <= '20250731']
print(f'Fake snapshot files remaining: {len(fake_files)}')
# Verify 009816 cleaned
h = json.load(open('data/history/20260203.json', encoding='utf-8'))
s = next((x for x in h['stocks'] if x['stock_id']=='009816'), None)
print(f'009816 in 20260203: {s}')
"
```

Expected: 0 fake snapshot files remaining; 009816 first appears in 20260203 with close=10.27.

- [ ] **Step 4: Commit history cleanup**

```bash
cd /root/mklab-stock && git add data/history/ data/history-repair-log.json && git commit -m "fix: remove 14 fake snapshots + padded rows from history/"
```

---

### Task 2: Run build_kline.py to rebuild kline files

**Files:**
- Modify: `skills/data/build_kline.py` (already has strip_padded_prefix, just execute)
- Modify: `data/kline/*.json` (1445 files rebuilt)
- Test: `tests/test_known_errors.py` (kline fake data checks)

**Interfaces:**
- Consumes: cleaned data/history/*.json, existing data/kline/*.json (for merge)
- Produces: rebuilt data/kline/*.json with strip_padded_prefix applied

- [ ] **Step 1: Run build_kline.py**

```bash
cd /root/mklab-stock && python3 skills/data/build_kline.py
```

Expected: Rebuilds 1445 kline files, prints total rows count.

- [ ] **Step 2: Verify 009816 kline starts from real first trading day**

```bash
cd /root/mklab-stock && python3 -c "
import json
d = json.load(open('data/kline/009816.json', encoding='utf-8'))
print(f'009816 kline rows: {len(d[\"rows\"])}')
print(f'First row: {d[\"rows\"][0]}')
print(f'Last row: {d[\"rows\"][-1]}')
# Verify no fake rows (close=15.0)
fake = [r for r in d['rows'] if r[4] == 15.0]
print(f'Fake rows (close=15.0): {len(fake)}')
"
```

Expected: rows=183, first=['2026-02-03', 10.31, 10.6, 10.15, 10.27], fake rows=0.

- [ ] **Step 3: Verify no kline files have padded prefix**

```bash
cd /root/mklab-stock && python3 -c "
import glob, json
padded = []
for f in sorted(glob.glob('data/kline/*.json')):
    d = json.load(open(f, encoding='utf-8'))
    rows = d.get('rows', [])
    if len(rows) >= 3:
        c0 = rows[0][4]
        n = sum(1 for r in rows if r[1]==r[2]==r[3]==r[4]==c0)
        if n >= 3:
            padded.append((os.path.basename(f)[:-5], n))
print(f'Kline files with padded prefix: {len(padded)}')
if padded:
    for p in padded[:5]: print(f'  {p}')
"
```

Expected: 0 kline files with padded prefix.

- [ ] **Step 4: Commit kline rebuild**

```bash
cd /root/mklab-stock && git add data/kline/ && git commit -m "fix: rebuild kline after history cleanup (strip_padded_prefix)"
```

---

### Task 3: Run compute_indicators.py to recalculate MA/RSI/MACD/KD/returns

**Files:**
- Modify: `skills/data/compute_indicators.py` (already has logic, just execute)
- Modify: `data/stocks.json` (indicators updated for all 1440 securities)
- Test: `tests/test_known_errors.py` (indicator coverage checks)

**Interfaces:**
- Consumes: cleaned data/history/*.json, rebuilt data/kline/*.json
- Produces: updated data/stocks.json with MA/RSI/MACD/KD/chg_* fields

- [ ] **Step 1: Run compute_indicators.py**

```bash
cd /root/mklab-stock && python3 skills/data/compute_indicators.py
```

Expected: Updates ~1440 securities with indicators, prints count.

- [ ] **Step 2: Verify 009816 indicators are correct (null where history insufficient)**

```bash
cd /root/mklab-stock && python3 -c "
import json
stocks = json.load(open('data/stocks.json', encoding='utf-8'))
s = next(x for x in stocks['stocks'] if x['sym']=='009816')
print(f'009816 ma5: {s.get(\"ma5\")}')
print(f'009816 ma10: {s.get(\"ma10\")}')
print(f'009816 ma20: {s.get(\"ma20\")}')
print(f'009816 ma30: {s.get(\"ma30\")}')
print(f'009816 rsi14: {s.get(\"rsi14\")}')
print(f'009816 macd_dif: {s.get(\"macd_dif\")}')
print(f'009816 chg_1m: {s.get(\"chg_1m\")}')
print(f'009816 chg_3m: {s.get(\"chg_3m\")}')
print(f'009816 chg_6m: {s.get(\"chg_6m\")}')
print(f'009816 chg_1y: {s.get(\"chg_1y\")}')
print(f'009816 pos52w_level: {s.get(\"pos52w_level\")}')
"
```

Expected: MA/RSI/MACD may be null (insufficient history), chg_* correctly computed from real data.

- [ ] **Step 3: Verify overall indicator coverage**

```bash
cd /root/mklab-stock && python3 -c "
import json
stocks = json.load(open('data/stocks.json', encoding='utf-8'))
s_list = [x for x in stocks['stocks'] if x.get('security_type')=='stock']
print(f'General stocks: {len(s_list)}')
for k in ['chg_1m','chg_3m','chg_6m','chg_1y']:
    n = sum(1 for s in s_list if s.get(k) is not None)
    print(f'{k}: {n}/{len(s_list)} = {n/len(s_list)*100:.1f}%')
"
```

Expected: Coverage ≥85% for chg_1m/3m/6m/1y.

- [ ] **Step 4: Commit indicators update**

```bash
cd /root/mklab-stock && git add data/stocks.json && git commit -m "fix: recompute indicators after fake data cleanup"
```

---

### Task 4: Add regression test for fake data detection

**Files:**
- Create: `tests/test_fake_data_regression.py` (new test file)
- Test: pytest integration

**Interfaces:**
- Consumes: data/history/*.json, data/kline/*.json
- Produces: test pass/fail

- [ ] **Step 1: Create tests/test_fake_data_regression.py**

```python
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
        dt = os.path.basename(fp)[:-5]
        for r in json.load(open(fp, encoding="utf-8")).get("stocks", []):
            sym = str(r.get("stock_id"))
            snaps.setdefault(sym, []).append((dt, r))

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
```

- [ ] **Step 2: Run the new regression test**

```bash
cd /root/mklab-stock && python3 tests/test_fake_data_regression.py
```

Expected: All checks PASS.

- [ ] **Step 3: Also run existing test_known_errors.py to ensure no regressions**

```bash
cd /root/mklab-stock && python3 tests/test_known_errors.py
```

Expected: All 400+ checks PASS.

- [ ] **Step 4: Commit new test**

```bash
cd /root/mklab-stock && git add tests/test_fake_data_regression.py && git commit -m "test: add fake data regression test (history + kline)"
```

---

### Task 5: Verify frontend "listedBase" marker works (research page)

**Files:**
- Verify: `assets/js/mklab-returns.js` (already has logic)
- Test: Manual browser check or JS test

**Interfaces:**
- Consumes: data/kline/*.json
- Produces: chart with "（上市首日）" marker when base date < first trading day

- [ ] **Step 1: Verify mklab-returns.js has listedBase logic**

```bash
cd /root/mklab-stock && python3 -c "
with open('assets/js/mklab-returns.js', encoding='utf-8') as f:
    content = f.read()
print('listedBase in JS:', 'listedBase' in content)
print('(上市首日) in JS:', '（上市首日）' in content)
print('bi < 0 fallback:', 'if (bi < 0) { bi = 0; listedBase = true; }' in content)
"
```

Expected: All three True.

- [ ] **Step 2: Quick JS syntax check**

```bash
cd /root/mklab-stock && node --check assets/js/mklab-returns.js
```

Expected: Exit code 0.

- [ ] **Step 3: (Optional) Manual verify in browser - open mklab-stock-research.html with 009816 and YTD period**

Expected: Chart shows base date as 2026-02-03 with "（上市首日）" label, YTD return ≈ +41.6% (from 10.27 to ~14.84).

---

### Task 6: Final verification and summary

- [ ] **Step 1: Run full test suite**

```bash
cd /root/mklab-stock && python3 tests/test_known_errors.py && python3 tests/test_fake_data_regression.py
```

Expected: All PASS.

- [ ] **Step 2: Verify git status clean**

```bash
cd /root/mklab-stock && git status
```

Expected: Only tracked files modified, no untracked.

- [ ] **Step 3: Summary stats**

```bash
cd /root/mklab-stock && python3 -c "
import glob, json, os
# History
h = len(glob.glob('data/history/*.json'))
# Kline
k = len(glob.glob('data/kline/*.json'))
# Stocks
s = json.load(open('data/stocks.json', encoding='utf-8'))
stocks = s['stocks']
print(f'History files: {h}')
print(f'Kline files: {k}')
print(f'Stocks in scope: {len(stocks)}')
print(f'  stock: {sum(1 for x in stocks if x.get(\"security_type\")==\"stock\")}')
print(f'  etf: {sum(1 for x in stocks if x.get(\"security_type\")==\"etf\")}')
print(f'  unverified: {sum(1 for x in stocks if x.get(\"security_type\")==\"unverified\")}')
# 009816 check
d = json.load(open('data/kline/009816.json', encoding='utf-8'))
print(f'009816 kline rows: {len(d[\"rows\"])}, first: {d[\"rows\"][0]}, last: {d[\"rows\"][-1]}')
"
```

Expected: History ~309 files (323-14), Kline 1440+, Stocks 1440, 009816 correct.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-11-12-fake-data-cleanup-plan.md`. Two execution options:**

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**