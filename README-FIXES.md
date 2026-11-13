# mklab-stock 資料品質修正包（2026-11-13）

對應文件：`docs/superpowers/plans/2026-11-13-data-quality-fix-plan.md`

## 內容
- 新增：`skills/data/data_rules.py`、`skills/data/sanitize_snapshot.py`、`tests/test_data_rules_2026_11_13.py`、`tests/fixtures/*pre-2026-11-13.json`、修正計畫文件
- 修改：`skills/data/fetch_data.py`、`skills/data/fetch_us_data.py`、`skills/qa-gate/qa_gate.py`、`data/stocks.json`、`data/us/us-stocks.json`、`data/us/us-etfs.json`
- `fixes.patch`：以上全部變更的 unified diff（相對於 repo main）

## 套用方式
方式 A（整檔覆蓋）：將本包檔案依相同路徑複製進 repo，然後 commit。
方式 B（patch）：`git apply --check fixes.patch && git apply fixes.patch`

## 套用後必做（離線環境無法完成）
1. `python3 -m unittest tests/test_data_rules_2026_11_13.py` → 應 30/30 通過
2. 在可連 TWSE 的環境執行 `python3 skills/data/fetch_data.py`
   - log 應出現「資產負債表取得 N 檔股本」，2330 股本約 2,593 億元
   - 若出現「單位疑似錯誤，整批不採用」，修改 `skills/data/data_rules.py` 的 `BALANCE_CAPITAL_UNIT_TWD`
   - 確認 TWSE 日期已是最新交易日
3. `python3 skills/data/fetch_us_data.py all`
4. `python3 skills/qa-gate/qa_gate.py` → 目標 Critical ERROR 0、ALLOW DEPLOY

## 目前狀態（已在本包驗證）
- 美股 ytd / 殖利率 / 淨值比單位錯誤：已修正
- 負 EPS 的本益比：已清除（49 項）
- 股本為 0、TWSE 日期落後：程式已修，快照需重抓才會消失，因此 qa_gate 目前仍 BLOCK DEPLOY（正確行為）

## 已知限制
- 未能連線 TWSE / yfinance，資產負債表端點與 仟元 單位為依官方欄位說明推定，需以第 2、3 步實測確認。
- PE 與 價/EPS 期間不一致（約 266 檔）目前僅告警，尚未統一基準。
- 美股 ETF 費用率來源缺漏，目前僅告警。

詳細修改說明見 `CHANGES-2026-11-13-data-quality.md`。
