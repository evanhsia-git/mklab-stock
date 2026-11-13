# 修改說明｜2026-11-13 資料品質修正

本包對應 2026-11-13 隨機抽查與全量規則檢查的結果。完整根因與後續計畫見 `docs/superpowers/plans/2026-11-13-data-quality-fix-plan.md`。

## 一、新增檔案

| 檔案 | 用途 |
|---|---|
| `skills/data/data_rules.py` | 資料品質共用規則：股本單位換算、市值計算、PE 與負 EPS 處理、美股殖利率／年初至今報酬／淨值比修正、快照驗證（唯一規則來源） |
| `skills/data/sanitize_snapshot.py` | 對既有快照做確定性修正，冪等，支援 `--dry-run`，會保留原檔格式 |
| `tests/test_data_rules_2026_11_13.py` | 30 項回歸測試，含修正前後的美股快照比對 |
| `tests/fixtures/us-stocks-pre-2026-11-13.json`、`us-etfs-pre-2026-11-13.json` | 修正前的美股原始快照，供回歸測試固定使用 |
| `docs/superpowers/plans/2026-11-13-data-quality-fix-plan.md` | 修正計畫（根因、驗證、上線前檢查、三階段改善） |

## 二、修改檔案

### `skills/data/fetch_data.py`
- **股本端點**：`TWSE_BALANCE` 由 `t187ap05_L`（月營收）改為 `t187ap07_L_{ci,basi,bd,fh,ins,mim}` 資產負債表，逐一讀取「股本」欄位。
- **單位換算**：股本以仟元計，換算為新台幣元。
- **單位保險絲**：換算後股數中位數不在 1 千萬至 500 億股之間，整批丟棄並記錄錯誤，避免寫入錯誤市值。
- **市值計算**：改用 `data_rules.market_cap_from_capital`，無效時不補 0。
- **本益比**：EPS ≤ 0 時本益比設為空（上市與上櫃皆適用）。
- **日期告警**：若上櫃最新日期晚於上市，記錄 `twse_stale_vs_tpex` 並輸出警告。

### `skills/data/fetch_us_data.py`
- **年初至今報酬**：移除多餘的 ×100（yfinance 已是百分比）。
- **殖利率**：優先使用 股息 ÷ 價格；退回 `dividendYield` 時不再乘 100；超過 30% 設為空。
- **淨值比**：優先使用 價格 ÷ 每股淨值；超出 0.05–200 範圍設為空。

### `skills/qa-gate/qa_gate.py`
- 語法檢查清單加入 `data_rules.py`、`sanitize_snapshot.py`。
- 新增「資料品質規則」區段，共 10 類檢查：股本為空（ERROR）、EPS ≤ 0 仍有 PE（ERROR）、上市日期落後上櫃（ERROR）、美股殖利率與年初至今報酬單位錯誤（ERROR）、市值 ≤ 0（ERROR）、PE 與價／EPS 不一致（WARNING）、無收盤價（WARNING）、美股淨值比異常（WARNING）、美股 ETF 費用率為空（WARNING）、規則檢查本身失敗（ERROR）。

### 資料快照（僅確定性修正，格式保留）
- `data/stocks.json`：49 檔 EPS ≤ 0 的本益比設為空。
- `data/us/us-stocks.json`：殖利率整批 ÷100（30 檔）；BRK-B、ABBV 淨值比設為空。
- `data/us/us-etfs.json`：年初至今報酬整批 ÷100（30 檔）。
- **未修改**：股本（全部為 0）與上市日期（11-11 落後）。這兩項必須重新抓取，離線環境無法修正。

## 三、驗證

- `tests/test_data_rules_2026_11_13.py`：30/30 通過。
- 既有測試：`test_known_errors.py` 143/143、`test_fake_data_regression.py` 通過、JS 測試 32/32 通過。
- `fixes.patch` 已對乾淨的原始 repo 套用驗證，可正常套用。
- `qa_gate.py` 修正後判定 **BLOCK DEPLOY**，Critical ERROR 2 項（股本、上市日期），皆需重新抓取資料才能解除。這是預期行為。

## 四、上線前必做

1. `python3 -m unittest tests/test_data_rules_2026_11_13.py`
2. 在可連 TWSE 的環境執行 `python3 skills/data/fetch_data.py`，確認 log 有「資產負債表取得 N 檔股本」，2330 股本約 2,593 億元。若出現「單位疑似錯誤」，修改 `data_rules.py` 的 `BALANCE_CAPITAL_UNIT_TWD`。
3. `python3 skills/data/fetch_us_data.py all`
4. `python3 skills/qa-gate/qa_gate.py`，目標 Critical ERROR 為 0。

## 五、已知限制

