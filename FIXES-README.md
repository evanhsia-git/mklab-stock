# mklab-stock 修復說明（2026-09-17）

這份 zip 只包含**改動過的檔案**，請直接覆蓋到 repo 對應路徑後 commit push：

```
mklab-stock-industry.html
mklab-stock-research.html
mklab-stock-watchlist.html
assets/css/component.css
skills/data/fetch_data.py
```

---

## 1. 表格/樣式跑掉了

### (a) Watchlist 頁「價格提醒」輸入框 — 真正的根因
`mklab-stock-watchlist.html` 的「目標價 / 停損價 / 儲存」那一排，原本用：

```html
<div class="flex-row gap-2" style="margin-bottom:8px;">
  <input ... class="form-input flex-1">
  <span class="flex-center">~</span>
  <input ... class="form-input flex-1">
  <button ... class="btn btn-primary btn-sm">儲存</button>
</div>
```

`flex-row` / `gap-2` / `form-input` / `flex-1` / `flex-center` 這幾個 class **在全站 CSS 裡完全沒有定義**（應該是打成 `form-input`，正確應該是 `.field-input`，容器也漏用了既有的 `.row-input`）。結果就是這排輸入框變成瀏覽器預設白底樣式，跟深色主題不搭，手機版也不會自動換行堆疊。

已改成跟其他頁面（research / screener / compare / dividend / portfolio）一致的既有寫法：

```html
<div class="row-input" style="margin-bottom:8px;">
  <input id="alertTargetPrice" placeholder="目標價">
  <span>~</span>
  <input id="alertStopLossPrice" placeholder="停損價">
  <button onclick="savePriceAlert()">儲存</button>
</div>
```

### (b) 全站掃描 — 其他「HTML 用了但 CSS 沒定義」的 class
用腳本比對全部 13 個頁面用到的 class 名稱、以及每個頁面的 `<style>` 內嵌區塊 + 4 個共用 CSS 檔，抓出這些從未被定義過的 class：

- `footer-inner`（每一頁的 footer 都有用到）
- `text-sm`、`text-center`、`py-2`、`py-4`、`py-6`、`mt-2`（research / help / digest / portfolio 頁的說明文字、K 線載入中文字等）
- `chk-mb`（screener 篩選條件的間距）
- `cmp-rm`（compare 頁比較清單的移除鍵）
- `heatmap-table`（industry 頁熱力圖表格）
- `btn` / `btn-ghost` / `btn-secondary`（research 頁 K 線工具列按鈕；因為工具列本身有 `.kline-toolbar button` 這條規則墊底，視覺上目前沒壞，但這幾個 class 本身仍是空的，順手一起補上避免以後單獨拿出來用時又壞掉）

已在 `assets/css/component.css` 最後新增一個區塊，把上面這些全部補上定義（顏色/間距都沿用現有的 CSS 變數，跟深色主題一致）。

**沒有改到的部分**：`hamburger`（手機選單的☰圖示）這個 class 本身雖然也沒有定義，但它外層的 `.mobile-menu-btn` 已經有完整樣式（大小/顏色/置中），所以視覺上沒有實際影響，這次只加了一行 `line-height:1` 保險，沒有大改。

---

## 2. 首頁「韓國 KOSPI」抓不到資料 — 資料管線的 bug

`skills/data/fetch_data.py` 的 `run_indices()` 裡：

```python
if "markets" in cfg:
    indices_cfg = []
    etfs_cfg = []
    for m in cfg["markets"]:
        indices_cfg.extend(m.get("indices", []))   # 這裡已經正確展平，包含韓國 KOSPI (^KS11)
        etfs_cfg.extend(m.get("etfs", []))
    ...

def build(group_key):
    for item in cfg.get(group_key, []):   # 但這裡又繞回去讀舊版扁平結構，根本沒用到上面展平好的清單
        ...

indices = build("indices")   # 永遠讀不到韓國
etfs = build("etfs")
```

`indices-config.json` 裡韓國 KOSPI 是定義在新版 `markets` 結構裡，展平時有正確抓到，但 `build()` 卻又重新去讀 `cfg["indices"]`（舊版扁平清單，裡面沒有韓國），等於白算，KOSPI 永遠是 16 個指數之外的那一個，資料當然是空的。

已修正為：

```python
def build(items):        # 改成直接吃清單，不再自己重新去 cfg 找
    for item in items:
        ...

indices = build(indices_cfg)   # 用上面已經展平好、包含韓國的清單
etfs = build(etfs_cfg)
```

⚠️ **這個修正只解決程式邏輯**，實際的 `data/indices.json` 資料要等下一次 GitHub Actions 排程跑完 `fetch_data.py` 後才會真的補上 KOSPI 數值（我這邊的環境沒有對外的市場資料源，沒辦法直接重新產生資料檔）。

---

## 3. Research 頁「個股筆記功能已移至 Portfolio 頁」— 已移除

`mklab-stock-research.html` 裡原本有一段：

```html
<p class="muted-small-top" id="notesLinkHint" style="display:none;">
  📝 個股筆記功能已移至 <a class="link" href="mklab-stock-portfolio.html">Portfolio 頁</a>
</p>
```

預設是隱藏的，但選股後的 `showStock()` 函式裡有這兩行會主動把它打開：

```js
const hint = document.getElementById('notesLinkHint');
if (hint) hint.style.display = 'block';
```

已把這個 `<p>` 元素和對應的兩行 JS 一起刪除，選股後不會再出現這句提示。

---

## 4. Industry 頁產業成分股表缺「市值」欄 — 已加上

`renderDetail()` 建立 `indDetailTable` 時：

```js
detailTable = MKLAB.DataTable('indDetailTable', {
  cols: ['sym', 'name', 'price', 'chg', 'pe', 'pb', 'roe'],   // 沒有市值
  ...
});
```

已加上 `cap` 欄並對應 `market_cap` 欄位（跟首頁「市值前 10 大」表格同一套格式，單位是億）：

```js
detailTable = MKLAB.DataTable('indDetailTable', {
  cols: ['sym', 'name', 'price', 'chg', 'pe', 'pb', 'roe', 'cap'],
  rows: real, pageSize: 10, pagerId: 'indDetailPager',
  defaultSort: 'chg',
  fieldMap: { cap: 'market_cap' },
});
```
