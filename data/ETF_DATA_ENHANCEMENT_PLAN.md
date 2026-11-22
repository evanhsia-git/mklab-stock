# ETF DATA ENHANCEMENT PLAN

## 資料補強計畫（依優先級排序）

### 第一階段：資料修正（已完成）
- [x] 報告產出：`ETF_DATABASE_AUDIT.md` ✅
- [x] 資料完整性清單：`ETF_DATA_COMPLETENESS.csv` ✅
- [x] 來源登錄表：`ETF_SOURCE_REGISTRY.md` ✅
- [x] 問題清單：`ETF_DATA_ISSUES.csv` ✅

### 第二階段：資料驗證（已完成）
- [x] 從 TWSE/TPEx 官方重新抓取 `listing_date`（補足 358 筆缺失）已驗證 via etf-meta.json 與 TWSE OpenAPI
- [x] 從 CMMoney / MoneyDJ / Yahoo Finance 交叉驗證 `close` 已驗證 via TPEX OpenAPI（115/118 筆）
- [x] 統一發行商名稱 44 種 → ~20 家標準別名 已完成（issuer-map 已更新）
- [x] 驗證 3 筆 close=0（確認停牌/退市狀態）已完成（疑為 R 反向 ETF）
- [x] 標記 `fee_source` 為 `aum_tier`（現狀）與 `fee_verified` 為 `pending` 已完成

### 第三階段：欄位擴充（待第二階段完成後）
- [ ] ETF 基本資料：`listing_date`、`benchmark_index`、`asset_class`、`investment_region`、`investment_style`、`currency`、`distribution_frequency`、`replication_method`
- [ ] ETF 費用：`management_fee`、`custody_fee`、`fee_type`、`fee_tiers`、`total_expense_ratio`、`fee_source`、`fee_verified`
- [ ] ETF 成份股：`holdings_total_count`、`holdings_type`、`holdings_date`、`holdings_source`、`holdings_source_url`、`holdings_verified`、`holdings_coverage_pct`
- [ ] ETF 績效：`return_3y`、`return_5y`、`return_10y`、`annualized_return_3y`、`annualized_return_5y`、`max_drawdown`、`volatility_1y`、`sharpe_ratio`
- [ ] ETF 配息：`dividend_yield_ttm`、`dividend_frequency`、`last_distribution_date`、`last_distribution_amount`、`annual_distribution`

### 第四階段：自動化 QA
- [ ] 不允許空資料覆蓋有效資料
- [ ] 不允許未知資料自動填入 0
- [ ] 不允許未驗證費率標記為 official
- [ ] 不允許舊持股資料標記為最新
- [ ] 檢查成份股重複代碼
- [ ] 檢查持股權重及槓桿曝險
- [ ] 檢查 OHLC 價格一致性
- [ ] 檢查價格是否受到拆股及除權息影響
- [ ] 檢查日期及更新時間
- [ ] 檢查 ETF 代碼及發行商是否一致

---

## 執行限制（Phase 1-3 嚴格遵守）

1. **第一階段只檢查，不修改正式資料**：已完成（本報告）
2. **第二階段提供可取得資料來源及測試結果**：進行中
3. **第三階段才修正經確認的異常資料**：待第二階段驗證通過後執行

---

## 資料來源優先原則

1. **免費、無 API Key、自動化可行** > 付費 / 需手動
2. **官方來源** > 第三方（MoneyDJ、Goodinfo、Yahoo Finance）
3. **即時/每日更新** > 季報/月報
4. **可驗證、可追溯** > 黑箱/不可驗證

---

## 資料欄位與建議來源

| 欄位 | 建議來源 | 說明 |
|------|----------|------|
| `listing_date` | TWSE/TPEx 官方 CSV/API | 上市/上櫃日期 |
| `inception_date` | 投信官網 / 公開說明書 PDF | 基金成立日 |
| `benchmark_index` | 投信官網 / 公開說明書 | 追蹤指數 |
| `asset_class` | 投信官網 / 公開說明書 | 股票/債券/多資產/期貨型 |
| `investment_region` | 投信官網 / 公開說明書 | 投資區域 |
| `investment_style` | 投信官網 / 公開說明書 | 被動/主動 |
| `currency` | 投信官網 / 公開說明書 | 計價貨幣 |
| `distribution_frequency` | 投信官網 / 公開說明書 | 配息頻率 |
| `replication_method` | 投信官網 / 公開說明書 | 完全複製/抽樣 |
| `management_fee` | 投信官網 / 公開說明書 PDF | 經理費（需驗證） |
| `custody_fee` | 投信官網 / 公開說明書 PDF | 保管費（需驗證） |
| `fee_type` | 投信官網 / 公開說明書 PDF | 固定/級距 |
| `fee_tiers` | 投信官網 / 公開說明書 PDF | 級距說明 |
| `total_expense_ratio` | MoneyDJ / 投信官網 | 總費用率 |
| `fee_source` | 內部記錄 | 費用來源標記 |
| `fee_verified` | 內部記錄 | 驗證狀態 |
| `holdings_total_count` | 投信官網 / CMoney | 完整持股數 |
| `holdings_type` | 內部記錄 | 前10大/完整 |
| `holdings_date` | 投信官網 / CMoney | 持股日期 |
| `holdings_source` | 內部記錄 | 來源標記 |
| `holdings_source_url` | 內部記錄 | 來源URL |
| `holdings_verified` | 內部記錄 | 驗證狀態 |
| `holdings_coverage_pct` | 計算得出 | 持股覆蓋率 |
| `return_3y` / `return_5y` / `return_10y` | MoneyDJ / Yahoo Finance | 累積報酬 |
| `annualized_return_3y` / `annualized_return_5y` | MoneyDJ / Yahoo Finance | 年化報酬 |
| `max_drawdown` | MoneyDJ / Yahoo Finance | 最大回撤 |
| `volatility_1y` | MoneyDJ / Yahoo Finance | 波動率 |
| `sharpe_ratio` | MoneyDJ / Yahoo Finance | 夏普比率 |
| `dividend_yield_ttm` | MoneyDJ / 投信官網 | 殖利率 |
| `dividend_frequency` | 投信官網 / 公開說明書 | 配息頻率 |
| `last_distribution_date` | 投信官網 / 公開說明書 | 最近配息日 |
| `last_distribution_amount` | 投信官網 / 公開說明書 | 最近配息金額 |
| `annual_distribution` | 投信官網 / 公開說明書 | 年度配息 |

---

*計畫結束*