- 資產負債表端點與仟元單位是依官方欄位說明推定，未能連線 TWSE 實測。
- PE 與價／EPS 期間不一致（約 266 檔）目前僅告警，待統一期間基準。
- 美股 ETF 費用率來源缺漏，目前僅告警。
- `daily-update.yml` 尚未加入 `sanitize_snapshot.py` 步驟，建議依計畫第二階段補上。
- 未修改 `daily-update.yml`，因此排程尚不會自動執行快照修正。

---

## 六、2026-11-13 套用後的追加修正（本機實抓驗證）

本包已在可連 TWSE / yfinance 的環境套用並完成第 2～4 步，過程中發現三處需要再修，已一併修正。

### 1. 股本來源改為 `t187ap03_L`（本包原用的 `t187ap07_L_*` 覆蓋率不足）

- 根因：`t187ap07_L_{ci,basi,bd,fh,ins,mim}` 只含「該期別已申報」的公司，實測 **752/1,099**，
  台積電 2330、富邦金 2881 等都不在內 → 股本仍為 0，`CAPITAL_ZERO` 重抓也無法解除。
- 修正：改用上市公司基本資料 `t187ap03_L` 的 **實收資本額**（涵蓋 1,099 家、單位已是新台幣元，
  沒有仟元換算的單位風險）作為主要來源；`t187ap07_L_*` 降為備援。
- 驗證：2330 股本 = 259,323,700,670 元（2,593.24 億元，與本包預期值一致）；
  一般股票股本覆蓋 **1086/1086、0 缺**；市值驗算 2340 × 25,932,370,067 = 60,681,745,956,780 相符。

### 2. `TWSE_STALE` 規則原本會永久誤判（已改為分級）

- 根因：TWSE `STOCK_DAY_ALL` 結構上只發 **T-1**，TPEX `tpex_mainboard_daily_close_quotes` 發 **T-0**
  （實測 2026-11-13 盤後：TWSE 回 11-12、TPEX 回 11-13）→ 原規則「TPEX 日期 > TWSE 日期即 ERROR」
  在每個交易日盤後都成立，閘門永遠 BLOCK，且重抓也不會解除。
- 修正：以快照內出現過的 `price_asof` 當交易日曆計算落後幾個交易日——
  **落後 1 日 → WARNING（`TWSE_T_MINUS_1`，屬來源既定行為）；落後 ≥2 日 → ERROR（`TWSE_STALE`）**。
- 測試同步：原「落後 1 日 = ERROR」案例改為兩案例（1 日→WARNING、2 日→ERROR）。

### 3. 回歸測試不應耦合線上快照

- 根因：`RealSnapshotRegression` 直接讀 `data/stocks.json` 並斷言「股本全為 0」；
  資料修好後這兩個測試反而失敗（「修好 = 測試壞掉」的假訊號）。
- 修正：改用固定的修正前台股樣本 `PRE_FIX_TW`；並新增 `test_sanitize_cannot_fix_capital_zero`
  保留原意（快照修正不可能修好股本，必須重抓官方資料）。

### 套用後實測結果

- `tests/test_data_rules_2026_11_13.py`：**32/32 通過**（原 30 項 ＋ 追加 2 項）。
- `test_known_errors.py` 143/143、`test_fake_data_regression.py` 全通過、4 支 node 測試全通過。
- `fetch_data.py daily` → trade_date 2026-11-12；後續鏈（compute_indicators／integrate_official_company／
  build_kline／compute_industry／build_digest）全部成功（K 線 1,444 檔 414,479 筆、32 產業）。
- `fetch_us_data.py all` → 美股 30 檔（div 0~3.29%、pb 全在範圍）、ETF 30 檔（ytd −9.46%~33.56%）。
- `qa_gate.py`：**🟢 ALLOW DEPLOY（Critical ERROR 0）**。

### 仍未處理（維持告警，非阻擋）

- `PE_EPS_MISMATCH` 266 檔（PE 與價／EPS 期間基準不一致）。
- 美股 ETF 費用率 30/30 為空（來源缺漏）。
- `daily-update.yml` 尚未加入 `sanitize_snapshot.py` 步驟。
- **觀察**：1808 潤隆自 2026-11-12 起不在 TWSE 每日行情 feed（最後成交日 11-11，疑似停牌），
  該檔因此從快照消失（1445 → 1444）。目前行為是「依當日 feed 重建」，未保留停牌標的；
  建議後續改為保留既有標的並標示停牌，避免個股無聲消失。

---

## 七、隨機抽查（80 檔）發現的缺陷與第一階段修正

2026-11-13 以固定種子 `20261113` 抽樣台股上市股票 20／台股 ETF 20／美股 20／美股 ETF 20，
與 TWSE / TPEx / yfinance / FinMind 交叉比對。

