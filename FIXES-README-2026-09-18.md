# mklab-stock 修復說明（2026-09-18）

這份 zip 包含**這一輪改動過的檔案**，直接覆蓋到 repo 對應路徑後 commit push：

```
index.html + 全部 12 個 mklab-stock-*.html 子頁      ← 頭部兩列順序調整
assets/css/layout.css                                ← utilbar/nav sticky 定位修正
assets/css/mobile.css                                 ← 移除失效的 utilbar top 手機覆寫
mklab-stock-compare.html                              ← 額外含股票代號不分大小寫
README.md                                             ← 全部重寫，對齊目前 11 個功能頁
```

---

## 1. 深色主題按鈕按下沒反應 — 根因找到了，跟版面擁擠有關

實測結果：`toggleDark()` 這段程式邏輯本身完全正常（用無介面瀏覽器直接點擊按鈕，`data-theme` 屬性和畫面顏色都正確切換）。問題不在按鈕的程式，而在**版面**：

原本頭部是「導覽列（11 個分頁）在第一列、品牌＋工具鈕在第二列」，且 `.utilbar`（品牌＋工具鈕那一列）用了寫死的 `top: 48px` 去做 sticky 定位，這個 48px 是假設「上面那一列導覽永遠只有一行、高度剛好 48px」。但實測發現：螢幕寬度在 **約 640px～900px 之間**（例如筆電開一半視窗、或平板橫向），11 個分頁文字會換行變成 2～3 行，導覽列實際高度變成 72～96px，跟寫死的 48px 對不上，造成品牌／工具鈕那一列的定位跟實際導覽列的高度不同步、視覺上互相疊到一起——這種情況下滑鼠點在「看起來是深色按鈕的位置」，實際點到的可能是導覽列的連結，按鈕當然「沒反應」。

## 2. 版面順序調整 — 已完成，同時解決了問題 1

已將全部 13 個頁面的 `<header>` 內容順序對調：

```html
<!-- 修改前：導覽列在上，品牌+工具鈕在下 -->
<nav id="mainNav" ...></nav>
<div id="utilbar" ...>...</div>

<!-- 修改後：品牌+工具鈕在上，導覽列在下 -->
<div id="utilbar" ...>...</div>
<nav id="mainNav" ...></nav>
```

同時把 CSS 的定位方式也改掉，不再用寫死的像素數字去猜另一列的高度：現在只有最外層的 `<header class="sticky-header">` 整體 sticky 在畫面頂端，`utilbar` 跟 `nav` 兩列都是它裡面正常排列的內容，不管導覽列換成幾行都不會互相疊到，也不需要再猜測像素高度。

效果：品牌「mklab-stock」＋搜尋／深色／GitHub／設定 固定在最上面一列，各分頁文字（Market/Screener/…/Digest）在第二列，換行也不會跟第一列打架，深色按鈕在任何寬度下都點得到。

## 3. GitHub README 更新

舊版 README 還停留在「7 個頁面＋`templates/`樣板系統＋GrapesJS 視覺編輯器」的舊架構描述，跟目前實際的 repo（13 個頁面、無 templates/ 目錄、無 build/ 目錄）完全不符。已整份重寫，內容依照目前實際檔案結構、目前 11 個功能頁（Market/Screener/Research/Industry/Watchlist/Dividend/Compare/Breadth/Backtest/Portfolio/Digest）+ Help/Log 說明頁、`data/stocks.json` 目前的 1,835 檔規模、`.github/workflows/daily-update.yml` 目前實際的 4 個排程時段（含新增的每日摘要/RSS 排程）重新撰寫。

## 4. Compare 頁股票代號不分大小寫

`addCompare()` 原本直接用 `input.value.trim()` 去跟資料裡的代號做**大小寫敏感**的字串比對，資料裡的代號字尾字母（例如 ETF/特別股代號 `00981A`）一律是大寫，使用者打小寫 `00981a` 會找不到而跳出「找不到股票代號」的錯誤。

已改成輸入後立即 `.toUpperCase()`：

```js
const sym = input.value.trim().toUpperCase();
...
if (!ALL.find(r => String(r.sym).toUpperCase() === sym)) { ... }
```

現在打 `00981a`、`00981A` 效果相同，都能正確加入比較清單。
