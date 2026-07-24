# QA Gate Checklist

執行 `python3 skills/qa-gate/qa_gate.py` 後，逐項確認：

- [ ] Python syntax / import 全部 PASS
- [ ] 股票資料：代號唯一、OHLC 合理、無 NaN/Inf
- [ ] JSON Schema 完整（stocks/industry）
- [ ] HTML 結構健康（7 頁全過）
- [ ] CSS Theme 變數一致、無硬寫核心樣式
- [ ] JS 語法 0 錯誤
- [ ] 內部連結可解析（本地檔案存在）、無 404
- [ ] Chart（手動）：canvas 存在、dataset 非空、無 console error
- [ ] 視覺回歸（手動）：截圖與 Baseline 比對無重大差異
- [ ] 最終判定 = **ALLOW DEPLOY**（0 Critical）

若有 ERROR：停止 Push，回報 `data/qa-report.md` 問題摘要與修正檔案位置。
