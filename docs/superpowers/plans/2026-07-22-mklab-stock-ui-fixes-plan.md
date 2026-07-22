# mklab-stock UI Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix five reported UI issues in mklab-stock using component‑level refactor (Approach B) while preserving existing design system.

**Architecture:** Leverage existing CSS classes (.card, .grid, .drawer, .table-wrap) and add small utility classes (.text-wrap) and minor adjustments (min-height, drawer background/width, placeholder) to resolve the specific problems without restructuring the overall layout.

**Tech Stack:** HTML, CSS, vanilla JavaScript (MKLAB Web Components), Git.

## Global Constraints
- Must keep the project build‑time only (no Node/npm).
- Must not introduce new external dependencies.
- Must keep all existing functionality intact.
- Must maintain the responsive breakpoints already defined in component.css.
- All changes must be committed with descriptive messages and pushed to origin/main.
- Verification must be done locally via a simple HTTP server and visual inspection; no automated UI test suite is required.

---

### Task 1: Remove duplicate freshness banner (index.html)

**Files:**
- Modify: `/root/Documents/mklab-stock/index.html:26-28`

**Interfaces:** None (pure presentation change).

- [ ] **Step 1: Write verification script that fails if #yellowBanner still exists**
  ```bash
  #!/usr/bin/env bash
  if grep -q '<div id="yellowBanner"' /root/Documents/mklab-stock/index.html; then
    echo "FAIL: #yellowBanner still present"
    exit 1
  else
    echo "PASS"
  fi
  ```
- [ ] **Step 2: Run verification to confirm failure**
  ```
  chmod +x /tmp/check_yellowbanner.sh
  /tmp/check_yellowbanner.sh
  # Expected output: FAIL: #yellowBanner still present
  ```
- [ ] **Step 3: Remove the #yellowBanner lines (26‑28) and its comment**
  ```html
  <!-- Remove these lines:
  <div id="yellowBanner" class="yellow-banner" aria-live="polite">資料載入中…</div>
  -->
  ```
- [ ] **Step 4: Run verification to confirm pass**
  ```
  /tmp/check_yellowbanner.sh
  # Expected output: PASS
  ```
- [ ] **Step 5: Commit changes**
  ```bash
  cd /root/Documents/mklab-stock
  git add index.html
  git commit -m "fix: remove duplicate yellow banner on homepage"
  ```

### Task 2: Add text‑wrap utility and apply to industry card text

**Files:**
- Create/Modify: `/root/Documents/mklab-stock/assets/css/mklab-theme.css` (add .text-wrap)
- Modify: `/root/Documents/mklab-stock/mklab-stock-industry.html` (add .text-wrap to .nm, .chg, .meta)

**Interfaces:** .text-wrap class must be defined before use.

- [ ] **Step 1: Write verification that .text-wrap CSS does not exist**
  ```bash
  #!/usr/bin/env bash
  if ! grep -q '\.text-wrap' /root/Documents/mklab-stock/assets/css/mklab-theme.css; then
    echo "FAIL: .text-wrap missing"
    exit 1
  else
    echo "PASS"
  fi
  ```
- [ ] **Step 2: Run verification to confirm failure**
  ```
  chmod +x /tmp/check_textwrap.sh
  /tmp/check_textwrap.sh
  # Expected: FAIL
  ```
- [ ] **Step 3: Add .text-wrap rule to mklab-theme.css**
  ```css
  .text-wrap { word-break: break-word; max-width: 100%; display: block; }
  ```
- [ ] **Step 4: Run verification to confirm pass**
  ```
  /tmp/check_textwrap.sh
  # Expected: PASS
  ```
- [ ] **Step 5: Write verification that .nm, .chg, .meta have class text-wrap**
  ```bash
  #!/usr/bin/env bash
  FILE="/root/Documents/mklab-stock/mklab-stock-industry.html"
  if grep -q 'class="nm text-wrap"' "$FILE" && grep -q 'class="chg text-wrap"' "$FILE" && grep -q 'class="meta text-wrap"' "$FILE"; then
    echo "PASS"
  else
    echo "FAIL: missing text-wrap on one of .nm .chg .meta"
    exit 1
  fi
  ```
