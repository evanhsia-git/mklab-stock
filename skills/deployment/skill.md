---
name: deployment
title: mklab-stock Deployment
description: GitHub Pages 部署流程。透過 GitHub Actions 自動部署，無需本地 Node build。當用戶要求「部署/發布/上 GitHub Pages」時使用。
version: 1.0
---

# Deployment（部署）

本專案 GitHub Pages 原生部署，零 Node.js Build。

## 腳本

- `deploy.py` — 部署輔助（檢查 QA 通過、觸發說明）

## 流程

1. 資料更新：`skills/data/fetch_data.py`
2. 模板同步：`build/template_sync.py`
3. 品質門禁：`skills/qa-gate/qa_gate.py` → ALLOW DEPLOY
4. 推送 main → GitHub Actions 自動部署至 GitHub Pages
5. 手動項目（Chart/視覺）由 Agent 以瀏覽器確認

## 原則

- Fork First：clone 即跑
- 根目錄 HTML 即正式網站
- 不得依賴 Node.js Production Build
- 不得破壞 GitHub Pages / Fork First
