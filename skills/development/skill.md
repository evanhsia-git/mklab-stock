---
name: development
title: mklab-stock Development
description: 開發輔助與編碼風格。新功能優先建立 Skill，Minimal Changes，不過度工程化。當用戶要求「新功能/重構/編碼風格」時使用。
version: 1.0
---

# Development（開發原則）

## 最高原則

- **優先建立 Skill**：不要先建立散落 Script
- **Minimal Changes**：禁止無關重構、大量重新命名、過度拆分
- **不過度工程化**：最少資料夾、最少重複程式碼
- **Long-term Maintainable**：AI Agent 易理解
- **保持向下相容**：不破壞 GitHub Pages / Fork First / Web Components / GrapesJS

## 新功能流程

1. 判斷是否可重複利用的 Skill
2. 是 → 建立 `skills/xxx/`（skill.md + Python + checklist + config 同資料夾）
3. 否 → 放入最相關的現有 Skill
4. 修改根目錄 HTML（唯一來源）
5. 跑 `build/template_sync.py` 同步共用區塊
6. 跑 QA（qa-gate / html-health / lint）
7. 產生 Repository Health Report

## 禁止

- 建立 `pages/`、`config/`、`components/`、`src/`、`tests/`、`tools/`
- Node.js Production Build
- 改變網站 UI / Design System（除非明確要求）
- 任意修改 JSON Schema / API
