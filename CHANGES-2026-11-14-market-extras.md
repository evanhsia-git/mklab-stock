# 官方加值資料導入（★★★ 六項）— 2026-11-14

## 一、做了什麼

依 2026-11-14 的 TWSE OpenAPI 全端點盤點結果（143 端點實測），導入效益最高的 **★★★ 六項**官方資料：

| 端點 | 資料 | 實測筆數 | 落點 |
|---|---|---|---|
| `opendata/t187ap05_L` | 上市公司每月營業收入彙總表 | 1,075 | `data/market-extras.json` → 篩選頁欄位 |
| `exchangeReport/MI_MARGN` | 集中市場融資融券餘額 | 1,302 | `data/market-extras.json` → 篩選頁欄位 |
| `opendata/t187ap17_L` | 上市公司營益分析（官方毛利率／營益率） | 1,000 | `data/market-extras.json` |
| `opendata/t187ap14_L` | 上市公司各產業EPS統計（官方累計 EPS） | 1,014 | `data/market-extras.json`（交叉驗證用） |
| `exchangeReport/TWTAWU` | 集中市場暫停交易證券 | 1 | `data/stocks.json` 的 `trading_status` |
| `holidaySchedule/holidaySchedule` | 開（休）市日期 | 29 | `data/market-extras.json` |

新增檔案：

- `skills/data/fetch_market_extras.py` — 一次抓六個端點，輸出單一檔 `data/market-extras.json`
- `skills/data/integrate_market_extras.py` — 把暫停交易狀態套用到 `stocks.json`（冪等）
- `tests/test_market_extras_2026_11_14.py` — 24 項單元測試

## 二、關鍵決策（含被否決的方案）

### 決策 1：加值資料**不塞進** `stocks.json`

`tests/test_known_errors.py` 有一條「`stocks.json` 單檔預算 1,300 KB」（2026-11-10 為瘦身而立的規則）。
實作過程中曾把 17 個加值欄位直接寫進快照，實測結果：

| | 檔案大小 |
|---|---|
| 直接內嵌 17 欄（**已否決**） | 1,213 KB → **1,751 KB**（+538 KB，超預算 35%） |
| 改放獨立檔（**採用**） | `stocks.json` 1,264 KB ＋ `market-extras.json` 779 KB（按需載入） |

`stocks.json` 每一頁都要下載，因此只保留「會改變交易狀態語意」的停牌欄位（僅影響 0–3 檔）；
月營收／融資融券／三率改由篩選頁按需載入獨立檔，並在該頁併入每列。

### 決策 2：官方累計 EPS 與官方三率**不覆蓋**本站值

- `t187ap14_L` 是**累計** EPS（季別 3 ＝ 前三季累計）；本站 `eps` 是**累計年化**。
  兩者基準不同，直接覆蓋會讓同一列的 `eps` 與 `pe` 互相矛盾 → 只存檔供交叉驗證。
- `t187ap17_L` 的官方比率與本站由損益表自算的比率口徑不同，同樣先並存（`*_off`），不直接取代。

## 三、實作中發現並修掉的錯誤（重要）

### 1. TWTAWU 含「已恢復」紀錄 → 誤標停牌

`TWTAWU` 回傳的暫停交易紀錄**可能是已經恢復的**。實測 2026-11-14：

- `2314 台揚`：停止 `2026-11-10`、恢復 `2026-11-11`（**早已恢復，當日正常交易、有收盤價 5.4**）

第一版程式只判斷「是否出現在清單中」→ 把它標成 `suspended`，等於**製造錯誤的停牌狀態**。
修正為比對日期（`is_halted_on`）：

- 停止日 > 當日 → 尚未停
- 無恢復日 → 仍在停
- **恢復日 ≤ 當日 → 已恢復，不算停牌**

且只有本檔造成的停牌（`suspended_reason='halt'`）才由本檔解除，
其他原因（例如無當日成交價）造成的 `suspended`（如 `1808 潤隆`）一律不動。

### 2. QA 規則與新架構不一致

`MARKET_EXTRAS_*` 規則第一版檢查 `stocks.json` 的逐列欄位；改為獨立檔後永遠誤報。
已改為檢查 `meta.market_extras`（來源與筆數）＋資料檔本體存在且有內容。

## 四、驗證結果（2026-11-14 實跑）

| 項目 | 結果 |
|---|---|
| `tests/test_market_extras_2026_11_14.py` | **24/24** |
| `tests/test_data_rules_2026_11_13.py` | **59/59** |
| `tests/test_known_errors.py` | **145/145**（含 1,300 KB 體積預算） |
| `tests/test_fake_data_regression.py` | 全通過 |
| Node 4 支（breadth／data-client／portfolio／screener） | 全 PASS |
| QA Gate | **🟢 ALLOW DEPLOY（Critical ERROR 0）** |
| `stocks.json` 大小 | 1,264 KB（預算 1,300 KB ✓） |
| `integrate_market_extras.py` 冪等 | 連跑兩次 md5 相同 ✓ |
| 停牌狀態 | `2314` 為 active（僅留停牌歷史）、`1808` 維持 suspended ✓ |
| 瀏覽器實看 | `mklab-stock-sources.html` 8 個表格皆有「本站應用」欄、狀態統計與程式一致 ✓ |

## 五、站台呈現

`mklab-stock-sources.html`：

- **每個表格新增「本站應用」欄位**（8 個表格、68 列）：
  ✅ 已應用 21、📦 已導入資料庫 4、⚠️ 空資料 1、— 未應用 42
- 頁首加入狀態圖例與統計
- 第 12 節補上「★★★ 六項已完成」現況說明

`mklab-stock-screener.html`：新增「官方加值」欄位群組
（月營收年增%、累計營收年增%、融資餘額(張)、融券餘額(張)），
按需載入 `market-extras.json` 後併入每列。群組刻意放在最後，
因為 `tests/test_screener_cols.js` 以索引斷言前面的群組順序。

## 六、已知限制

- **t187ap17_L／t187ap14_L 不含金控／銀行／保險**（2881／2882／2891 實測缺席），
  金融類仍走「官方 PE 反推 EPS」，這兩支端點救不了該缺口。
- **holidaySchedule 目前回傳的是 116 年（2027）年度**清單，不含當年度（115），
  因此現階段還不能用來驗證 2026 年的交易日；待跨年後可用。
- `root` 的 `twtazu_od`（漲跌證券數）出表日期停在 `1150605`，疑似非每日更新，未導入。
