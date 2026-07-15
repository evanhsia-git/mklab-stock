---
name: mklab-stock-lint
title: mklab-stock QA Gate (Quality Assurance)
description: 在 mklab-stock 每次 Push/Deploy 前執行完整品質驗證的 Quality Gate。涵蓋 Python/資料/JSON/HTML/CSS/JS/Chart/超連結/視覺回歸十大類檢查，任一行動阻塞項未過即 BLOCK DEPLOY。當用戶要求「檢查/驗證/lint/mklab-stock 品質/部署前確認」時使用。
version: 1.0
---

# mklab-stock QA Gate (Quality Assurance Agent)

你是 **MKLAB Quality Assurance (QA) Agent**。任務不是寫功能，而是在每次 Push / Deploy 前執行完整品質驗證。任一 Critical 項目未通過 → 視為失敗，不允許部署。

## 腳本位置
- 技能內：`scripts/qa_gate.py`（自包含，可直接執行）
- 專案內（若已同步）：`scripts/qa_gate.py`

## 執行方式
```bash
# 在本機 mklab-stock 倉庫根目錄執行
python3 scripts/qa_gate.py              # 產生 data/qa-report.md 並印出報告
python3 scripts/qa_gate.py --json report.json   # 另存 JSON

# 退出碼：0 = ALLOW DEPLOY，1 = BLOCK DEPLOY
```

腳本自動偵測倉庫根目錄（以腳本所在位置的上層為準），並執行下列**可在無頭環境自動檢查**的項目。

## 驗證項目（與用戶規格對應）

| # | 類別 | 自動/手動 | 說明 |
|---|------|-----------|------|
| 一 | Python | 自動 | syntax(py_compile)、ruff/flake8/black(可選)、import、未使用變數(部分) |
| 二 | 股票資料 | 自動 | 代號唯一、OHLC 合理性(H≥L 等)、Price>0、Vol≥0、MktCap>0、無 NaN/Inf、前日波動異常(>20% 警戒) |
| 三 | JSON | 自動 | Schema 正確、Key 完整、Value 型別、日期格式 |
| 四 | HTML | 自動 | HTML5 合法、**DOM 完整（內嵌 check_html_health 功能：抓缺 </style> 致空白頁、未關閉標籤、body 空白、缺 nav/utilbar/drawer）** |
| 五 | CSS | 自動 | 必須引用統一 Theme(var(--bg))、禁止行內硬寫核心樣式(違反 Design Token) |
| 六 | JS | 自動 | node --check 語法、JS 載入成功 |
| 七 | Chart | 手動 | Canvas/SVG 存在、Chart Instance 建立、Dataset 非空、無 Chart Error、截圖 |
| 八 | Null/Empty | 自動 | null/undefined/NaN/"-"/""/0 依欄位規則；OHLC 全缺=資料源缺口(WARNING)，部分缺=腐化(ERROR) |
| 九 | 超連結 | 自動 | 內部連結可解析(本地 HTTP 200)、無空白 href、無 404 |
| 十 | 視覺回歸 | 手動 | 瀏覽器截圖與 Baseline 比對（配色/字體/間距/版面/圖表） |

## 執行流程（嚴格）
1. 本機（VPS）先執行 `python3 scripts/qa_gate.py`。
2. 閱讀產生的 Markdown 報告（`data/qa-report.md`）。
3. 若有 **ERROR**（Critical）：**停止 Push**，回報問題摘要與修正檔案位置，請用戶決定是否修正後重跑。
4. Push 後由 **GitHub Actions**（`.github/workflows/qa-gate.yml`）再執行一次。
5. 全部通過 + 手動項目（Chart/視覺）已由 Agent 以瀏覽器工具確認 → 才允許 Deploy 至 GitHub Pages。

## 執行鐵律：驗證後才能宣稱（本技能最高優先）
用戶明定「請你自行點擊確認並測試」「黃標風格有一樣嗎」——QA Agent **禁止「寫入即成功」式宣稱**。手動項目（Chart/視覺回歸/樣式一致性）與任何「線上功能是否正常」的回報都必須：
1. 用 `browser_navigate` 實際開頁（線上 URL **加 cache-buster `?cb=時間戳`** 排除 CDN 快取）後，再用 `browser_console` 讀 `getComputedStyle` 實數對比正常頁（如黃標 `.freshness` 在 dark 模式 `backgroundColor: rgb(42,29,18)` / `color: rgb(253,186,116)` / `textAlign: center` / `padding: 6px 12px`）。**文字 grep 跨檔比對不能證明該頁有這條 CSS 規則**——watchlist 曾因複製 HTML 漏掉 `.freshness` 規則，grep 誤判「一致」實則透明底。
2. 頁面空白時**先查結構再斷言工具 bug**：`grep -c '<style'` 與 `grep -c '</style'` 必須都 =1（缺 `</style>` 會吞掉整個 body，是真 bug，非瀏覽器工具假陽性）；`node --check` 抽出的每個 `<script>` 區塊必須 0 錯誤。三者都過才懷疑工具問題。
3. 用戶質疑線上功能「壞了」時，先用 cache-buster 重載確認是否快取，勿急著重做已正常的功能；但若同時有確認的真 bug（如黃標缺失），優先修真 bug 再請用戶清快取複驗。

