# mklab-stock Handoff（2026-07-15 更新 — Web Components 開發輪）

> 新 session 接手時：先讀此檔 + 執行導航（SCHEMA/policy/index/log）+ 讀 `docs/mklab-stock-dev.md`（完整開發指引）。
> 上一輪（待修 A/B + 圖表庫修正 + push）已完成並合併 master，內容已清空，不再贅述。

## 當前 Git 狀態（重要）
- **當前分支**：`dev/web-components`（開發分支，未提交變更）
- **備份分支**：`backup/static-2026-07-15`（靜態頁備份，主要上線版安全保留）
- **master 最新 commit**：`30cc767`（含 DAV 分析文件）
- **未提交變更**（本輪開發，待 commit）：
  ```
   M data/fetch-log.json
   M data/fetch-log.txt
   M data/twii_kdata.js        ← 重產（含 window.TWII_KDATA 掛載）
   M docs/mklab-stock-dav.md   ← 重寫為 Web Components 版
   M scripts/fetch_data.py     ← 改 twii 產出格式
  ?? assets/mklab-wc.js        ← 新增：Web Components 元件庫
  ?? prototypes/wc-demo.html   ← 新增：元件測試頁
  ```

## 一、本輪決策（用戶指令）
1. **備份當前靜態網頁** → 建 `backup/static-2026-07-15`（靜態頁為主要上線版，不動）
2. **分支開發** → `dev/web-components`
3. **選 2 路線**：放棄 React 化（需 Node/npm/Vite，違反「不依賴外部軟體」），改採**原生 Web Components / ES Modules 元件化**，守零依賴 / fork 即維護
4. 開發完畢用 **superpowers 執行檢查與驗證**（verification-before-completion + qa_gate）
5. 最後**自動上線**（dev → main merge + push → GitHub Pages 自動部署）

## 二、已完成事項（本輪）

### ✅ 1. 分支策略建立
- `backup/static-2026-07-15`：從 master@30cc767 分出（靜態頁安全備份）
- `dev/web-components`：開發分支（當前所在）

### ✅ 2. DAV 重寫為 Web Components 版
- `docs/mklab-stock-dav.md` + `Obsidian Vault/finance/mklab-stock/mklab-stock-dav.md` 已重寫
- 含：現狀事實、決策轉向、差異比對、12 項待開發（推薦度/難易度）、最高原則符合性、風險緩解

### ✅ 3. WC 基礎 + 第一元件 `<mklab-kline>`
- 新增 `assets/mklab-wc.js`（plain script，classic 註冊，**零依賴**，不破壞現有 `MKLAB.*`）
- 實作 `<mklab-kline>` Custom Element，封裝 LightweightCharts v4.1.3：
  - `connectedCallback`：檢查 `window.LightweightCharts` 是否存在（不存在靜默退出）
  - `data-symbol="TWII"` 屬性驅動：讀 `window[sym+'_KDATA']` 全域
  - `setData(arr)` 方法：程式化餵資料
  - `loadGlobal(name)` / `addLine(opts)` 方法
  - `disconnectedCallback`：清理 chart + resize listener（防記憶體漏）
  - resize 自適應（監聽 window resize）

### ✅ 4. demo 頁 + 瀏覽器實測驗證
- 新增 `prototypes/wc-demo.html`（測試頁，不動正式頁）
- **實測驗證通過**（browser 實際載入 + console + vision）：
  - 測試 1（屬性驅動 `data-symbol="TWII"`）→ 渲染 260 天台灣加權指數 K 線 ✅（console 確認 `windowTwii:true, len:260, canvases:7`）
  - 測試 2（程式化 `setData(15筆)`）→ 渲染蠟燭圖 ✅
- **解決的 bug（本輪實測發現）**：
  1. **路徑錯誤**：demo 在 `prototypes/` 子目錄，script src 用根相對路徑 → 404。改絕對路徑 `/vendor/...` `/data/...` `/assets/...`
  2. **const 不掛 window**：`twii_kdata.js` 用 `const TWII_KDATA`，瀏覽器頂層 const **不掛 window 物件** → `window.TWII_KDATA` 為 undefined → 元件讀不到。修法：`fetch_data.py` 產出加 `if(typeof window!=='undefined')window.TWII_KDATA=TWII_KDATA;`，並重產本機 `data/twii_kdata.js`
  3. **瀏覽器快取**：script 子資源不被 `?nocache` 影響 → demo 加 `?v=` cache-bust
  4. **時序競爭**：第二個測試 `setData` inline script 與元素升級時序不穩 → 用 `customElements.whenDefined('mklab-kline').then(...)` 包裝

