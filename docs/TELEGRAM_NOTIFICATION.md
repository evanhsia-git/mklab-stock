# MKLAB-STOCK — Telegram 自動通知系統（v1.0）

> 2026-11-25 建立。獨立、輕量、安全：由 GitHub Actions 執行，不依賴
> Hermes Agent／VPS／外部伺服器。Fork 即可運作（未設定 Secrets 時通知
> 安全跳過，不影響任何資料更新與部署）。

## 1. 系統架構

```
┌─ GitHub Actions（全部執行環境）──────────────────────────┐
│ daily-update.yml ──┐                                      │
│ qa-gate.yml ───────┼─→ scripts/telegram_notify.py ─→ api.telegram.org
│ telegram-test.yml ─┘      │                                 │
│                           │ TELEGRAM_BOT_TOKEN / CHAT_ID    │
│                           │ （僅存於 GitHub Secrets）        │
└───────────────────────────┼─────────────────────────────────┘
                            └→ 失敗一律 exit 0，不影響主流程
```

- 核心模組 `scripts/telegram_notify.py`：純 Python 標準庫，零第三方套件
- 測試 `tests/test_telegram_notify.py`：unittest＋mock，**不呼叫真實 API**
- 獨立測試 `.github/workflows/telegram-test.yml`：workflow_dispatch 手動觸發
- 訊息預設**純文字**（不送 parse_mode），避免 Markdown/HTML 特殊字元解析失敗
- 已知限制：GitHub Actions 未啟動、平台故障、或 workflow 被強制取消時，
  通知**可能無法送達**；timeout 後重試在極少數情況下可能造成重複通知
  （模組不做去重，不得宣稱完全去重）。

## 2. Telegram Bot 建立（約 3 分鐘）

1. Telegram 搜尋 **@BotFather** → `/newbot`
2. 輸入顯示名稱（如 `MKLAB-STOCK 通知`）→ 輸入 bot username（須以 `bot` 結尾）
3. BotFather 回覆一組 **Token**（格式 `1234567890:AAxxxx...`）——
   **此 Token 即密碼，僅貼到 GitHub Secrets，不要貼到任何程式碼或對話**

## 3. Chat ID 取得

**方法 A（推薦）**：先把要收訊息的對話（私訊或群組）跟你的 bot 開啟，
瀏覽器開：
```
https://api.telegram.org/bot<你的Token>/getUpdates
```
在回應 JSON 中找 `"chat":{"id":8730017948,...}`——該數字即 Chat ID。
（群組的 id 為負值，如 `-1001234567890`，原樣使用。）

**方法 B**：使用 @userinfobot——私訊它即回覆你的個人 Chat ID。

## 4. GitHub Secrets 設定

repo 頁面 → **Settings → Secrets and variables → Actions → New repository secret**

| Name | Value | 必要 |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather 給的完整 Token | ✅ |
| `TELEGRAM_CHAT_ID` | 取得的 Chat ID（純數字或負數） | ✅ |

**Variables（選配開關）**——同頁面 **Variables** 分頁：

| Name | 預設（未設定時） | 說明 |
|---|---|---|
| `TELEGRAM_ENABLED` | 啟用 | 設 `false`/`0` 即全域停用通知 |

⚠️ 安全規則（模組已強制，也請遵守）：
- Token 只存在於 GitHub Secrets，不寫入任何程式碼／HTML／JSON／.env.example
- 含 Token 的 `.env` 不入 Git（`.gitignore`）
- 模組所有例外訊息與日誌會自動遮蔽 token/chat_id，不輸出 API URL
- Token 不進 Artifacts、不進 Pages 部署產物、不送非官方 API

## 5. 手動測試

repo 頁面 → **Actions → Telegram Notification Test → Run workflow**