- [ ] **Step 6: Run verification to confirm failure**
  ```
  chmod +x /tmp/check_industry_classes.sh
  /tmp/check_industry_classes.sh
  # Expected: FAIL
  ```
- [ ] **Step 7: Edit mklab-stock-industry.html to add text-wrap to the three spans**
  - Change `<span class="nm">` → `<span class="nm text-wrap">`
  - Change `<span class="chg` → `<span class="chg text-wrap`
  - Change `<div class="meta">` → `<div class="meta text-wrap">`
- [ ] **Step 8: Run verification to confirm pass**
  ```
  /tmp/check_industry_classes.sh
  # Expected: PASS
  ```
- [ ] **Step 9: Commit changes**
  ```bash
  cd /root/Documents/mklab-stock
  git add assets/css/mklab-theme.css mklab-stock-industry.html
  git commit -m "fix: add text-wrap utility and apply to industry card text to prevent overflow"
  ```

### Task 3: Set min-height on industry cards for uniform grid

**Files:**
- Modify: `/root/Documents/mklab-stock/assets/css/mklab-theme.css` (add min-height to .icard)

**Interfaces:** .icard selector.

- [ ] **Step 1: Write verification that .icard does NOT have min-height**
  ```bash
  #!/usr/bin/env bash
  if grep -q '\.icart' /root/Documents/mklab-stock/assets/css/mklab-theme.css; then
    # dummy
    :
  fi
  if ! grep -A2 '\.icard {' /root/Documents/mklab-stock/assets/css/mklab-theme.css | grep -q 'min-height'; then
    echo "FAIL: .icard missing min-height"
    exit 1
  else
    echo "PASS"
  fi
  ```
  Simpler: just check absence of min-height.
  ```bash
  #!/usr/bin/env bash
  if grep -q '\.icard.*min-height' /root/Documents/mklab-stock/assets/css/mklab-theme.css; then
    echo "FAIL: min-height already present"
    exit 1
  else
    echo "PASS"
  fi
  ```
- [ ] **Step 2: Run verification to confirm failure**
  ```
  chmod +x /tmp/check_icard_minheight.sh
  /tmp/check_icard_minheight.sh
  # Expected: FAIL
  ```
- [ ] **Step 3: Add min-height:120px; to .icard rule**
  Locate `.icard { ... }` and insert `min-height:120px;`.
- [ ] **Step 4: Run verification to confirm pass**
  ```
  /tmp/check_icard_minheight.sh
  # Expected: PASS
  ```
- [ ] **Step 5: Commit changes**
  ```bash
  cd /root/Documents/mklab-stock
  git add assets/css/mklab-theme.css
  git commit -m "fix: set min-height on industry cards for uniform grid height"
  ```

### Task 4: Adjust drawer desktop styling (background and width)

**Files:**
- Modify: `/root/Documents/mklab-stock/assets/css/component.css` (desktop media query)

**Interfaces:** .drawer and .drawer-mask selectors.

- [ ] **Step 1: Write verification that desktop .drawer lacks background and max-width**
  ```bash
  #!/usr/bin/env bash
  FILE="/root/Documents/mklab-stock/assets/css/component.css"
  # Look for @media (min-width: 769px) block and check for background and max-width
  if ! grep -A10 '@media (min-width: 769px)' "$FILE" | grep -q 'background:'; then
    echo "FAIL: missing background in desktop drawer"
    exit 1
  fi
  if ! grep -A10 '@media (min-width: 769px)' "$FILE" | grep -q 'max-width:'; then
    echo "FAIL: missing max-width in desktop drawer"
    exit 1
  else
    echo "PASS"
  fi
  ```
  We'll invert: expect FAIL initially.
- [ ] **Step 2: Run verification to confirm failure**
  ```
  chmod +x /tmp/check_drawer_desktop.sh
  /tmp/check_drawer_desktop.sh
  # Expected: FAIL (missing background/max-width)
  ```
- [ ] **Step 3: Edit component.css: inside @media (min-width: 769px) add**
  ```css
  .drawer {
    background: var(--bg);
    max-width: 260px;
  }
  .drawer-mask { display: none !important; }
  ```
  Ensure we keep existing mobile styles untouched.
