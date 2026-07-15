# mklab-stock handoff（工作交接狀態）

最後更新：2026-07-15
狀態：未完成上線，有一個 blocker 待修。

## 目標
把 mklab-stock 儀表板的「表格顯示」與「頂部工具列 + 設定抽屜」都收成共用模組（單一來源維護），5 頁一致，最後驗證上線。

## 已完成
1. `assets/mklab-core.js` 單一模組檔，含 4 個子模組：
   - `MKLAB.DataTable`：22 欄 COLUMNS 註冊表 + 表格類（排序/格式化/分頁/箭頭）
   - `MKLAB.Drawer`：設定抽屜（外觀/語言/說明/System）
   - `MKLAB.Watch`：共用自選清單（localStorage，首頁與 watchlist 共用同一份）
   - `MKLAB.Shell`：頂部工具列（搜尋鍵/深色按鈕/GitHub 跳轉/設定鍵/導覽列）
2. 5 頁工具列已遷移（你本輪要求）：
   - index.html / mklab-stock-screener.html / mklab-stock-research.html / mklab-stock-industry.html / mklab-stock-watchlist.html
   - 舊的 nav+utilbar 硬寫 HTML 刪除，改為 `<div id="utilbar"></div>` + `MKLAB.Shell.mount({active:'market'|'screener'|'research'|'industry'|'watchlist'})`
   - 各頁舊的 `toggleSearch/doSearch/toggleDark/setLang` 重複函式已刪除
   - 瀏覽器實測 index：工具列渲染正常（品牌+5導覽+搜尋+主題+GitHub+設定），設定抽屜內容（外觀/語言/說明/System）全頁一致 ✓
3. 抽屜 bug 已修：核心模組缺 `MKLAB.initDrawer` 別名 → 已加，抽屜現可正常注入與開關

## 未解 blocker（必須修，否則「點擊排序」承諾未達成）
**DataTable 點擊表頭不排序。** → ✅ **已修（2026-07-15，session A）**

### 修法（已採用方案 A：document 級事件委託，根治脫鉤）
- `mklab-core.js`：`_build` 內對 `this.table` 綁 click 的邏輯移除；改在 `DataTable.prototype._register` 裡對 `document` 綁一次委託：
  ```js
  document.addEventListener('click', function(e){
    const th = e.target.closest('thead th');
    if(!th) return;
    const tbl = th.closest('table');
    const inst = _byTable[tbl.id];   // 實例按 tableId 註冊於 _byTable
    if(inst) inst.toggleSort(th.getAttribute('data-k'));
  });
  ```
- 實例建構時新增 `this.tableId`，並在 `_register` 註冊進 `_byTable[tableId]`。永遠不依賴「建構時捕獲的 DOM 引用」，徹底消除脫鉤。
- 各頁（screener/industry/watchlist）共用同一 DataTable，修法一次性解決，無需各頁改。

### 瀏覽器實測（已驗證，非推測）
- 真實 `browser_click` 點擊「代號」th → console 出現 `[DT doc-click] indTable sym` + `[DT.toggleSort] sym ... dir=-1 rows=10`
- 表格順序由「綜合評分降冪」(00715L=5, 00640L=3, ...) 正確重排為「代號字串降冪」(00715L, 00640L, 00642U, 006207, 00633L, 00636, 00645, 00655L, 00657, 00661)
- cache-busting URL 已用，排除 browser cache 誤判。排序 bug 確認根治。

### 已定位事實（用瀏覽器實測確認，非推測）
- 手動呼叫 `indTable.toggleSort('sym')` → 排序完全正常（A→Z 重排成功）
- `indTable` 實例存在、`_clickBound=true`、綁在 `#indTable` 上
- 但點擊 th 時 click listener 完全不觸發（無 `[DT click]` log；對 th 手動 dispatch click 也不觸發）
- 對同一 `#indTable` 另加的測試 listener 卻收到 click（count=1）
  → 證明事件能到達 table，但 DataTable 綁的那個 listener 綁在「一個不同的 table 實例/DOM 引用」上

