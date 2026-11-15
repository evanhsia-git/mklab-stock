# ETF 保留、停牌分割、市值與股本口徑 — 2026-11-15

對應 Ivan 提出的 6 項問題，逐項確認與修復。

## 一、00662 富邦NASDAQ 整檔從資料庫消失（最嚴重）

**現象**：`etf-meta.json` 有 00662，`stocks.json` 沒有。

**根因**（`skills/data/fetch_data.py` 的停牌沿用判定）：

```python
_listed = set(capital_stock_map.keys())   # ← 資產負債表，只有「公司」
...
if _sym in _fresh or _sym not in _listed:
    continue                              # ETF 永遠不在此清單 → 一停牌就整檔消失
```

`capital_stock_map` 來自**資產負債表**（`t187ap07_L_*`），而 ETF 沒有資產負債表
（實測：`t187ap03_L` 與 `t187ap07_L` 都不含 0050／00662）。
所以 ETF 一旦停牌（當日 feed 沒有行情）就被判定「不在上市清單」→ 不沿用 → 消失。
一般股票（如 1808 潤隆）在清單內，所以有被沿用 —— 這就是「股票活著、ETF 消失」的原因。

**修正**：
`_listed = set(capital_stock_map.keys()) | set(etf_ref or ())`
（`etf_ref` ＝官方基金清單，來自 `t187ap47_L`／ETF 篩選器；ETF 在下市前都留在清單內）

**已消失的補回來**（`skills/data/sanitize_snapshot.py` 新增 `restore_missing_etfs()`）：
掃「在站內 ETF 清單（`etf-classified.json`）卻不在快照裡」者，用 `etf-meta.json` 的官方基本資料
＋個股 K 線最後一根（本站 K 線由官方日行情產生）重建，**不冒充現價**：

```json
{"sym":"00662","name":"富邦NASDAQ","security_type":"etf","is_etf":true,
 "price":null,"price_asof":"2026-11-10","last_close":117.8,"last_close_date":"2026-11-10",
 "trading_status":"suspended","capital_stock":null,"market_cap":null,
 "corporate_action":{"type":"split","ratio":5.0,"halt_from":"2026-11-11","resume_date":"2026-11-17"},
 "halt_date":"2026-11-11","halt_resume":"2026-11-17","suspended_reason":"corporate_action"}
```

K 線查不到時只留 null（**不編造**最後成交價），已由測試覆蓋。

## 二、5 拆 1 的處理

新增登記表 `data/corporate-actions.json`（**每筆都必須有來源**），
由 `sanitize_snapshot.apply_corporate_actions()` 套用：停止交易期間標 `suspended`、
清掉當日價量與市值、標示 `corporate_action`。停止日未到者只標示不標停牌。

**⚠️ 官方端點查不到這檔的停牌與分割**：實測 `TWTAWU`（暫停交易證券）與
`TWT48U_ALL`（除權除息預告）**都不含 00662**（TWTAWU 只收短暫停牌如 2314 台揚）。
因此分割倍數來自 Ivan 提供之公告，已逐字記在 `source` 欄位；
停止日與最後成交價可由本站既有官方資料交叉驗證（K 線最後一根為 2026-11-10 收 117.8）。

**QA 假警報已排除**：`qa_gate` 的「異常漲跌 (>10.5% 警示 / >30% 阻擋)」原本會把
00662 恢復交易日（2026-11-17，價格約變 1/5）判成 >30% 而 **BLOCK DEPLOY**。
已改為：有 `corporate_action` 的標的分流，不計為異常（改列 WARNING 提醒確認還原價與技術指標）。

**尚未處理（需決策）**：K 線／技術指標仍用**原始價**，跨越分割日會不連續
（MA／RSI 會被 5 倍跳空扭曲）。`adj_close`（還原收盤）欄位在前端已預留但**沒有任何資料在填**。

## 三、price 為 null 卻留著舊市值（4 筆）

`data_rules.sanitize_stock_record()` 新增：`price is None` → `market_cap = None`。
（市值＝股價 × 股數，沒有當日股價就不該有「當日市值」；缺值顯示「—」）

實測 4 筆已清空：00625K、00643K、00707R、1538。另加 QA ERROR 規則 `MARKET_CAP_WITHOUT_PRICE`。

> 另註：`fetch_data` 的停牌沿用路徑本來就會清 market_cap；這 4 筆是**其他來源**
> （未走到停牌路徑、但股價已為 null）留下的舊值，所以防線要加在確定性修正層。

## 四、stocks.json 檔案大小

實測**沒有超過**：本機與線上皆是 **1,265～1,267 KB**（預算 1,300 KB），
`tests/test_known_errors.py` 第 380 行**通過**（全套 145/145，含此項）。
Ivan 看到的 1,418 KB 與現況不符（可能是不同時間點的檔案）。

**邊界提醒**：目前只差約 33 KB 就到上限。這次新增的 `corporate_action` 等欄位都很小，
但未來若要再加整檔欄位（如把 market-extras 併回來）會立刻超標 —— 架構上仍應維持獨立檔按需載入。

## 五、ETF 基本資料與分類更新

已於同日稍早的自動化 commit（`e0397e11`）處理：`fetch_etf_meta` ＋ `classify_etf` 接上排程。
本次驗證：00413A／00418A 皆為 `security_type=etf`、`is_etf=true` ✅

## 六、ETF 的 capital_stock 統一為 null

`data_rules.sanitize_stock_record()` 新增：`security_type == 'etf'` 且 `capital_stock == 0` → `null`。
實測 233 筆已全部清空（ETF 共 359 檔，`capital_stock == 0` 者現為 **0** 筆、`== null` 359 筆）。
一般股票的 0 **不動**（那是真的異常，要重抓財報）。另加 QA ERROR 規則 `ETF_CAPITAL_STOCK_ZERO`。

## 七、ETF 持股 299 筆無法確認完整成份股數

**已符合要求，無需修改**：`data/etf-holdings.json` 的 `n`（成份股總數）在只取得前 10 大時為 `null`
（實測：`n=null` **299** 筆、有值 64 筆），檔案 `meta.note` 明載
「只取得權重前 10 大、無法證實總數時為 null，前端顯示「—」而非錯誤的 10」。

## 驗證（2026-11-15 實跑）

| 項目 | 結果 |
|---|---|
| `test_etf_preservation_2026_11_15.py` | **15/15** |
| `test_known_errors.py` | **145/145**（含 1,300 KB 預算） |
| 四套 unittest 合計 | **109/109** |
| `test_fake_data_regression` / Node 4 支 | 全通過 |
| QA Gate | **🟢 ALLOW DEPLOY（Critical ERROR 0）** |
| `sanitize_snapshot` 冪等 | 連跑兩次 md5 相同 |
| 檔數 | 1445 → **1446**（+00662） |
| stocks.json | **1,266.8 KB**（< 1,300） |

## 檔案

| 檔案 | 變更 |
|---|---|
| `skills/data/fetch_data.py` | 沿用判定納入官方 ETF 清單（根因修正） |
| `skills/data/sanitize_snapshot.py` | 新增 `restore_missing_etfs`／`apply_corporate_actions`／`recompute_meta` |
| `skills/data/data_rules.py` | 2 條確定性修正 ＋ 2 條 QA ERROR 規則 |
| `skills/qa-gate/qa_gate.py` | 異常漲跌規則排除公司行為 |
| `data/corporate-actions.json` | 新增（公司行為登記表，逐筆附來源） |
| `tests/test_etf_preservation_2026_11_15.py` | 新增 15 項測試 |
