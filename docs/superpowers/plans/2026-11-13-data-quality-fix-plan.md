# 資料品質修正計畫（2026-11-13）

來源：2026-11-13 隨機抽查（台股上市股票/ETF、美股股票/ETF 各 20 檔）與全量規則檢查。
目標：修正已知根因，並讓同類問題在發布前被 `qa_gate.py` 攔下。

## 一、根因與對應修正

| # | 症狀 | 根因（已在程式碼中確認） | 修正 | 狀態 |
|---|---|---|---|---|
| 1 | 台股 1087 檔股本全為 0，市值無法計算 | `TWSE_BALANCE` 指向 `t187ap05_L`，該端點實為「月營收」，無股本欄位 | 改用 `t187ap07_L_{ci,basi,bd,fh,ins,mim}` 資產負債表；股本（仟元）×1000 換算為元；加單位保險絲 `capital_unit_plausible` | 程式已修，**需實際抓取驗證** |
| 2 | 上市股價日期 11-11，上櫃 11-12 | TWSE 端點未更新或取用舊資料；流程未比對 TPEX 日期 | `fetch_data.py` 加 TWSE 落後 TPEX 告警；`qa_gate` 新增 `TWSE_STALE`（ERROR） | 偵測已加；**需重抓驗證** |
| 3 | 美股 ETF 年初至今報酬顯示 1173.5（實為 11.7%） | `ytdReturn` 已是百分比，程式又 ×100 | 移除 ×100；快照以 `meta.units.ytd=pct` 冪等修正 | **已修正快照**（30 檔） |
| 4 | 美股殖利率 58、156、257（實為 0.58%、1.56%、2.57%） | `dividendYield` 已是百分比，程式又 ×100 | 優先 `dividendRate ÷ 價格`；快照以 `meta.units.div=pct` 修正 | **已修正快照**（30 檔） |
| 5 | BRK-B 淨值比 0.0011、ABBV -113.6 | `priceToBook` 來源失真 | 優先 `價格 ÷ bookValue`；超出 (0.05, 200) → null | **已修正快照** |
| 6 | 47–49 檔 EPS 為負仍有本益比（例 福懋油 PE 120） | 本益比與 EPS 來源期間不同，未做負 EPS 判斷 | `sanitize_pe`：EPS≤0 或 PE 超範圍 → null | **已修正快照** |
| 7 | PE 與 價/EPS 偏差 >25%（約 266 檔） | PE（BWIBBU）與 EPS（官方年化累計）基準不同 | 僅告警（WARNING），待統一期間基準後再升級 | 告警已加，**待改善計畫第三階段** |
| 8 | 美股 ETF 費用率 30/30 為空 | yfinance 欄位缺漏 | 告警（WARNING）；待找替代欄位 | 告警已加 |
| 9 | QA 閘門在上述問題下仍判定 ALLOW DEPLOY | 閘門缺數值與跨欄位檢查 | `qa_gate` 新增「資料品質規則」區段，共 10 類規則 | **已完成** |

## 二、本次交付的檔案

- `skills/data/data_rules.py`（新）：單位換算、合理範圍、跨欄位一致性、快照驗證，**唯一的規則來源**。
- `skills/data/sanitize_snapshot.py`（新）：對既有快照做確定性修正，冪等，支援 `--dry-run`。
- `skills/data/fetch_data.py`：股本端點、單位換算、PE 負 EPS 處理、TWSE 落後告警。
- `skills/data/fetch_us_data.py`：ytd、殖利率、淨值比單位修正。
- `skills/qa-gate/qa_gate.py`：新增資料品質規則區段，並語法檢查新模組。
- `tests/test_data_rules_2026_11_13.py`（新）：30 項回歸測試，含修正前後的美股快照比對。
- `tests/fixtures/us-*-pre-2026-11-13.json`（新）：修正前的原始美股快照，供回歸測試固定使用。
- `data/stocks.json`、`data/us/us-stocks.json`、`data/us/us-etfs.json`：僅套用確定性修正（PE、殖利率、ytd、淨值比）。**股本與 TWSE 日期未修改，無法在離線環境修正。**

## 三、驗證結果

- `python3 -m unittest tests/test_data_rules_2026_11_13.py`：30/30 通過。
- 既有測試：`test_known_errors.py` 143/143、`test_fake_data_regression.py` 通過、JS 測試 32/32 通過。
- `qa_gate.py`：修正後判定 **BLOCK DEPLOY**，Critical ERROR 2 項，且僅剩需重抓資料才能解決的兩項：
  - `CAPITAL_ZERO`：股本為空（需重跑 `fetch_data.py` 抓取資產負債表）
  - `TWSE_STALE`：上市日期落後（需確認 TWSE 是否已更新後重跑）
  - 美股單位錯誤、負 EPS 的 PE 已全部清除。

## 四、上線前必須人工確認（離線環境無法驗證）

1. 在能連到 `openapi.twse.com.tw` 的環境執行 `python3 skills/data/fetch_data.py`，確認 log 出現 `資產負債表取得 N 檔股本`，且 2330 股本約 2,593 億元（259,303,804 仟元）。若出現「單位疑似錯誤，整批不採用」，代表仟元假設不成立，需改 `BALANCE_CAPITAL_UNIT_TWD`。
2. 確認 TWSE 最新交易日是否為 2026-11-12；若 TWSE 仍為 11-11，屬來源延遲，需等待或重跑。
3. 重跑 `python3 skills/data/fetch_us_data.py all`，確認 ytd、殖利率在合理範圍（殖利率中位數約 1%）。
4. 執行 `python3 skills/qa-gate/qa_gate.py`，目標：Critical ERROR 0，才可 ALLOW DEPLOY。

## 五、改善計畫（防止問題再發生）

**第一階段（已完成）**：根因修正、規則集中化、閘門加強、回歸測試。

**第二階段（一週內）**
- 在 `daily-update.yml` 的 `daily` job 於 commit 前加入 `python3 skills/data/sanitize_snapshot.py`，並在 `fetch_data.py` 寫入後直接跑 `qa_gate`，使 ERROR 在寫入前就阻擋。
- 將 `tests/test_data_rules_2026_11_13.py` 加入 `qa-gate.yml`，PR 時自動執行。
- `ci_commit_push.sh` 在 push 前比對 `meta.price_asof_counts`，TWSE 與 TPEX 日期不一致時不推送。

**第三階段（一個月內）**
- 統一 PE 與 EPS 的期間基準（建議 PE 由 `價 ÷ 官方 TTM EPS` 自行計算，BWIBBU 僅作對照）。
- 跨來源抽樣：每日隨機 30 檔與 FinMind／yfinance 比對收盤價，差異 >0.5% 告警。
- 日環比異常：市值單日變動 >30%、成交量超過 20 日均量 10 倍，觸發人工覆核。
- 歷史快照比對：市值突然大幅改變、ETF 成分股數量突減（需先新增 `etf-holdings` 抓取，目前 repo 內 `data/etf-holdings.json` 覆蓋範圍不足）。
- 美股 ETF 費用率：找替代來源（例如發行商 CSV），或在 UI 明確標示「未提供」。

**驗收標準**：連續 10 個交易日 qa_gate Critical ERROR 為 0；抽查（每週 20 檔 × 4 類）發現的錯誤數為 0。

## 六、回滾

所有修正皆為獨立函式，`data_rules.py` 可單獨還原。若新端點抓取異常，`fetch_balance_sheet` 會回傳空 dict，市值沿用前次值（`market_cap` 不補 0），不會寫入錯誤資料。
