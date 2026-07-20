---
name: html-health
title: mklab-stock HTML 結構健康檢查
description: 在 push/CI 階段攔截「HTML 結構破壞導致網頁空白」的問題。檢查 style/head/body/script 配對、關鍵區塊存在。當用戶報告「頁面空白/結構異常」或部署前結構確認時使用。
version: 1.0
---

# HTML Health（結構健康檢查）

目的：攔截 HTML 結構破壞導致網頁空白的問題。
經典案例：缺 `</style>` → parser 把整個 `<body>` 當成 CSS → 頁面空白。

## 腳本位置（自包含）

- `check_html_health.py` — 結構檢查器

## 執行方式

```bash
python3 skills/html-health/check_html_health.py          # 檢查根目錄 *.html
python3 skills/html-health/check_html_health.py <file>   # 檢查單檔
# 退出碼：0 = 全部健康，1 = 有失敗
```

## 檢查項目

1. `<style>` / `</style>` 配對（未關閉會吞掉 body）
2. `<head>` / `</head>` 配對
3. `<body>` / `</body>` 配對
4. `<script>` / `</script>` 配對
5. 解析後 `<body>` 必須有子元素
6. `<style>` 必須在 `<body>` 之前關閉
7. 關鍵區塊存在（nav / utilbar / drawer / 至少一個 table 或 section 或 mklab-*）

## 與 qa-gate 的關係

`qa_gate.py` 已內嵌本檢查邏輯；本 Skill 提供獨立執行版本。
