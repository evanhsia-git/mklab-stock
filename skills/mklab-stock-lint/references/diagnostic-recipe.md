# mklab-stock 頁面失效診斷食譜

當某頁在 browser 工具顯示 `empty page` / 樣式異常 / 功能「沒反應」時，按此順序排查。**不要**第一時間斷定「browser 工具 bug」或「快取問題」——本專案三次誤判都來自過早下結論。

## 步驟 1：區分「工具 bug」與「真實失效」
1. 用 `browser_navigate` 載入**線上 URL**（非 localhost，排除本地差異）。
2. `browser_console` 讀關鍵資訊：
   ```js
   ({
     doc_len: document.documentElement.outerHTML.length,
     body_children: document.body ? document.body.children.length : 'no body',
     scripts: document.scripts.length,
     style_rules: document.styleSheets.length
   })
   ```
   - `body_children: 0` 但 `doc_len` 很大 → HTML 載入但 body 沒解析 → **真實結構問題**（如缺 `</style>` 吞掉 body）。
   - `scripts: 0` → `<script>` 區塊沒被解析。

## 步驟 2：樣式異常用 getComputedStyle 對比
不要只看 CSS 文字是否「看起來一樣」。實際讀 computed style 並與已知正常頁對比：
```js
const f = document.querySelector('.freshness');
const cs = getComputedStyle(f);
return { bg: cs.backgroundColor, color: cs.color, textAlign: cs.textAlign, padding: cs.padding };
```
- 正常（industry）：`bg: rgb(42,29,18)`、`color: rgb(253,186,116)`、`textAlign: center`。
- 異常（watchlist 曾發生）：`bg: transparent`、`color: 淺灰`、`textAlign: start` → 該 CSS 規則根本不存在於該檔。
→ 根因通常是 `<style>` 漏定義該 class 規則（從別頁複製時遺漏）。

## 步驟 3：二分法定位結構破壞
若 body 空白，懷疑某區塊破壞 parser：
1. 移除 `<script>` 區塊另存測試檔 → 若仍空白，說明是 HTML body 結構問題（非 JS）。
2. 建立最小測試頁（只留 nav + 一行字 + 最小 script）→ 若能渲染，說明 browser 工具正常，問題在原檔某處。
3. `grep -c "</style>" 檔名`：回傳 0 即確認缺關標籤（本專案 watchlist 實例）。

## 步驟 4：功能「無效」先用 console 實測
勿憑初次 snapshot 判斷。直接用 console 呼叫函式並讀狀態：
```js
sortWl('price');
[...document.querySelectorAll('#wlBody tr')].map(r=>r.children[2].textContent);
```
- 若排序確實重排 → 功能正常，使用者看到的是**瀏覽器快取舊版**（強制重新整理即可）。
- 若報 `sortWl is not defined` → script 有語法錯誤未執行（`node --check` 驗證）。

## 步驟 5：本地復原 vs 線上
`curl -s URL` 抓線上原始 HTML，與本地 `diff` 確認線上=本地（排除推送失敗）。
`curl -s -o /dev/null -w "%{http_code}" URL` 確認 HTTP 200 且 `</body>` 存在。

## 本專案實戰案例（已發生）
| 現象 | 誤判 | 真實根因 | 解法 |
|------|------|----------|------|
| watchlist 線上空白 | browser 工具 bug | 缺 `</style>` → body 被吞 | 補 `</style></head><body>` |
| watchlist 黃標無黃底 | CSS 與他頁不一致 | `<style>` 漏 `.freshness`/`.section-title` 規則 | 補 CSS 規則（與他頁逐字一致） |
| watchlist 排序無效 | 功能壞了 | 瀏覽器快取舊版 | 強制重新整理；功能本就正常 |
| screener/home 數據 null | 前端錯 | `export_db.py` 從空 `daily_prices` 總表讀 → PE/PB null | 改讀 `daily_prices_YYYYMMDD` 最大日期表 |