- `mode: dry-run`：驗證模組邏輯與訊息分段，**不需 Secrets**、不實際發送
- `mode: real`：實際發送測試訊息；未設 Secrets 顯示 SKIPPED（非失敗），
  發送失敗才會讓 workflow 失敗（--strict 僅作用於本測試 workflow）

Workflow 會先跑完整單元測試（32 情境）再執行發送。

## 6. 通知事件分類（v1.1 已實作——telegram-notify.yml workflow_run 監聽器）

**架構**：不修改任何既有 workflow。`.github/workflows/telegram-notify.yml`
監聽 daily-update／qa-gate／pages build and deployment 的完成事件，
呼叫 `scripts/telegram_report.py` 組訊息後發送（零侵入、單檔回退）。

| 級別 | 事件 | 通知與否 |
|---|---|---|
| P0 Critical | QA 閘門失敗、資料驗證失敗、Pages 部署失敗、發布遭阻擋 | 每事件即時單發 |
| P1 Warning | 資料源失效、備援啟用、欄位缺漏、更新停滯、容量近檻、QA Warning | 同 workflow 彙整成一則 |
| P2 Info | 每日更新成功、QA 通過、部署成功、每月稽核 | 每日一則彙總報告 |
| P3 Future | LKG 啟動／回退／版本差異 | 僅保留介面，現階段不啟用 |

**防濫發設計**：同一次 workflow 的 Warning 彙整單發；Critical 獨立發；
不做每檔股票通知；通知模組自身失敗不再觸發通知（無循環）。

## 7. 故障排除

| 症狀 | 檢查 |
|---|---|
| SKIPPED（未設定） | Secrets 名稱拼寫（`TELEGRAM_BOT_TOKEN`／`TELEGRAM_CHAT_ID`） |
| HTTP 401 | Token 錯誤或已被 revoke——重新向 BotFather 取得 |
| HTTP 403 | 封鎖了 bot，或 bot 未被加入群組——先傳 `/start` 給 bot |
| HTTP 400 | Chat ID 錯誤（檢查負號）；訊息超長會自動分段，非此原因 |
| HTTP 429 | 限流——模組會等 retry_after 重試；持續出現請降低通知頻率 |
| 持續失敗 | 先用 telegram-test workflow 的 real 模式隔離測試 |

## 8. Token 洩漏處理

1. BotFather → `/revoke` 產生新 Token（舊的立即失效）
2. 更新 GitHub Secrets 的 `TELEGRAM_BOT_TOKEN`
3. 若 Token 曾被 commit：視同已洩漏，除 revoke 外檢視 Git 歷史是否需清理
   （Token revoke 後歷史中的舊值即無效，一般無需改寫歷史）

## 9. Fork 使用方式

Fork 後**不需設定任何 Secrets 也能正常運作**——所有通知步驟會輸出
SKIPPED 並安全跳過。想要通知時，僅需設定上面兩個 Secrets。

## 10. 停用通知

- 全域：Settings → Variables → `TELEGRAM_ENABLED=false`
- 單一 workflow：移除該 workflow 內使用 `telegram_notify.py` 的 step
- 徹底移除：見 §11

## 11. 回退及移除方式

- 模組為**新增檔案**，不影響任何既有檔案：刪除
  `scripts/telegram_notify.py`、`tests/test_telegram_notify.py`、
  `.github/workflows/telegram-test.yml`、`docs/TELEGRAM_NOTIFICATION.md`
  即完全回退（git rm 後 commit）
- 正式整合（v1.1）時，每個通知 step 皆為獨立 step，逐一刪除即可回退，
  資料更新與部署邏輯零改動

## 12. 未來 LKG 通知擴充（P3——現階段不啟用）

模組的 `send()` 為通用介面（輸入純文字即可），LKG 啟用後僅需：
1. `lkg-promote.yml` 成功／失敗 step 呼叫 `telegram_notify.py`
2. 訊息模板加入 LKG tag／manifest SHA／回退原因
3. 不修改 LKG 核心邏輯本身