## 三、未完成事項（待續）

| # | 項目 | 狀態 | 備註 |
|---|------|------|------|
| 7 | `data-client.js` 統一資料層 | 待做 | 取代各頁散落 fetch；IIFE 或 classic |
| 8 | `<mklab-datatable>` 表格元件 | 待做 | 從 `MKLAB.DataTable` 轉 Custom Element |
| 9 | `<mklab-drawer>` 抽屜/主題/語言 | 待做 | 從 `MKLAB.Drawer/Shell` 轉 |
| 10 | SPA 路由（History API） | 待做 | 無 React Router |
| 11 | 逐頁接入 WC 元件 | 待做 | 並行過渡，不破壞靜態主要 |
| 12 | superpowers 驗證 | 待做 | verification-before-completion + qa_gate |
| 13 | 合併 dev → main + push | 待做 | GitHub Pages 自動上線 |

## 四、中斷接手部分（新 session 必讀）

### 🔴 當前中斷點
- **分支 `dev/web-components` 有大量未提交變更**（見上方 Git 狀態）
- 本輪開發**尚未 commit**（用戶指示「開發完畢用 superpowers 驗證後」才上線，故中途不 commit）
- 下一個應做：**#7 `data-client.js` 統一資料層**

### ⚠️ 接手注意事項（踩坑記錄）
1. **元件註冊用 classic script，非 ES module**：`mklab-wc.js` 是 IIFE + `customElements.define`，刻意不用 `type="module"`（因 `mklab-core.js` 支援 file:// 直接開，module 有 CORS 限制）。若改用 ES module 需同步改預覽方式（http.server 而非 file://）
2. **`window.TWII_KDATA` 已修**：`fetch_data.py` 現產出 `const TWII_KDATA=[...]; if(typeof window!=='undefined')window.TWII_KDATA=TWII_KDATA;`。未來其他資料 JS 若也要給 `<mklab-*>` 讀，需同樣掛 window
3. **Custom Element 時序**：呼叫元件方法（setData 等）必須等 `customElements.whenDefined('mklab-kline')` 後，否則 `_series` 未建
4. **demo 頁在 prototypes/**：script src 用絕對路徑 `/vendor/...`（`/data/...`/`/assets/...`），勿改回相對路徑
5. **LightweightCharts v4 限制**（沿用上輪）：無 `series.getData()`、無 overlay 繪圖工具（畫線/費波那契不生效）
6. **local server**：`python3 -m http.server 8765`（背景 proc 可能還在跑）。新 session 先確認 `curl -s -o /dev/null -w "%{http_code}" http://localhost:8765/index.html`

### 📋 接手第一步建議
```
cd /root/Documents/mklab-stock
git branch --show-current          # 確認在 dev/web-components
git status --short                 # 確認未提交變更還在
# 接續 #7：寫 assets/data-client.js（統一 fetch data/*.json）
```

## 五、關鍵事實（防踩坑，沿用+更新）
1. **圖表庫**：`vendor/lightweight-charts.min.js` 實為 **LightweightCharts v4.1.3**（全局變數 `LightweightCharts`）。`<mklab-kline>` 已封裝它
2. **FinMind 不可用**：直接用 yfinance（TWII K 線來源）
3. **本機 DB 權威源**：`/root/Documents/database/tw_stock_all.db`
4. **零依賴原則**：選 2 路線核心，新增檔案不得引入 npm/Node/Vite。元件用 plain script + Custom Elements
5. **靜態頁為主要**：`index.html` + 4 個 `mklab-stock-*.html` 現役上線版，開發期不動；WC 元件先經 `prototypes/wc-demo.html` 驗證再考慮接入

## 六、用戶偏好/決策（本輪）
- 決策：放棄 React（違零依賴），選 Web Components 元件化
- 靜態網頁繼續使用且為主要上線版；分支開發新專案
- 開發完畢用 superpowers 檢查驗證 → 最後自動上線
- Wiki：問題+解法寫進 Wiki（先查類似頁併入，不開新頁）