### 根因推論
DataTable 建構時 `this.table = document.getElementById(tableId)` 取得的元素，與後來實際渲染的 `#indTable` 不是同一個節點。index 初次同步 `renderInd()` 建立 indTable 並 `_build` 綁定 click；後來 `loadStocks().then` 二次 `renderInd()` → `setRows` → `render()` 路徑中，table 元素引用可能漂移（或初次建立時 DOM 狀態與二次不一致），導致綁定事件的 DOM 與可見渲染的 table 脫鉤。

### 建議修法（二選一，推薦 A）
- **A. document 級事件委託（最穩健）**：不要在 `_build` 裡對 `this.table` 綁 click，改在 `MKLAB.DataTable` 首次呼叫時對 `document` 綁一次：
  ```js
  document.addEventListener('click', function(e){
    const th = e.target.closest('thead th');
    if(!th) return;
    const tbl = th.closest('table');
    const inst = _instances[tbl.id];   // 需要把實例按 tableId 存進 _instances
    if(inst) inst.toggleSort(th.getAttribute('data-k'));
  });
  ```
  關鍵：實例要能從 `tableId` 找回（`_instances[tableId] = this`，建構時註冊）。這樣永遠不依賴「建構時捕獲的 DOM 引用」，徹底消除脫鉤類錯誤。
- **B. render() 末尾重綁**：每次 `render()` 用 `document.getElementById(this.tableId)` 重新取元素並確保 listener 綁定（去掉 `this._clickBound` 一次性防護，或改在 render 裡判斷）。

### 其他頁排序同理
screener / industry / watchlist 的 DataTable 也用同一套 `_build` + click 綁定，修 A 後一併解決，無需各頁改。

## 還沒做（待續）
1. 修上面排序 bug（用 execute_code 分析 + 改 core.js，完成後用最小瀏覽器驗證 index 一頁即可，勿逐頁狂點）
2. 逐頁瀏覽器驗證 screener / research / industry / watchlist 的表格渲染 + 工具列 + 抽屜（建議開新 session 專做，避免爆呼叫）
3. 確認首頁「我的自選」卡片改讀共用自選 + stocks.json 真實價格正常（watchlist 頁已用 MKLAB.Watch.decorate(priceMap)）
4. 定位首頁 js_error 來源（載入時 1-2 筆空 message exception，推測來自 KLineChart 圖表庫初始化，功能不受影響；若確認是圖表庫則加容錯或 defer，不阻擋上線）
5. commit + push 到 evanhsia-git/mklab-stock main
6. 確認 qa-gate CI 綠（已有 .github/workflows/qa-gate.yml，require 檢查）

## 本地環境
- repo: /root/Documents/mklab-stock （git，branch main，未提交修改）
- 本地預覽 server: `python3 -m http.server 8765 --bind 127.0.0.1`（背景 proc_5510a1ce2bbc，若不在用 `terminal(background=true)` 重起）
- 瀏覽器驗證加 cache-busting: `?nocache=數字`
- GitHub owner: evanhsia-git（非 ivanhsia）；gh token 缺 Administration/actions:write scope，建 repo/開 Pages/手動觸 workflow 需你手動做

## 檔案結構（已上線相關）
- index.html（首頁，含 TOP10 表 + 自選卡片）
- mklab-stock-screener.html / -research.html / -industry.html / -watchlist.html
- assets/mklab-core.js（核心模組，本次重點）
- mklab-stock-help.html（功能說明頁）
- data/（stocks.json / industry.json / history/）
- vendor/（klinecharts.min.js）
- .github/workflows/daily-update.yml + qa-gate.yml

## 設計決策（用戶已確認）
- 首頁「設定首頁顯示股票」專屬設定已放棄；所有頁抽屜內容完全一致（外觀/語言/說明/System）
- 表格：單一 DataTable 模組，各頁只選要顯示的欄位（cols 陣列），22 欄一次定義於 COLUMNS
- 自選：首頁與 watchlist 共用同一份 localStorage（MKLAB.Watch）
- 零外部依賴原則：GitHub Pages 直接開 index.html 可載（開發用本地 server 是因為 fetch 需 http 協議）

## 下一步建議（拆解，別一輪全做）
- session A：「修 DataTable 排序點擊（用 document 委託），execute_code 驗證邏輯，最小瀏覽器確認 index 一頁」
- session B：「逐頁瀏覽器驗證 4 頁 + 定位 js_error + commit/push + 確認 qa-gate 綠」
