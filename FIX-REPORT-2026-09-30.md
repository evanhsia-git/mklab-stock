# mklab-stock 修復與新功能報告（2026-09-30）

## 你的四大指數問題，查證結果

| 指數 | 公司數 | 實際股票代號數（含雙類股） | 來源 |
|---|---|---|---|
| 道瓊工業指數（DJI） | 30 | 30 | 固定 30 檔，是道瓊指數的定義特性 |
| 那斯達克 100（Nasdaq-100） | 100 | ~101-102 | GOOGL/GOOG 等少數公司有雙重股權，實際代號數略多於 100 |
| S&P 500 | 500 | 503 | Wikipedia「List of S&P 500 companies」目前實測確認 503 檔（GOOGL/GOOG、FOX/FOXA、NWS/NWSA 三組雙類股） |
| 費城半導體指數（SOX） | 30 | 30 | 已用 Nasdaq 官方 SOX 持股權重文件（2026-05-01）核對，確認剛好 30 檔 |

**四個指數去重後合計約 520~535 檔**（不是四個數字直接相加）。你估計的「約 540 檔」已經很接近，差異來自重疊程度：道瓊 30 檔幾乎全部同時也是 S&P 500 成分股（增量趨近 0）；Nasdaq-100 跟 S&P 500 重疊度很高，增量約 15~20 檔；SOX 的 30 檔裡，NVDA/AMD/AVGO/INTC/TXN/QCOM/MU 等多數已經在 S&P 500/Nasdaq-100 裡，但 TSM（台積電 ADR）、ASML、STM 這幾檔外國公司通常不在 S&P 500 名單內（S&P 500 規則排除外國私人發行人），增量約 5~8 檔。

**精確數字需要實際跑一次我這次寫好的腳本才能確定**（見下方），我沒辦法在這個環境自己把四個指數的最新完整名單一一核對去重（那需要抓四個頁面的完整表格內容，光一個 S&P 500 表格就有 500 多列，用人工比對不切實際），所以這次改成讓程式碼自己去抓、自己去重。

## 已完成並實測驗證的功能

### 1. 美股資料庫擴充：四大指數成分股清單（新增 `skills/data/fetch_us_universe.py`）

這支新腳本會自動抓 Wikipedia 的「List of S&P 500 companies」「Nasdaq-100」「Dow Jones Industrial Average」「PHLX Semiconductor Sector」四個頁面的成分股表格，合併去重，輸出 `data/us/index-universe.json`（內容是每檔股票屬於哪個/哪些指數）。

**用 Wikipedia 而非自己手動列清單的原因**：S&P/Nasdaq/Dow Jones 這些指數編制機構都沒有免費、允許程式化存取的官方成分股 API（要抓真正官方資料得付費訂閱）。Wikipedia 的這幾個頁面是業界公認拿來程式化取得這些清單的慣用做法（連 GitHub 官方的 `datasets/s-and-p-500-companies` 專案都是這樣做），採用 CC BY-SA 授權可重製利用，跟 TWSE ETF 投資篩選器那種明文禁止自動化擷取的網站不同，**沒有合規疑慮**。

`fetch_us_data.py`（抓美股市值前 30 大的腳本）已經改成優先讀取這份清單當候選池（原本只有手動維護的 60 檔，現在能涵蓋四大指數全部成分股），沒有這份檔案時會自動退回原本的候選池，不會壞掉。

**⚠️ 限制**：這個沙箱連不到 Wikipedia（網路白名單限制），我只能用模擬資料驗證解析邏輯本身是正確的（欄位比對、列數篩選、`BRK.B→BRK-B` 這種代號正規化都測過），**沒辦法在這裡實際跑出真正的四大指數完整清單跟精確的去重數字**。第一次請在有網路權限的環境（GitHub Actions 或你自己電腦）執行 `python3 skills/data/fetch_us_universe.py`，跑完就能看到 log 印出的「各指數檔數」跟「四個指數去重後合計」的精確數字。

### 2. CSV 匯出功能（新增 `MKLAB.exportCSV()` 共用函式）

在 `assets/js/mklab-core.js` 新增全站共用的 CSV 匯出函式，Screener 頁面已經接上做示範（「⬇ 匯出目前篩選結果 CSV」按鈕）。匯出的 CSV 開頭會有一段 `#` 開頭的備註，內容包含：

```
# mklab-stock 資料匯出
# 匯出時間：2026/10/20 上午10:26:32
# 本次匯出筆數：232
# 目前資料庫總筆數：1382
# 其中一般個股：1141 檔
# 其中 ETF：241 檔
# 資料來源：TWSE OpenAPI（上市）+ TPEx OpenAPI（上櫃）...
# 來源網址：https://openapi.twse.com.tw/ ， https://www.tpex.org.tw/openapi/
# 產生方式：本頁 Screener 依目前設定的篩選條件...
```

