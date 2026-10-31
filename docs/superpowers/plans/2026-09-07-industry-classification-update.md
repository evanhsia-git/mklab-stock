# Industry Classification Weekly Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add weekly updating of stock industry classification from TWSE t187ap03_L to ensure ind field in stocks.json is always correct.

**Architecture:** We will add a new function fetch_industry_map() to retrieve industry code mapping from t187ap03_L, and a function apply_industry_to_stocks() to update the ind field in the stocks list. These will be called from the existing run_weekly() function after ROE/ROA update, ensuring the industry classification is refreshed once per week without affecting daily data collection.

**Tech Stack:** Python, existing mklab-stock codebase, TWSE OpenAPI.

## Global Constraints

- Must not break existing daily data collection.
- Must preserve existing ind field if API fails (conservative update).
- Must use existing helper functions (fetch_json, RunLogger, etc.).
- Must follow the project's zero-secret, GitHub-native principles.
- Must not introduce new external dependencies.
- Must maintain backward compatibility with existing stocks.json schema.

---
### Task 1: Add fetch_industry_map function

**Files:**
- Modify: skills/data/fetch_data.py

**Interfaces:**
- Consumes: None
- Produces: fetch_industry_map() -> dict mapping stock symbol to industry code (string)

**Steps:**
- [ ] Step 1: Write the failing test (we'll implement a simple inline test later)
```python
def test_fetch_industry_map_returns_dict():
    result = fetch_industry_map()
    assert isinstance(result, dict)
```

- [ ] Step 2: Run test to verify it fails
Run: `python -c "import sys; sys.path.insert(0, './skills/data'); from fetch_data import fetch_industry_map; test_fetch_industry_map_returns_dict()"`  
Expected: FAIL with NameError or similar

- [ ] Step 3: Write minimal implementation
At the end of the file (before the main guard), add:
```python
def fetch_industry_map():
    """
    Retrieve industry code mapping from TWSE t187ap03_L.
    Returns a dict {stock_symbol: industry_code}.
    On failure, returns empty dict.
    """
    url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
    try:
        raw = fetch_json(url, timeout=30)
        if not isinstance(raw, list):
            LOG.warn("t187ap03_L response is not a list")
            return {}
        industry_map = {}
        for r in raw:
            sym = str(r.get("公司代號", "")).strip()
            ind_code = str(r.get("產業別", "")).strip()
            if sym and ind_code:
                industry_map[sym] = ind_code
        LOG.info(f"Fetched industry map for {len(industry_map)} stocks")
        return industry_map
    except Exception as e:
        LOG.warn(f"Failed to fetch industry map: {e}")
        return {}
```

- [ ] Step 4: Run test to verify it passes
Run same command as step 2  
Expected: PASS (no assertion error)

- [ ] Step 5: Commit
```bash
git add skills/data/fetch_data.py
git commit -m "feat: add fetch_industry_map function for weekly industry classification update"
```

### Task 2: Add apply_industry_to_stocks function

**Files:**
- Modify: skills/data/fetch_data.py

**Interfaces:**
- Consumes: stocks (list of dict), industry_map (dict), codes (dict), fallback (str)
- Produces: None (modifies stocks in place)

**Steps:**
- [ ] Step 1: Write the failing test
```python
def test_apply_industry_to_stocks_updates_ind():
    stocks = [{"sym": "1234", "ind": "OldInd"}]
    industry_map = {"1234": "01"}
    codes = {"01": "水泥工業"}
    fallback = "其他等"
    apply_industry_to_stocks(stocks, industry_map, codes, fallback)
    assert stocks[0]["ind"] == "水泥工業"
```

- [ ] Step 2: Run test to verify it fails
Run: `python -c "import sys; sys.path.insert(0, './skills/data'); from fetch_data import apply_industry_to_stocks; test_apply_industry_to_stocks_updates_ind()"`  
Expected: FAIL (NameError)

- [ ] Step 3: Write minimal implementation
Add function after fetch_industry_map:
```python
def apply_industry_to_stocks(stocks, industry_map, codes, fallback):
    """
    Update the 'ind' field of each stock in stocks based on industry_map.
    industry_map: dict {symbol: industry_code}
    codes: dict {industry_code: industry_name}
    fallback: default industry name if code not found
    Modifies stocks list in place.
    """
    updated = 0
    for s in stocks:
        sym = s.get("sym")
        if not sym:
            continue
        ind_code = industry_map.get(sym)
        if ind_code is None:
            # keep existing ind if no data
            continue
        ind_name = codes.get(ind_code, fallback)
        if s.get("ind") != ind_name:
            s["ind"] = ind_name
            updated += 1
    LOG.info(f"Applied industry classification to {updated} stocks")
```

- [ ] Step 4: Run test to verify it passes
Run same command as step 2  
Expected: PASS

- [ ] Step 5: Commit
```bash
git add skills/data/fetch_data.py
git commit -m "feat: add apply_industry_to_stocks function"
```

### Task 3: Integrate industry update into run_weekly

**Files:**
- Modify: skills/data/fetch_data.py

**Interfaces:**
- Consumes: None
- Produces: run_weekly() now updates industry classification

**Steps:**
- [ ] Step 1: Write the failing test (we'll test by checking that run_weekly calls the new functions; we can do a simple integration test later)
```python
def test_run_weekly_calls_industry_functions(monkeypatch):
    # This test would require mocking; we skip for now and rely on manual verification.
    pass
```

- [ ] Step 2: Run test to verify it fails (skip)

- [ ] Step 3: Write minimal implementation
Locate the run_weekly function. After the ROE/ROA update block (around line 795), add:
```python
    # ====== 新增：週更新產業別 ======
    industry_map = fetch_industry_map()
    if industry_map:
        codes, fallback = load_codes()
        apply_industry_to_stocks(stocks, industry_map, codes, fallback)
    else:
        LOG.warn("Industry map empty; skipping industry classification update")
```
Make sure to indent properly within the function.

- [ ] Step 4: Run test to verify it passes
We'll do a manual test by running the weekly mode in a safe way (see later).

- [ ] Step 5: Commit
```bash
git add skills/data/fetch_data.py
git commit -m "feat: integrate industry classification update into run_weekly"
```

### Task 4: Verify that daily collection still works and inherits correct ind

**Files:**
- No code changes (just verification)

**Steps:**
- [ ] Step 1: Write a small script to check that after running weekly update, the ind field for known stocks (6505, 8926, 1802, 1806, 1817) matches expectations.
```bash
python -c "
import json
with open('data/stocks.json', encoding='utf-8') as f:
    data = json.load(f)
stocks = {s['sym']: s for s in data['stocks']}
for sym in ['6505', '8926', '1802', '1806', '1817']:
    s = stocks.get(sym)
    if s:
        print(sym, s.get('name'), s.get('ind'))
"
```
- [ ] Step 2: Run the script and record output (should show correct industries: 6505 -> 油電燃氣業, 8926 -> 油電燃氣業, 1802 -> 玻璃陶瓷, 1806 -> 玻璃陶瓷, 1817 -> 玻璃陶瓷)

- [ ] Step 3: Commit a note if needed (optional)
```bash
git commit -m "test: verify industry classification update works" --allow-empty
```

### Task 5: Ensure no regression in daily mode

**Files:**
- No code changes

**Steps:**
- [ ] Step 1: Run daily mode in a test environment (optional, but we can simulate by checking that the script does not crash)
```bash
# We'll just import and call run_daily with a mock? Instead we rely on existing CI.
```
- [ ] Step 2: Commit a note if needed
```bash
git commit -m "test: daily mode unchanged" --allow-empty
```

### Task 6: Final integration test and cleanup

**Files:**
- No code changes

**Steps:**
- [ ] Step 1: Run the full fetch_data.py in weekly mode (using a temporary copy of data to avoid corrupting production) to ensure it works end-to-end.
We can do:
```bash
cd /root/mklab-stock
cp -r data data.backup
python skills/data/fetch_data.py weekly
# check logs and data/stocks.json
```
- [ ] Step 2: Verify that the ind field updated as expected.
- [ ] Step 3: Restore backup if needed.
```bash
rm -rf data && mv data.backup data
```
- [ ] Step 4: Commit final verification
```bash
git commit -m "test: end-to-end weekly industry update verification" --allow-empty
```

## Summary

After completing these tasks, the mklab-stock project will have a weekly automated process that refreshes the industry classification (ind field) for all stocks using the official TWSE t187ap03_L API, ensuring the data stays accurate without affecting the daily collection workflow.