# mklab-stock QA Gate 報告
**時間**: 2026-07-17 05:43:05  
**Critical ERROR**: 0  | **WARNING**: 2  
**最終判定**: 🟢 ALLOW DEPLOY

| 類別 | 項目 | 狀態 | 說明 | 修正建議 | 位置 |
|------|------|------|------|----------|------|
| Python | syntax: fetch_data.py | PASS |  |  |  |
| Python | syntax: update_overview.py | PASS |  |  |  |
| Python | syntax: export_db.py | PASS |  |  |  |
| Python | syntax: check_html_health.py | PASS |  |  |  |
| Python | syntax: qa_gate.py | PASS |  |  |  |
| Python | import-ok: fetch_data.py | PASS |  |  |  |
| Python | import-ok: update_overview.py | PASS |  |  |  |
| Python | import-ok: export_db.py | PASS |  |  |  |
| Python | import-ok: check_html_health.py | PASS |  |  |  |
| Python | import-ok: qa_gate.py | PASS |  |  |  |
| Data | 股票代號唯一 | PASS | 1370 檔唯一 |  |  |
| Data | 無髒值 (NaN/null/undefined/Infinity/空字串/非法'-') | WARNING | 00408A.ind=null(無產業分類，ETF/海外股正常); 0050.market_cap=null(雲端未涵蓋); 0051.market_cap=null(雲端未涵蓋); 0052.market_cap=null(雲端未涵蓋); | 確認資料源 | /root/Documents/mklab-stock/data/stocks.json |
| Data | OHLC 合理性 (H>=L, H>=O, H>=C, L<=O, L<=C, P>0, V>=0, MktCap>0) | PASS | 1370 檔 OHLC 合理 |  |  |
| Data | 前日波動異常 (>20% 閾值) | PASS | 無異常波動 |  |  |
| Data | chg 單位合理性 (|chg|<=50 應為漲跌%) | PASS | chg 單位合理 |  |  |
| JSON | stocks.json Schema | PASS | schema 完整 (1370 檔) |  |  |
| JSON | industry.json Schema | PASS | 33 個產業 |  |  |
| HTML | 結構健康檢查 | PASS | 全部 7 個 HTML 通過結構檢測 |  |  |
| CSS | 統一 Theme 變數 (var(--bg) 等) | PASS | 所有頁面皆有引入 Theme |  |  |
| CSS | 禁止硬寫核心樣式 (違反 Design Token) | WARNING | 行內硬寫樣式: ['mklab-stock-research.html:1', 'mklab-stock-log.html:1', 'mklab-stock-watchlist.html:3'] | 改用 CSS class | mklab-stock-research.html:1, mklab-stock-log.html:1, mklab-stock-watchlist.html:3 |
| JS | syntax: mklab-stock-screener.html#0 | PASS |  |  |  |
| JS | syntax: index.html#0 | PASS |  |  |  |
| JS | syntax: mklab-stock-research.html#0 | PASS |  |  |  |
| JS | syntax: mklab-stock-industry.html#0 | PASS |  |  |  |
| JS | syntax: mklab-stock-log.html#0 | PASS |  |  |  |
| JS | syntax: mklab-stock-help.html#0 | PASS |  |  |  |
| JS | syntax: mklab-stock-watchlist.html#0 | PASS |  |  |  |
| Chart | 圖表渲染: index.html | MANUAL | 需瀏覽器/人工驗證 |  |  |
| Chart | 圖表渲染: mklab-stock-research.html | MANUAL | 需瀏覽器/人工驗證 |  |  |
| Links | 內部連結 HTTP 200 (本地) | PASS | 內部連結正常 |  |  |
| Visual | 視覺回歸比對 | MANUAL | 需瀏覽器/人工驗證 |  |  |

## 問題摘要
- **[WARNING] Data/無髒值 (NaN/null/undefined/Infinity/空字串/非法'-')**: 00408A.ind=null(無產業分類，ETF/海外股正常); 0050.market_cap=null(雲端未涵蓋); 0051.market_cap=null(雲端未涵蓋); 0052.market_cap=null(雲端未涵蓋); 0053.market_cap=null(雲端未涵蓋); 0055.market_cap=null(雲端未涵蓋); 0056.market_cap=null(雲端未涵蓋); 0057.market_cap=null(雲端未涵蓋)（非阻擋）
  - 建議: 確認資料源 (/root/Documents/mklab-stock/data/stocks.json)
- **[WARNING] CSS/禁止硬寫核心樣式 (違反 Design Token)**: 行內硬寫樣式: ['mklab-stock-research.html:1', 'mklab-stock-log.html:1', 'mklab-stock-watchlist.html:3']
  - 建議: 改用 CSS class (mklab-stock-research.html:1, mklab-stock-log.html:1, mklab-stock-watchlist.html:3)

## 最終判定: ALLOW DEPLOY

> 除非所有 Critical 項目皆通過，否則一律 BLOCK DEPLOY。