實測下載確認：UTF-8 BOM 編碼（Excel 開啟中文不會亂碼）、數字欄位正確處理千分位逗號、備註資訊完整正確。因為是共用函式，之後要幫其他頁面（US 頁、Compare 頁等）加匯出按鈕，只要呼叫 `MKLAB.exportCSV(資料陣列, 欄位清單, 說明物件)` 就好，工程量很小，我這次先在 Screener 做示範，你可以之後叫我比照加到其他頁面。

### 3. Industry 頁新增領漲／領跌（movers）

原本每張卡片只有「領漲 X%」且因為 `industry.json` 的 `top` 欄位從沒被算過（一直是 `null`），其實是失效的。這次改成即時用全市場個股真實漲跌資料算出每個產業的領漲／領跌各一檔，實測如：

```
水泥工業 -0.50%
7 檔
▲1108 +0.45%  ▼1101 -2.41%
```

### 以上 1~3 項實測結果
`qa_gate.py`：0 Critical，ALLOW DEPLOY；全站 13 頁 Playwright 回歸測試：全部無 Console 錯誤。

---

## ETF 成分股第三方資料來源評估

查過之後，**MoneyDJ「ETF持股狀況」頁面**（`https://www.moneydj.com/etf/x/basic/basic0007.xdjhtm?etfid={代號}.tw`）確實有你要的兩種資料：「持股明細」（個股名稱、投資比例%）跟「持股分佈（依產業）」（產業別、比例%），這正是你這次舉的 00981A 範例資料的真實來源，而且看起來是伺服器端直接渲染（不像 TWSE 篩選器那樣要等 JS 才有資料）。

**但我找不到 MoneyDJ 明確公開的服務條款文字**（不像上次 TWSE ETFortune 我有找到白紙黑字「禁止自動化擷取」），所以我沒辦法像上次一樣做出明確的「有/沒有合規疑慮」判斷。CMoney、Pocket.tw 這幾個平台也查不到明確條款。

**我的建議，比照之前 ETF meta CSV 的做法**：這些平台沒有像 TWSE 那樣提供「CSV 下載」按鈕，但如果你願意，一樣可以自己瀏覽頁面、把資料複製/整理成 CSV 或貼給我（例如某幾檔你常看的 ETF），我可以照 `parse_etf_meta.py` 的模式幫你寫一支解析腳本接上 Compare 頁。這樣完全是「你自己手動取得資料」，不涉及自動化爬蟲的合規疑慮。如果你想要「自動排程天天更新」，則需要先確認這些平台的服務條款是否允許，我建議先別做自動化版本。

---

## 還沒動手做的 3 項（給你技術方案，供你評估優先順序）

### A. 依產業 × 市值的色塊矩陣視覺化
技術上可行、工程量中等：用現有的 `data/industry.json`（33 產業）+ `data/stocks.json`（市值），把股票依「產業」分列、「市值級距」（如 <50億/50-200億/200-1000億/1000億以上）分欄，色塊深淺對應該格平均漲跌幅。這個我還沒做，下一輪可以直接動手。

### B. 國家切換鍵測試頁（TW｜US，先做首頁一頁）
你已經把範圍收得很合理（只做一頁測試）。技術方案：首頁加一個 TW/US 切換鈕，US 模式下複用現有的 `MKLAB.DataTable` 元件，資料來源換成 `data/us/us-stocks.json`／`data/us/us-etfs.json`（已經存在，就是 `mklab-stock-us.html` 在用的那兩份），顯示美股市值前 10/ETF 規模前 10。JP/KR/CN 三個選項先寫進切換鈕但 disabled（灰掉），註明「資料尚未建置」。這個工程量不大，下一輪可以直接做。

### C. Compare 頁查詢四大指數前 10 大成分股
這個需要的不只是「誰是誰的成分股」（這次 `fetch_us_universe.py` 已經解決），還需要「每檔占該指數的權重 %」才能排出「前 10 大」。**這份權重資料，S&P/Nasdaq/Dow Jones 官方一樣不公開免費提供**，需要另外找資料源（例如追蹤這些指數的 ETF——SPY 追蹤 S&P500、QQQ 追蹤 Nasdaq100、DIA 追蹤道瓊、SOXX 追蹤 SOX——這些 ETF 的官網通常會公開每日持股權重，可能是比較可行的路徑，但要另外花時間查證每個 ETF 官網的資料格式與可行性，這次沒時間做）。等 A、B 兩項確定要做之後，我再排一輪專門查這個。

---

## 其他提醒

- `mklab-stock-dividend.html` 這個檔案我看你 repo 裡還留著（上次已經從 NAV 拿掉連結、內容也不會被使用，但檔案本身還沒刪），記得找時間 `rm mklab-stock-dividend.html`。
- 這次修改/新增的檔案：`skills/data/fetch_us_universe.py`（新）、`skills/data/fetch_us_data.py`、`skills/data/skill.md`、`skills/qa-gate/qa_gate.py`、`assets/js/mklab-core.js`、`mklab-stock-screener.html`、`mklab-stock-industry.html`。
