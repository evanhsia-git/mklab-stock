# 修改說明｜美股月漲跌、年漲跌補齊（2026-11-17）

## 目的
美股市值前 30 大（個股）與 ETF 規模前 30 大，原本只有當日漲跌，月漲跌與年漲跌為空白。本次新增歷史價格計算，並在頁面顯示。

## 定義（以交易日計，使用 yfinance 調整後收盤 auto_adjust=True）
| 欄位 | 定義 |
|---|---|
| `chg_1m` | 最後收盤 ÷ 21 個交易日前收盤 − 1 |
| `chg_1y` | 最後收盤 ÷ 252 個交易日前收盤 − 1 |
| `chg_ytd` | 最後收盤 ÷ 上一年度最後收盤 − 1（寫入資料，頁面目前未顯示） |

欄位名稱與台股 `chg_1m`、`chg_1y` 一致。

## 檔案變更

**新增**
- `skills/data/fetch_us_returns.py`：抓取 60 檔（個股 30 + ETF 30）近 2 年日線，計算報酬，寫回 `us-stocks.json`、`us-etfs.json`。
  - 單檔失敗：保留該檔前次數值，並記入 `meta.returns_failed`
  - 資料過舊（最後一根 K 棒距今超過 7 天）：視為失敗
  - 計算值超出 ±1000%：設為 null
  - 失敗比例超過 50%：回傳非零結束碼，CI 失敗、不推送
- `tests/test_us_returns.py`：18 項測試（定義、交易日索引、過舊、缺資料、異常值、失敗保留、格式保留、dry-run、欄位保留、覆蓋率規則）

**修改**
- `skills/data/fetch_us_data.py`：`fetch_us_data` 每日整檔覆寫，會把報酬欄位清掉。新增 `carry_return_fields()`，覆寫前先讀舊檔，把同代號的報酬欄位帶回。
- `skills/data/data_rules.py`：新增 `US_RETURNS_MISSING` 警告，月漲跌缺漏超過 30% 時提醒。
- `mklab-stock-us.html`：個股與 ETF 的月漲跌、年漲跌由寫死的 `null` 改為讀取資料欄位（`r.chg_1m ?? null`），缺值仍顯示「-」。
- `.github/workflows/daily-update.yml`：`us-market` job 在 `fetch_us_data.py` 之後、QA 閘門之前，新增 `fetch_us_returns.py` 步驟。

## 驗證
- `test_us_returns.py` + `test_data_rules_2026_11_13.py`：全部通過
- `test_known_errors.py` 145/145、`test_fake_data_regression.py`、JS 測試 32/32 全部通過
- 頁面腳本語法檢查（`node --check`）通過；workflow YAML 解析通過
- `qa_gate.py`：Critical ERROR 0，判定 ALLOW DEPLOY。目前顯示 4 項 `US_RETURNS_MISSING` 警告，是因為資料中尚未有報酬欄位，屬預期。

## 上線後需要確認（我這裡無法連到 Yahoo Finance）
1. 手動觸發 `us-market` workflow（workflow_dispatch），確認 log 顯示「合計失敗率」低於 50%。
2. 檢查 `data/us/us-stocks.json` 的 `meta.returns_failed` 是否為空或只有少數幾檔。
3. 抽查 3 檔（例如 AAPL、VOO、SPY）的 `chg_1y`，與 Yahoo 網頁或發行商頁面比對，誤差應在 0.5% 以內。
4. 第一次執行後，頁面應顯示數值；若仍是「-」，檢查 `data/us/*.json` 是否有 `chg_1m` 欄位。

## 已知限制
- yfinance 非官方來源，偶爾會限流或改格式。失敗時保留前次值，但若連續多日失敗，數字會變舊，因為 `returns_as_of` 會停在最後成功的日期。建議頁面未來加上「資料日期」標示。
- 「1M」用滾動 21 個交易日，不是「上個月月底至今」。頁面若要標註定義，需另行修改文案。
- 年初至今（`chg_ytd`）已寫入資料，但頁面目前沒有欄位顯示，如需要可再加一欄。
