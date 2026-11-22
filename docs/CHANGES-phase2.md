# 第二階段修改說明｜stocks.json 安全精簡（2026-11-22）

依第一階段盤點報告，執行你同意的項目：1）刪除孤兒與無引用欄位；2）依建議處理 ETF 價格與 close 的不一致；3）移出孤兒匯出檔。費用來源（第八節第 1 項）因需要外部核對，本次**未修改**。

## 一、檔案大小

| 項目 | 修改前 | 修改後 |
|---|---|---|
| data/stocks.json | 3,177,480 bytes（縮排格式） | 1394063 bytes（緊湊格式） |
| 欄位數 | 111 | 76 |
| 列數 | 1,449 | 1,449（未增減） |

大小變化的來源拆開計算：
- 刪除欄位：約 827 KB（約佔原檔 26%）
- 縮排改為緊湊格式：約 954 KB（約佔原檔 30%）。這是排版變化，JSON 內容不變，前端讀取結果相同。

## 二、刪除內容

| 類別 | 欄位 | 依據 |
|---|---|---|
| 孤兒欄位（19 個） | `official_*` 全部 | 與 official-fundamentals.json 逐筆 100% 相同；全 repo 無寫入端、無讀取端 |
| 無引用欄位（14 個） | annualized_return_3y/5y、dividend_frequency、fee_checked_at、holdings_coverage_pct、holdings_total_count、holdings_type、holdings_verified、last_distribution_date、max_drawdown、return_10y、return_3y、sharpe_ratio、volatility_1y | 前端、後端、欄位選單、測試皆無引用 |
| 全 null 欄位 | custody_fee | 1,449 列全部為 null；費用顯示來自 etf-meta.json |
| 過期重複欄位 | ETF 列的 close（359 列） | 分割前的舊值，例：0050 為 180.0，實際最新價為 90.2（1 拆 4 已完成）。price 與 K 線、每日快照一致，故保留 price。 |

## 三、移出的檔案

- `data/etf_export_20261122.csv`（333 KB）：全 repo 無任何程式引用的孤兒匯出檔。原檔已備份於 `removed-data-etf_export_20261122.csv`。

## 四、驗證

- 所有保留欄位的值與修改前逐列比對，**完全相同**；列數與代號順序不變；meta 不變。
- JavaScript 測試 6 組全部通過；Python 測試 9 組通過，其中 `test_known_errors.py` 有 1 項失敗（見第五節）。
- QA 閘門修改前後皆為 ALLOW DEPLOY，Critical ERROR 0。
- 本機瀏覽器測試：螢幕篩選、研究、觀察清單、首頁、美股頁皆無 JavaScript 錯誤，表格列數與修改前相同。

## 五、尚未完成或需要你決定的事項

1. **單檔預算測試仍失敗**（`test_known_errors.py`：「單檔預算 1,300 KB」，目前 1394063 bytes ≈ 1,361 KB）。此測試在**修改前的線上版本就已失敗**（修改前為 3,103 KB）。剩下的超標主要來自 ETF 持股 `holdings`（約 186 KB，與 etf-holdings.json 重複，前 10 大）。移除該欄位即可通過測試，但這屬於第二階段第 5 項，需要你同意後再做。
2. **縮排格式回退**：所有寫入 stocks.json 的腳本目前都輸出緊湊格式，但線上檔案是縮排格式（3.18 MB），來源無法從程式碼確定。這可能是 11-10 的瘦身結果在某次提交中被還原。建議確認提交紀錄，並讓寫入端統一緊湊格式。
3. **費用來源（未處理）**：
   - 螢幕篩選頁顯示的管理費與總費用來自 etf-meta.json，該檔以基金規模（AUM）階梯**推算**（`parse_etf_meta.py` 的 `compute_etf_fees`），不是發行商公告。
   - stocks.json 的 `management_fee`／`total_fee` 與 etf-fees.csv 的 moneydj 欄位完全相同（323／323），是 moneydj 來源的原始值，因此不能刪除。
   - 需決定費用的權威來源，並以發行商公告逐檔核對；在此之前，頁面應標示為「估算」。
4. **ETF close 的顯示問題**：螢幕篩選頁的 ETF 列是以 etf-meta.json 為底，其 `close` 同樣是過期值。本次只刪除 stocks.json 的 close，不影響 etf-meta.json；若畫面上有「收盤」欄，仍會顯示過期價格。建議改用 price，或每日更新 etf-meta 的 close。

## 六、檔案

- `data/stocks.json`：修改後的完整檔案（SHA-256：50e9fe4ced76a892a1bf85564e38e559d64eafeb75a053f2407e7e9e517b4762）
- `scripts/prune_stocks_phase2_2026_11_22.py`：本次執行的腳本（可重複執行，但只能用於修改前的檔案）
- `removed-data-etf_export_20261122.csv`：被移出的孤兒匯出檔（備份）
