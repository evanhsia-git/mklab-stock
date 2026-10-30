#!/usr/bin/env bash
# 在 repo 根目錄執行：刪除已確認無用的檔案與 18 個無效歷史快照
set -e
rm -f assets/js/mklab-wc.js vendor/lightweight-charts.min.js data/stocks.json.bak2
rm -f skills/deployment/deploy.py skills/development/helper.py skills/qa-gate/validate_data.py
rm -f skills/data/probe_twse_openapi.py data/qa-report.md
rm -f FIX-REPORT-2026-09-29.md FIX-REPORT-2026-09-30.md INDICATORS-REPORT-2026-09-25.md NEXT-PHASE-ROADMAP-2026-09-26.md PHASE3-FIX-REPORT-2026-09-24.md
for d in 20250929 20251006 20251010 20251024 20251225 20260101 20260212 20260213 20260216 20260217 20260218 20260219 20260220 20260227 20260403 20260406 20260501 20260619; do rm -f data/history/$d.json; done
echo "清理完成"