**比對結果（修正前）**：台股 60/60 與外部來源精確吻合（TWSE、TPEx、FinMind 三源）；
美股個股 30/30 吻合；結構檢查（重複代號、H<L、負量、市值≤0、未來日期、不可能日漲跌）全過。
但找到三個會讓使用者看到錯數字的缺陷：

### 1. 市值用「股本 ÷ 10」推股數 → 32 檔算錯（P0）

- 根因：`market_cap_from_capital` 假設面額固定 10 元，但台股面額有 0.5／1／2.5／5 元，
  甚至有「無面額」公司；13 檔誤差 >20%，合計低估約 1.07 兆元。
  最嚴重 `6919 康霈*`（面額 0.5 元）市值 5.4B 應為 108.2B，**差 20 倍**。
- 修正：改用 `t187ap03_L` 的 **「已發行普通股數」**（`data_rules.market_cap_from_shares`），
  不對面額做任何假設；`market_cap_from_capital` 降為備援。快照新增 `shares` 欄位供稽核。
- 驗證：全庫 1084 檔「市值 = 收盤 × 已發行股數」**0 檔不符**；
  `2327 國巨*` 209.9B → 839.7B（+300%）、`6919 康霈*` 5.4B → 108.2B（+1900%）。

### 2. 美股 ETF 的 price 取 `navPrice`（淨值）而非市價（P1）

- 根因：`fetch_us_data.py` 的 `price = navPrice or currentPrice or ...`。淨值晚一天更新且非市價，
  而 `chg` 卻用市價的 `previousClose` 算 → 價格與漲跌幅口徑不一致。
  16/30 檔與市場收盤差 >0.5%，最大 3.64%（GLD）。
- 修正：`price` 改用 `currentPrice / regularMarketPrice`；淨值另存 `nav` 欄位供參考。
- 驗證：`price == nav` 由 2/30 → **0/30**；與市場收盤偏差中位數 0.56% → **0.058%**、
  最大 3.64% → **0.165%**（殘差為美股盤中即時價位漂移）。

### 3. ETF「成份股總數」被截斷（P1）

- 根因：`etf-holdings.json` 的 `n` 文件寫「成份股總數」，實測 363 檔**全部 `n == items 長度`**，
  其中 299 檔剛好 = 10；前端把它當總數顯示 → `0050` 顯示 10 檔（實際 50）、`00850` 顯示 10（實際約 100）。
- 修正：語意修正為可證實的值（`data_rules.etf_holdings_n` + `sanitize_etf_holdings_doc`）：
  - `n_listed` = 實際列出檔數（永遠可證實）
  - `n` = 官方直出完整清單（`src` 為 `FUBON`）或「列出的檔數 ≠ 10」（截斷只發生在前 10 大這個切點）
    → 填實際數；其餘**無法證實 → null**
  - 前端 `n == null` 顯示「—」，不得回填 `items.length`（否則又把 10 謊稱成總數）
- 驗證：363 檔中 **72 檔可證實、291 檔改 null**；`0050` 顯示「—」、`006208` 顯示「50 檔」、
  `00632R`（6 檔）／`00653L`（3 檔）等短清單正確保留。

### 4. qa_gate 新增 3 條防護規則（防止再犯）

- `MARKET_CAP_MISMATCH`（ERROR）：市值與 收盤 × 已發行股數 不符 >1%
- `US_ETF_PRICE_IS_NAV`（ERROR）：美股 ETF 的 `price` 與 `nav` 位元級相等（取錯欄位）
- `ETF_HOLDINGS_TRUNCATED`（WARNING）：`n == 10` 且 `items` 長度 == 10（截斷跡象）

### 5. 回歸測試

`tests/test_data_rules_2026_11_13.py` 由 32 項擴充到 **44 項**，新增 3 個測試類別
（`MarketCapFromShares`、`UsEtfPriceMustBeMarketPrice`、`EtfHoldingsCountSemantics`），
分別鎖住上述三個事故（含「面額 0.5 元會差 20 倍」與 sanitize 冪等性）。

### 驗證總結

- `test_data_rules_2026_11_13` 44/44、`test_known_errors.py` 143/143、
  `test_fake_data_regression.py` 全通過、4 支 node 測試全通過、`py_compile` 全通過、
  前端 JS `node --check` 全通過。
- 瀏覽器實測 compare 頁：0 console 錯誤；ETF 總數顯示「—／50 檔」如預期。
- `qa_gate.py`：**🟢 ALLOW DEPLOY（Critical ERROR 0）**。

### 仍未處理（第二／三階段）

- 停牌標的改為保留 + 標示（1808 事件）
- PE 與價／EPS 期間基準統一（266 檔）
- 美股 ETF 費用率來源補齊（30/30 為空）
- `daily-update.yml` 納入 `sanitize_snapshot.py`
