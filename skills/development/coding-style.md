# Coding Style（編碼風格）

- Python：PEP 8，零依賴優先，類型提示可選
- 路徑計算用 `os.path.dirname(__file__)` 相對，不硬寫絕對路徑（除本機 DB 種子）
- HTML：語意化標籤，Web Components 優先
- CSS：Design Token（`var(--*)`），禁止硬寫核心樣式
- JS：原生 ES，Web Components，不依賴框架
- 註解：繁體中文，說明「為什麼」而非「做什麼」
- 最小變動：只改必要處，不順手重構
