# GitHub Pages 部署說明

## 架構

- 來源：GitHub 倉庫 `main` 分支根目錄 HTML
- 部署：GitHub Actions（`.github/workflows/daily-update.yml` 等）自動 build + 部署
- 靜態托管：GitHub Pages（Settings → Pages → Source: GitHub Actions）

## Workflow 職責

- `daily-update.yml`：定時抓資料 → 更新 data/ → 提交
- `qa-gate.yml`：push/PR 時跑 `skills/qa-gate/qa_gate.py`
- `html-health.yml`：push/PR 時跑 `skills/html-health/check_html_health.py`

## 注意

- 無 Node.js Build 步驟
- `build/template_sync.py` 僅同步共用區塊，非產生整站
- 根目錄 HTML 為唯一正式來源
