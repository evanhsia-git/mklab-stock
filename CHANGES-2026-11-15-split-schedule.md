# CHANGES 2026-11-15 — 官方公司行為預告接入每日更新

## 目的
讓未來分割／減資「還沒發生就先知道」，不必等 K 線跳空才反推（detect_corporate_actions 是事後偵測）。

## 新增
- `skills/data/fetch_split_schedule.py`
  - 來源：TWSE `TWTBAU1`（暫停先賣後買當沖預告表）、`TWTBAU2`（同表歷史）、
    TPEx `tpex_intraday_trading_pre`
  - 只保留 `Reason` 含「分割／減資／換發」→ `data/corporate-actions-schedule.json`
  - `--register`：未登錄者以 `status=planned`、`ratio=null` 寫入 registry（冪等）
  - 三個來源全失敗時**不覆寫**既有排程檔
- QA 規則 `CORPORATE_ACTION_UPCOMING`（WARNING）
- 前端 planned 標籤（分割預告／反分割預告／減資預告）
- `daily-update.yml` 新增步驟（排在 build_kline 之前）

## 安全設計（不可回退）
| 設計 | 原因 |
|------|------|
| 預告一律 `ratio=null` | 預告沒有比率，推測值會被直接拿去算還原價 |
| `planned` 不觸發停牌 | sanitize 只對 `status=pending` ＋ `halt_from` 生效 |
| 漲跌幅豁免改為「需已量化（ratio 有值）且 done/pending」 | 否則任何有預告的標的都能無聲跳 30%，掩蓋真實異常（原豁免條件只看 `corporate_action` 是否存在） |
| 已登錄者不被預告覆寫 | 人工登錄的比率／停牌日比預告精確 |

## 實測（2026-11-15 首跑）
| 代號 | 名稱 | 類型 | 暫停當沖區間 | 狀態 |
|------|------|------|--------------|------|
| 0053 | 元大科技市值 | ETF分割 | 2026-11-27~12-03 | 已在 registry（pending，12-08 換發） |
| 6108 | 競國 | 減資 | 2026-12-07~12-11 | 自動登錄 planned |

線上實看：`6108 競國 +4.33% 減資預告`。

## 驗證
- 測試：新增 12 項（民國日期轉換、Reason 過濾、分類、冪等輸出、planned 登錄、planned 不被用於還原）
- 全套：35＋56＋11＋16＋24＋12 Python、145 known_errors、4 Node 全通過；QA Gate ALLOW DEPLOY
- CI：`327d99d8` qa-gate ✓、pages ✓
- 被排程插隊（ea1ef442）時以 `--ours` 取遠端 stocks.json ＋本地重跑 pipeline 重建：
  registry 30→31 筆、既有欄位零差異
