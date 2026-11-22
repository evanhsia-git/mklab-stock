# ETF SOURCE REGISTRY

## 資料來源登錄表

| 資料模組 | 資料類型 | 原始網址 | 更新日期 | 取得時間 | 品質等級 | 驗證狀態 |
|----------|----------|----------|---------|----------|---------|---------|
| **TWSE ETF 基本面** | TWSE 投資篩選器 CSV (CP950) | https://wwwc.twse.com.tw/zh/ETFortune/etfExcel?rangeTotalAv=1&... | 2026-11-03 | 自動抓取 | ⭐⭐⭐ | 需驗證 |
| **TPEx ETF 基本面** | TPEx API (JSON) | https://info.tpex.org.tw/api/etfFilter | 2026-11-03 | 自動抓取 | ⭐⭐ | 缺 close |
| **ETF 成份股** | 投信官方持股頁 (HTML/JS) | https://www.fsit.com.tw/FubonETF/Fund/Assets.aspx?stkId=<code> | 手動下載 | 2026-11-15 | ⭐⭐⭐ | 前 10 大僅 |
| **ETF 費用** | AUM 階梯試算 (內部算法) | data/stocks.json | 2026-11-17 | 自動產出 | ⭐ | ❌ 未驗證 |
| **ETF 價格** | TWSE/TPEx 即時報價 | TWSE: https://iftp.twse.com.tw/... ; MoneyDJ: https://www.moneydj.com/ETF/X/Basic/... | 當日 | 當日 | ⭐⭐⭐ | 需驗證 |
| **發行商** | 各投信官方網站 | 見 `references/issuer-sources.md` | 手動登錄 | 手動 | ⭐⭐⭐ | 需統一別名 |

### 來源優先順序（依 `taiwan-etf-holdings` SKILL.md）

1. **官方可直出**：富邦投信 (`websys.fsit.com.tw`), 元大投信 (`yuantaetfs.com/product/detail/<code>/ratio`)
2. **CMoney 備援**：`https://www.cmoney.tw/etf/tw/<代號>` — Nuxt SSR，前 10 大持股
3. **yfinance**：`yf.Ticker(code+'.TW').funds_data.top_holdings` — 股票型/主動式交叉驗證
4. **TPEx OpenAPI**：`https://info.tpex.org.tw/api/etfFilter`
5. **手動 CSV 備援**：`data/raw/*.csv`

### 已實測可用 URL 樣式

| 投信 | URL 樣式 | 取到什麼 |
|------|----------|---------|
| 富邦投信 | `https://websys.fsit.com.tw/FubonETF/Fund/Assets.aspx?stkId=<code>` | 完整清單 + 股數/金額/權重(%) |
| 元大投信 | `https://www.yuantaetfs.com/product/detail/<code>/ratio` | Vue SSR HTML（前 5 檔），完整清單需 PCF 下載 |
| 凱基投信 | `kgifund.com.tw/Fund/Detail?fundID=...` | HTML 部分代號 |
| 中信投信 | `ctbcinvestments.com` (SPA, XHR) | 需瀏覽器抓取 network |
| 貝萊德投信 | `blackrock.com` → 403 (Akamai) | 手動上傳或第三方 |
| 國泰投信 | `united.com.tw/ETFlandingpage` | 需瀏覽器 |

---

## 統一發行商別名對照表

| 原始名稱 | 標準別名 |
|----------|----------|
| 富邦證券投資信託股份有限公司 | 富邦投信 |
| 元大證券投資信託股份有限公司 | 元大投信 |
| 國泰證券投資信託股份有限公司 | 國泰投信 |
| 中國信託證券投資信託股份有限公司 | 中信投信 |
| 群益證券投資信託股份有限公司 | 群益投信 |
| 復華證券投資信託股份有限公司 | 復華投信 |
| 台新證券投資信託股份有限公司 | 台新投信 |
| 凱基證券投資信託股份有限公司 | 凱基投信 |
| 永豐證券投資信託股份有限公司 | 永豐投信 |
| 統一證券投資信託股份有限公司 | 統一投信 |
| 安聯證券投資信託股份有限公司 | 安聯投信 |
| 玉山證券投資信託股份有限公司 | 玉山投信 |
| 第一金證券投資信託股份有限公司 | 第一金投信 |
| 大華銀投信 | 大華銀投信 |
| 聯博證券投資信託股份有限公司 | 聯博投信 |
| 摩根證券投資信託股份有限公司 | 摩根投信 |
| 華南永昌證券投資信託股份有限公司 | 華南永昌投信 |
| 街口證券投資信託股份有限公司 | 街口投信 |
| 聯邦證券投資信託股份有限公司 | 聯邦投信 |
| 華南永昌投信 | 華南永昌投信 |
| 野村投信 | 野村投信 |
| 富蘭克林華美 | 富蘭克林華美投信 |
| 兆豐國際證券投資信託股份有限公司 | 兆豐國際投信 |
| 貝萊德投信 | 貝萊德投信 |
| 街口/聯邦/華南永昌等 | 1 筆 each |

---

*報告結束*
