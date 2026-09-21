# Skill Router（路由決策）

修改任務前，依下表判斷需要載入哪個 Skill 的 `skill.md`。

| 任務類型 | 載入 Skill | 執行腳本 |
|----------|-----------|----------|
| 修改後要部署 / Push 前驗證 | `qa-gate` | `qa-gate/qa_gate.py` |
| HTML 結構疑慮（空白頁/缺標籤） | `html-health` | `html-health/check_html_health.py` |
| 調整顏色/字體/版面/Design Token | `design-system` | —（規範） |
| 抓資料/更新 JSON/產生每日摘要 | `data` | `data/fetch_data.py`、`data/build_digest.py` |
| 部署到 GitHub Pages | `deployment` | —（GitHub Pages 依 `main` 分支變動自動發布，無需手動腳本，見 `deployment/github-pages.md`） |
| 新建功能/重構/編碼風格 | `development` | —（規範，見 `development/coding-style.md`） |

## 多重 Skill 場景

- **新增一個頁面**：`development`（編碼）→ `design-system`（UI 規範）→ `html-health`（結構）→ `qa-gate`（門禁）
- **資料更新後部署**：`data`（抓取）→ `qa-gate`（驗證）→ `deployment`（部署）
- **UI 調整**：`design-system` → `html-health` → `qa-gate`

## 鐵律

任何重大修改完成後，必須產生 **Repository Health Report**（見各 Skill checklist 與 HANDOFF.md）。
