# mklab-stock QA Gate 報告
**時間**: 2026-07-20 12:01:01  
**Critical ERROR**: 0  | **WARNING**: 1  
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
| Data | 股票代號唯一 | PASS | 1789 檔唯一 |  |  |
| Data | 無髒值 (NaN/null/undefined/Infinity/空字串/非法'-') | WARNING | ?.capital_stock=None; ?.capital_stock=None; ?.capital_stock=None; ?.capital_stock=None; ?.capital_stock=None; ?.capital_ | 確認資料源是否涵蓋該標的 | /root/Documents/mklab-stock/data/stocks.json |
| Data | OHLC 合理性 (H>=L, H>=O, H>=C, L<=O, L<=C, P>0, V>=0, MktCap>0) | PASS | 1789 檔 OHLC 合理 |  |  |
| Data | 前日波動異常 (>20% 閾值) | PASS | 無異常波動 |  |  |
| JSON | stocks.json Schema | PASS | schema 完整 (1789 檔) |  |  |
| JSON | industry.json Schema | PASS | 33 個產業 |  |  |
| HTML | 結構健康檢查 | PASS | 全部 7 個 HTML 通過 |  |  |
| CSS | 統一 Theme 變數 (var(--bg) 等) | PASS | Theme CSS 關鍵設計令牌完整 |  |  |
| CSS | 禁止硬寫核心樣式 (違反 Design Token) | PASS | 無行內硬寫核心樣式 |  |  |
| JS | syntax: mklab-stock-screener.html#0 | PASS |  |  |  |
| JS | syntax: index.html#0 | PASS |  |  |  |
| JS | syntax: mklab-stock-research.html#0 | PASS |  |  |  |
| JS | syntax: mklab-stock-industry.html#0 | PASS |  |  |  |
| JS | syntax: mklab-stock-log.html#1 | PASS |  |  |  |
| JS | syntax: mklab-stock-help.html#0 | PASS |  |  |  |
| JS | syntax: mklab-stock-watchlist.html#0 | PASS |  |  |  |
| Chart | 圖表渲染: index.html | MANUAL | 需瀏覽器載入確認 Canvas/SVG 存在、Dataset 非空、無 Chart Error，並截圖 |  |  |
| Chart | 圖表渲染: mklab-stock-research.html | MANUAL | 需瀏覽器載入確認 Canvas/SVG 存在、Dataset 非空、無 Chart Error，並截圖 |  |  |
| Links | 內部連結 HTTP 200 (本地) | PASS | 全部內部連結可解析 |  |  |
| Visual | 視覺回歸比對 | MANUAL | 需瀏覽器截圖，與 Baseline 比較配色/字體/間距/版面/圖表，差異超閾值標記失敗 |  |  |

## 問題摘要
- **[WARNING] Data/無髒值 (NaN/null/undefined/Infinity/空字串/非法'-')**: ?.capital_stock=None; ?.capital_stock=None; ?.capital_stock=None; ?.capital_stock=None; ?.capital_stock=None; ?.capital_stock=None; ?.capital_stock=None; ?.capital_stock=None; ?.eps=None; ?.capital_stock=None
  - 建議: 確認資料源是否涵蓋該標的（/root/Documents/mklab-stock/data/stocks.json）

## 最終判定: ALLOW DEPLOY

> 除非所有 Critical 項目皆通過，否則一律 BLOCK DEPLOY。
> [MANUAL] 項目需 Agent 以瀏覽器工具實際載入頁面驗證（Chart/Console/視覺回歸），不計入自動阻擋，但須於部署前完成。