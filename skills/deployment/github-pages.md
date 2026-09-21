# GitHub Pages 部署說明

## 架構

- 來源：GitHub 倉庫 `main` 分支根目錄 HTML
- 部署：GitHub Pages 監看 `main` 分支變動，自動發布，repo 內無自訂部署腳本（Settings → Pages → Source: Deploy from a branch）

## Workflow 職責

- `daily-update.yml`：定時抓資料 → 更新 data/ → 提交（提交本身就會觸發 GitHub Pages 重新發布）
- `qa-gate.yml`：push/PR 時跑 `skills/qa-gate/qa_gate.py`（內含呼叫 `skills/html-health/check_html_health.py` 做 HTML 結構檢查）

## 注意

- 無 Node.js Build 步驟
- 根目錄 HTML 為唯一正式來源，每頁共用的導覽列/抽屜由 `assets/js/mklab-core.js` 在瀏覽器端注入，不需要建置期同步腳本
