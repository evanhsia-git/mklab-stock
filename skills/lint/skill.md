---
name: lint
title: mklab-stock Lint 規則
description: 程式碼與結構 Lint 規範。檢查 Python 風格、HTML 結構、CSS Design Token 遵循、禁止過度工程化。當用戶要求「lint/程式碼風格/結構檢查」時使用。
version: 1.0
---

# Lint（程式碼/結構規範）

本 Skill 定義 mklab-stock 的 Lint 規則。可執行 `lint.py` 進行基礎檢查。

## 腳本

- `lint.py` — 基礎 Linter（Python 語法 + 禁止 Node build + 檔案結構檢查）

## 執行

```bash
python3 skills/lint/lint.py
```

## 核心規則

- 禁止 Node.js Production Build
- 禁止建立 `pages/`、`config/`、`components/`、`src/`、`tests/`、`tools/`
- Python 僅作輔助（資料/QA/同步），不當網站框架
- CSS 必須使用 Design Token（`var(--bg)` 等），禁止硬寫核心樣式
- 最少重複程式碼、最少資料夾
- 每個 Skill 自包含，不拆散
