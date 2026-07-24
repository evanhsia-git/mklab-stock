# Lint Checklist

- [ ] 無 Node.js build 依賴
- [ ] 無 `pages/` `config/` `components/` `src/` `tests/` `tools/` 目錄
- [ ] Python 腳本 `python -m py_compile` 0 錯誤
- [ ] CSS 使用 `var(--*)` Design Token，無硬寫核心樣式
- [ ] 根目錄 HTML 為唯一來源，無第二份頁面
- [ ] 所有 Python 位於對應 `skills/<name>/` 內（無散落 `scripts/`）
- [ ] 無重複 JSON（config 與 data 不重疊）
- [ ] vendor/ 無重複第三方庫
