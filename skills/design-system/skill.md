---
name: design-system
title: mklab-stock Design System
description: UI/Theme 規範。定義 Design Token、顏色語意（紅=漲/綠=跌）、字體、間距、Dark/Light 模式。當用戶調整顏色/字體/版面/元件樣式時使用。
version: 1.0
---

# Design System（設計系統）

## 核心原則

- **Design Token 優先**：所有顏色/間距用 `var(--*)`，禁止硬寫
- **漲跌語意**：紅色 = 上漲，綠色 = 下跌（台股慣例）
- **Dark / Light 雙模式**：由 `data-theme` 切換
- **Web Components 相容**：樣式不依賴特定框架
- **GrapesJS 相容**：輸出標準 HTML/CSS

## 顏色 Token（見 theme.json）

- `--up`：上漲紅（`#f87171` dark / `#dc2626` light）
- `--down`：下跌綠（`#4ade80` dark / `#16a34a` light）
- `--bg` / `--fg` / `--card` / `--muted` 等

## 漲跌幅顯示規則

卡片漲跌使用 `.card-val.up` / `.card-val.down`、`.card-sub.up` / `.card-sub.down` 套用紅綠。