- [ ] **Step 4: Run verification to confirm pass**
  ```
  /tmp/check_drawer_desktop.sh
  # Expected: PASS
  ```
- [ ] **Step 5: Commit changes**
  ```bash
  cd /root/Documents/mklab-stock
  git add assets/css/component.css
  git commit -m "fix: give desktop drawer opaque background and limit width"
  ```

### Task 5: Add placeholder for research 財報摘要 table and hide/show logic

**Files:**
- Modify: `/root/Documents/mklab-stock/mklab-stock-research.html` (wrap table, add placeholder, update selectSym)

**Interfaces:** #finTablePlaceholder DOM element.

- [ ] **Step 1: Write verification that placeholder does NOT exist**
  ```bash
  #!/usr/bin/env bash
  if grep -q 'id="finTablePlaceholder"' /root/Documents/mklab-stock/mklab-stock-research.html; then
    echo "FAIL: placeholder already present"
    exit 1
  else
    echo "PASS"
  fi
  ```
- [ ] **Step 2: Run verification to confirm failure**
  ```
  chmod +x /tmp/check_research_placeholder.sh
  /tmp/check_research_placeholder.sh
  # Expected: FAIL
  ```
- [ ] **Step 3: Edit mklab-stock-research.html**
  - Wrap `<table id="finTable"></table>` in a `<div class="table-wrap" style="position:relative;">`
  - After the table, insert:
    ```html
    <div id="finTablePlaceholder" class="text-muted text-center py-4"
         style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;">
      請選擇個股以顯示財報摘要
    </div>
    ```
  - In `selectSym()` function, after the block that creates/updates `finTable`, add:
    ```js
    // hide placeholder when table has data
    const placeholder = document.getElementById('finTablePlaceholder');
    if (placeholder) placeholder.style.display = 'none';
    ```
- [ ] **Step 4: Run verification to confirm placeholder present**
  ```
  /tmp/check_research_placeholder.sh
  # Expected: PASS
  ```
- [ ] **Step 5: Write verification that selectSym contains the hide line**
  ```bash
  #!/usr/bin/env bash
  if grep -q 'placeholder.style.display.*=.*'"'none'" /root/Documents/mklab-stock/mklab-stock-research.html; then
    echo "PASS"
  else
    echo "FAIL: hide logic missing"
    exit 1
  fi
  ```
- [ ] **Step 6: Run verification to confirm failure**
  ```
  chmod +x /tmp/check_research_hide.sh
  /tmp/check_research_hide.sh
  # Expected: FAIL
  ```
- [ ] **Step 7: Apply the hide logic (step 3 already includes it)**
- [ ] **Step 8: Run verification to confirm pass**
  ```
  /tmp/check_research_hide.sh
  # Expected: PASS
  ```
- [ ] **Step 9: Commit changes**
  ```bash
  cd /root/Documents/mklab-stock
  git add mklab-stock-research.html
  git commit -m "fix: add placeholder and hide/show logic for research 財報摘要 table"
  ```

### Task 6: Run local verification and QA gate

**Files:** None (temporary).

- [ ] **Step 1: Start local server in background**
  ```bash
  cd /root/Documents/mklab-stock
  python3 -m http.server 8000 --bind 127.0.0.1 &
  SERVER_PID=$!
  ```
- [ ] **Step 2: Wait a moment, then open each page to visually inspect (manual)**
  - http://127.0.0.1:8000/ (homepage)
  - http://127.0.0.1:8000/mklab-stock-industry.html
  - http://127.0.0.1:8000/mklab-stock-research.html
  - Check that drawer works (click menu button).
- [ ] **Step 3: Stop the server**
  ```bash
  kill $SERVER_PID
  ```
- [ ] **Step 4: Run QA gate script**
  ```bash
  cd /root/Documents/mklab-stock
  python3 skills/qa-gate/qa_gate.py
  ```
  Expect output indicating no Critical errors (warnings are okay).
- [ ] **Step 5: If QA passes, commit any temporary files (none) and finalize**
  ```bash
  # No additional commit needed if all changes already committed.
  echo "All tasks completed and QA passed."
  ```

**Note:** The verification scripts are temporary and can be removed after the plan is executed, or kept in a temporary directory.

--- 

*End of plan.*