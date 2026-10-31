# mklab-stock UI Fixes Design (Approach B – Component‑Level Refactor)

## Goal
Resolve the five reported UI issues while maintaining consistency with the existing MKLAB component system and keeping changes minimal and maintainable.

## Issues
1. Duplicate “資料以 … 收盤為準” text on homepage.
2. Industry card text overflowing its grid cell.
3. Drawer background transparent on desktop and width not constrained.
4. Research page財報摘要 table not shown until a stock is selected.
5. Industry card heights inconsistent causing uneven grid.

## Chosen Approach – B (Component‑Level Refactor)
Leverage existing component classes (`.card`, `.grid`, `.drawer`, `.table-wrap`) and introduce small, reusable utility classes where needed. This keeps the design system intact, reduces duplicated CSS, and improves future extensibility.

## Detailed Changes

### 1. Homepage – Remove duplicate freshness banner
- **File**: `index.html`
- **Change**: Delete the `#yellowBanner` element (lines 26‑28) and keep only the `.freshness` element for the build‑time message.
- **Result**: Single source of truth for data freshness text.

### 2. Industry Card – Prevent text overflow
- **Files**: `mklab-stock-industry.html`
- **Change**: Add utility class `.text-wrap` to elements that may contain long text (`.nm`, `.chg`, `.meta`). Define `.text-wrap` in `assets/css/mklab-theme.css`:
  ```css
  .text-wrap { word-break: break-word; max-width: 100%; display: block; }
  ```
- **Result**: Text wraps inside the card instead of spilling out.

### 3. Industry Card – Uniform height
- **File**: `assets/css/mklab-theme.css`
- **Change**: Add `min-height: 120px;` to the `.icard` rule (already present in mobile media query; move to base `.icard`).
- **Result**: All cards share a minimum height, giving a clean grid layout.

### 4. Drawer – Desktop background and width constraint
- **File**: `assets/css/component.css`
- **Changes**:
  - In the desktop media query (`@media (min-width: 769px)`), add:
    ```css
    .drawer {
      background: var(--bg);   /* opaque dark background */
      max-width: 260px;        /* prevent full‑width stretch */
    }
    .drawer-mask { display: none !important; }
    ```
  - Keep existing mobile styles unchanged.
- **Result**: Drawer has a solid background on desktop, does not stretch to full width, and mobile behavior remains intact.

### 5. Research Page – Show placeholder until stock selected
- **File**: `mklab-stock-research.html`
- **Changes**:
  - Wrap `#finTable` in a `<div class="table-wrap" style="position:relative;">`.
  - Add a placeholder `<div id="finTablePlaceholder" class="text-muted text-center py-4" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;">請選擇個股以顯示財報摘要</div>`.
  - In `selectSym()` after successfully creating/updating `finTable`, set `placeholder.style.display = 'none'`.
  - Ensure placeholder is shown on init (already present).
- **Result**: User sees a friendly prompt before selecting a stock; table appears after data load.

### 6. Shared Utility – Text wrapping (optional reuse)
- **File**: `assets/css/mklab-theme.css`
- Add `.text-wrap` as described above; can be reused elsewhere (e.g., research info card if needed).

## Implementation Steps (to be turned into a plan)
1. Backup original files.
2. Edit `index.html` to remove `#yellowBanner`.
3. Update `assets/css/mklab-theme.css`:
   - Add `.text-wrap`.
   - Add `min-height:120px;` to `.icard`.
4. Update `assets/css/component.css` for drawer desktop styles.
5. Edit `mklab-stock-industry.html` to apply `.text-wrap` to `.nm`, `.chg`, `.meta`.
6. Edit `mklab-stock-research.html` to wrap table, add placeholder, and modify `selectSym()` to hide placeholder.
7. Run local dev server (`python3 -m http.server 8000`) and verify each issue is resolved.
8. Run QA gate (`python3 skills/qa-gate/qa_gate.py`) and ensure no new critical errors.
9. Commit changes with descriptive message and push to `origin/main`.

## Verification Checklist
- [ ] Homepage shows only one freshness line.
- [ ] Industry cards text stays inside cell on narrow screens.
- [ ] Industry cards have equal minimum height.
- [ ] Desktop drawer has dark background and limited width; mobile drawer unchanged.
- [ ] Research page displays placeholder until a stock is chosen, then table appears.
- [ ] No regression in other pages (market, screener, watchlist, help, log).
- [ ] QA gate passes (0 Critical warnings).

## Risks & Mitigations
- **Risk**: CSS changes may affect other components using `.icard` or `.text-wrap`.
  - **Mitigation**: Use specific selectors (`.icard` only) and test all pages.
- **Risk**: Removing `#yellowBanner` may break any JS that references it.
  - **Mitigation**: Search codebase for `yellowBanner`; none found aside from the HTML element.
- **Risk**: Placeholder may flash if data loads slowly.
  - **Mitigation**: Placeholder is shown by default and hidden only after table has rows.

## References
- Existing MKLAB component definitions in `assets/css/mklab-theme.css` and `assets/css/component.css`.
- Current HTML structure of `index.html`, `mklab-stock-industry.html`, `mklab-stock-research.html`.