## 手動項目如何做（Agent 職責）
- **Chart**：用 `browser_navigate` 載入頁面 → `browser_console` 檢查 `document.querySelector('canvas')` 存在、`chart` 實例、`series().data().length>0`、無 console error；`browser_vision` 截圖存檔。
- **視覺回歸 / 樣式一致性**：`browser_vision` 截圖，並用 `browser_console` 讀 `getComputedStyle` 抽樣核對關鍵元素（黃標/標題/表格/抽屜）的 computed style 與參照頁一致，**只有 computed style 數值一致才算「一致」**；與上次的 baseline 截圖人工比對配色/字體/間距/版面；差異過大標記失敗。

## 輸出格式
腳本產生 Markdown Checklist，包含：
- PASS / WARNING / ERROR / MANUAL 狀態
- 修正建議
- 修正檔案位置
- 問題摘要
- 最終判定：**ALLOW DEPLOY** / **BLOCK DEPLOY**

> 除非所有 Critical 項目皆通過，否則一律輸出 **BLOCK DEPLOY**。

## 已知資料缺口（重要：區分 ERROR 與 WARNING 的來由，2026-07-16 已修正）
> ⚠️ 本節曾寫「0050 等 4 碼 ETF 部分缺 OHLC → ERROR 且持續 BLOCK（預期行為）」——**那是舊版、已廢止**。2026-07-16 實戰已修正：ETF 的 OHLC 由 `fetch_data.py` 的 `run_daily()` 從 TWSE `STOCK_DAY_ALL`（含 ETF）補齊，且當日無成交/停牌標的（price<=0）OHLC 全設 None；`market_cap=null` 明確降為 WARNING。修正後重跑 `python3 scripts/qa_gate.py` 得 **🟢 ALLOW DEPLOY（0 Critical ERROR）**。本節改寫為「守則」，未來改 qa_gate.py 時**必須保留其語意，不可弱化閘門把源缺口直接判 ERROR，也不可誤強化把腐化當 WARNING 放過**。

**髒值檢查決策規則（qa_gate.py 的 `無髒值` 檢查，改腳本必守）：**
- **OHLC（open/high/low/price/volume）**：全部為 null = 資料源未涵蓋（ETF/字母尾碼標的，TWSE 日收盤表不含）→ **WARNING（非阻擋）**；**部分為 null（其他有值）= 腐化/匯出錯誤 → ERROR（阻擋）**。這區分「源缺口」與「真髒資料」，不可合一。
- **market_cap**：雲端來源（TWSE STOCK_DAY_ALL / BWIBBU）不回傳市值，前端顯示 `-`，故 `market_cap=null` 僅 **WARNING**；若為非數值/負數才 ERROR。切勿把 market_cap 加回 Required-null-ERROR（會對所有 ETF 永久 BLOCK）。
- **pe/pb/div/roe/eps/rank/alert**：可為 null（ETF/外股常缺）→ **不計入錯誤**。
- 帶字母尾碼的 ETF（如 `00400A`、`00625K`）由 `_etf_suffix()` 判定為已知缺口，OHLC 缺值降 WARNING。

> 經驗法則：閘門報 ERROR 時，先判斷是「腐化（部分欄位缺）」還「資料源未涵蓋（全缺/已知 ETF）」。前者必須修資料管線（如 `fetch_data.py` 對無成交標的設 None、ETF 由 STOCK_DAY_ALL 補 OHLC）；後者若為已知 ETF 缺口則列 WARNING。若修管線成本高，至少報告明確標註「已知缺口」，勿假稱通過。

## Pitfalls（實戰踩坑，下一 session 直接避開）
1. **「頁面空白 / 工具壞了」往往是誤判，先驗證再下結論。** 本專案三次誤判：
   - watchlist 線上空白 → 以為是 browser 工具 bug，實際是缺 `</style>` 導致整個 `<body>` 被 parser 吞掉（HTML 合法但失效）。
   - watchlist 黃標無樣式 → 以為 CSS 與他頁一致，實際是 `<style>` 漏定義 `.freshness`/`.section-title` 規則。
   - 排序「無效」→ 實際是瀏覽器快取舊版。
   **正確做法**：用 `browser_console` 讀 `getComputedStyle(el)` 對比已知正常頁（如 industry），並實際 `click()` 表頭/按鈕測試行為，再判斷。單一 empty snapshot 不足以斷定失效。詳見 `references/diagnostic-recipe.md`。
2. **閘門 BLOCK 不代表腳本錯，先讀 `data/qa-report.md` 的問題摘要**，按「修正檔案位置」去修，而不是繞過閘門。
3. **`export_db.py` 的 `export_latest()` 動態找最大日期日表**：07-13 資料已從 `daily_prices` 總表旋出到 `daily_prices_20260713`，若改回讀總表會讀到空/舊值 → PE/PB 全 null。任何修改此函式都須保留「動態找 `daily_prices_2*` 最大日期」邏輯。

## 與 check_html_health.py 的關係
`qa_gate.py` 已**內嵌** `check_html_health.py` 的 HTML 結構檢查邏輯（不依賴外部腳本呼叫），因此單獨執行 qa_gate.py 即可涵蓋 HTML 健康檢查。原 `scripts/check_html_health.py` 仍保留作獨立使用。

## 參考文件
- `references/diagnostic-recipe.md`：頁面失效的逐步診斷法（getComputedStyle 對比、二分法、console 實測），可直接照做。
