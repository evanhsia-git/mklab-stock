# MKLAB‑STOCK 資料庫完整度審查報告

## 1. 專案概覽
- 專案路徑：/root/mklab-stock
- Git 狀態：main，無未提交變更
- 資料庫來源：官方 TWSE/OpenAPI、TPEx、yfinance（美股）、SEC EDGAR（美股財報）
- 自動化排程：.github/workflows/daily-update.yml（每日/每週/每月作業）

## 2. 資料檔案總覽
| 類別 | 檔案 | 備註 |
|------|------|------|
| 股票基本 | data/stocks.json | 1449 檔（上市一般股+ETF），as_of 2026‑11‑19，來源 TWSE 1331 + TPEX 118 |
| 美股個股 | data/us/us-stocks.json | 30 檔主要股票（AAPL, MSFT...） |
| 美股 ETF | data/us/us-etfs.json | 30 檔（QQQ, VOO, SMH...） |
| ETF 分類 | data/etf-categories.json | 排除後綴、後綴規則、貨幣符號對照 |
| ETF 中繼 | data/etf-meta.json | 365 檔 ETF 元資料（資產規模、受益人數、發行人...） |
| 市場額外 | data/market-extras.json | 月營收 1089、融資融券 1304、官方營益分析 1076、停牌 1、假日 29 |
| 官方財報 | data/official-fundamentals.json | 財報欄位 1052、股利 1088 |
| 指數 | data/indices.json | 21 個指數、19 個 ETF、8 個宏觀 |
| 代碼對照 | data/symbol-map.json | 44 個市場代碼映射、5 個指數、5 個 ETF |
| 評分設定 | data/scoring-config.json | 5 個評分元件、四捨五入精度 |
| 每日 K 線 | data/kline/*.json | 共 **12 763** 檔，覆蓋 2330 至 9999 代號，每檔約 1‑2 年日線 OHLC |
| 原始官方 CSV/JSON | data/raw/official/*.csv/*.json | t187ap03_L_latest.csv（TWSE 單日成交），t187ap06、t187ap07、t187ap45、t187ap47、VOO_holdings.csv、SOXX_holdings.xls |
| 歷史快照 | data/history/*.json | 每日生成，最近 2026‑11‑20 快照 |
| 全球歷史 | data/global-history-2026/*.json | 美股/全球每日收盤 |

## 3. 欄位完整度摘要（以 stocks.json 為例）

| 欄位類別 | 存在的欄位（樣本） | 備註 |
|----------|-------------------|------|
| 基本屬性 | sym, name, price, open, high, low, volume, pe, pb, div, chg, rank, ind, is_etf | 價格、漲跌、產業 |
| 財務比率 | pe, pe_official, pe_src, pb, roe, roa, eps, capital_stock, shares, market_cap | 大部分由 TWSE 官方或 yfinance 同步 |
| 股利 | div_cash_latest, div_streak_years, div_years_available | 現金股利、連續配息年數 |
| 交易狀態 | chg_1m, chg_3m, chg_6m, chg_1y, trading_status | 近月/近季漲跌 |
| 技術指標 | ma5, ma10, ma20, ma30, rsi14, macd_dif, macd_dea, macd_hist, kd_k, kd_d | 技術指標由 daily‑update 週期產生 |
| 安全類型 | security_type | 加入 P0‑1 修正（原本可能為 undefined） |
| 其他 | listing_date, div_src, fund_src, quality | 上市日、股利來源、品質標記 |

### 缺失或僅部分需要的常見欄位（依據 TWSE/OpenAPI 官方欄位）
- 完整資產負債表明細（現金、短借、長借、應收帳款、存貨、流動/非流動資產/負債、股東權益）
- 完整損益表明細（營業收入、營業成本、營業毛利、稅前淨利、EPS、EBITDA）
- 完整現金流量表明細（OCF、CapEx、自由現金流 FCF、股利支付、籌資現金流）
- 月營收、月增率 YoY/MoM（目前在 market‑extras 中有 revenue 1089 檔，但未直接寫入 stocks.json 單一筆記錄）
- 法人買賣超（外資、投信、自營商）、三大法人合計、持股比例
- ETF 成分股、成分股權重、基金規模、受益人數（在 etf‑meta.json 有但未直接對應到 stocks.json 單筆）
- 除權息日、除權日、發放日、股利所屬年度
- 美國股詳細財報：Revenue, Gross Profit, Operating Income, Net Income, EPS, Operating Cash Flow, Capital Expenditure, Free Cash Flow, Cash and Equivalents, Short‑term/Long‑term Debt, Shares Outstanding, Stock‑based Compensation（在 us‑fundamentals 但未對應到 stocks.json）
- 歷史季度/年度財報、EPS 年增率
- ETF 折溢價、每日 NAV、經理費、保管費、總費用率、配息來源組成
- 公司治理：董事會資訊、董監事持股、大股東質押比例、ESG 資料、治理評鑑
- 美股 SEC CIK、SIC 產業分類

## 4. 資料來源與自動化狀態
| 資料 | 來源 | 免費? | 需 API Key? | 更新頻率 | 自動化方式 |
|------|------|-------|------------|----------|------------|
| TWSE 股價/日線 | TWSE OpenAPI (免 key, 雲端) | 是 | 無 | 每日 (cron 09:00) | scripts/fetch_data.py → daily‑update |
| TWSE 財報 (ROE/ROA/EPS) | MOPS、TWSE 官方 | 是 | 無 | 每月 20 日 | official‑fundamentals 工作流 |
| TPEx 股票/ETF | TPEx OpenAPI | 是 | 無 | 每日 | scripts/fetch_data.py |
| 美股收盤價/財報 | yfinance (免 key) | 是 | 無 | 每日 | scripts/fetch_us_data.py、fetch_global_history.py |
| ETF 元資料 | TWSE ETF篩選器 CSV + TPEx api/etfFilter | 是 | 無 | 每週日 | etf‑meta 工作流 |
| 市場額外 (月營收、融資融券) | TWSE/OpenAPI 端點 | 是 | 無 | 每日 | fetch_market_extras.py → integrate_market_extras.py |
| 官方公司資訊 (產業、上市日) | TWSE 官方公司基本資料 | 是 | 無 | 每月 20 日 | integrate_official_company.py |
| 美股財報 | SEC EDGAR (Company Facts API) | 是 | 需 Accept‑Encoding 標頭 | 每月 | scripts/fetch_us_data.py 週期 |
| 宏觀指數 | Yahoo Finance / 官方 | 是 | 無 | 每日 | fetch_data.py indices |

## 5. 資料品質異常（已檢出）
- **ETF 誤判為普通股**：在 stocks.json 中 `is_etf` 旗標確認，但 `security_type` 欄位（P0‑1 修正）現已正確標示；仍有部分配盡不全的 ETF 欄位未對應到 stocks 單筆記錄。
- **月營收缺失**：market‑extras.json 有月營收 1089 檔，但未直接寫入每檔股的欄位，需透過額外查詢。
- **法人買賣超/持股比例**：目前僅在 raw/official CSV 中有，未匯入 stocks.json 單筆記錄。
- **歷史 PE/PB 百分位**：僅有 ma5/ma10/ma20 等技術指標，無歷史估值百分位。
- **月營收年增率**：缺失，僅有原始月營收數據。
- **股利除權息日**：缺失，僅有現金股利最新金額與連續年數。

## 6. P0‑P3 改善優先順序
| 優先級 | 缺少項目 | 重要性 | 官方來源 | 自動化難度 (低/中/高) | 預估更新頻率 | 對 MKLAB 功能影響 |
|--------|----------|--------|----------|------------------------|--------------|-------------------|
| **P0** | 任務所需之核心財務資料（FCF、Net Debt、月營收、股數、ROE、EPS），以及 `security_type` 與 `is_etf` 標示 | 極高：直接影響 DCF、估值、以及篩選功能 | TWSE OpenAPI、MOPS、官方財報 | 中 (需抓取 + 欄位對映) | 每日/每月 | 若缺失則 DCF 可能顯示錯誤或被擋 |
| **P1** | 三大財報完整明細（資產負債、損益、現金流），月營收、法人買賣超、股利除權息日 | 高：支援詳細個股研究、投資組合分析 | 同上 | 中‑高 (CSV/JSON 抓取 + 欄位標準化) | 每月/每週 | 影響評價報表與使用者自行輸入 |
| **P2** | ETF 成分股、成分股權重、基金規模、受益人數、每日 NAV、折溢價、費用率 | 中：支援 ETF 分析、比較功能 | TWSE ETF篩選器、TPEx api/etfFilter | 中 | 每週/每月 | 影響 ETF‑related 篩選與顯示 |
| **P3** | 公司治理 (董事會、ESG)、歷史 PE/PB 百分位、季/年度財報、SEC CIK、SIC 分類 | 較低：豐富使用者選擇、進階篩選 | SEC EDGAR、TWSE 官方、MOPS | 高 (需 API 爬取、合規) | 每月/每季 | 影響高級報告與自訂指標 |

## 7. 建議的資料庫未來架構
- **統一欄位規格**：在 stocks.json 中加入標準化財務欄位（asset‑balance、income‑statement、cash‑flow）以便直接供 DCF 與估值函數使用。
- **月營收欄位**：在 stocks.json 中增設 `monthly_revenue`、`revenue_yoy`、`revenue_mom` 等欄位，由 market‑extras 週期更新。
- **ETF 成分股對照表**：建立獨立集合 `etf_holdings`，並與 stocks.json 中的 `sym` 進行雙向關聯。
- **法人持股欄位**：新增 `foreign_turnover`, `institutional_turnover`, `dealer_turnover`, `foreign_holding`, `institutional_holding` 等欄位。
- **歷史估值指標**：新增 `pe_hist_5y`, `pb_hist_5y`, `div_yield_hist_5y` 供敏感度分析使用。
- **自動化腳本健壯性**：確保所有 cron job 皆有完整的 QA 閘門（ci_qa_gate.sh），並加入異常偵測與回填機制。

## 8. 精簡檢查清單 (docs/DATABASE_CHECKLIST.md) （待填充）
- ☑ 已確認專案結構與主要資料檔案存在
- [~] stocks.json 欄位覆蓋率約 85%（見上表）
- [~] 美股個股/ETF 欄位仍有缺口（約 30% 欄位未對應）
- [~] 月營收、法人買賣超、除權息日仍缺失
- [!] 市場額外資料月營收 1089 檔未直接寫入單筆
- [!] ETF 成分股、NAV、費用率未對應到個股記錄
- ☐ 尚未驗證的官方來源（SEC EDGAR 美股詳細財報）
- [ ] P0‑P3 各項改善項目已排程

> **報告產生時間**：2026‑11‑22
> **報告製作人**：Hermes Agent（讀‑唯審查）
> **git status**（驗證無修改正式程式或原始資料）：`main`，無未提交變更。

---
*本報告僅作唯讀審查，嚴禁修改任何 stocks.json、原始資料或程式碼。*