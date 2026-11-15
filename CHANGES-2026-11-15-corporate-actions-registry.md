# CHANGES 2026-11-15 — 公司行為登錄 21 筆＋減資還原公式＋偵測器缺陷修復

## 1. 偵測器缺陷（根因）

`min_gap_days` 用**日曆日**，週五→週一剛好 3 天就過關。槓桿／反向 ETF 單日 ±20~30% 是正常行情
（無漲跌幅限制），因此 29 檔候選中有 8 筆是純週末跳空（缺 0 個交易日）。

修法：用 `data/history/*.json` 檔名當交易日曆，`scan_for_discontinuity(trading_days=...)` 要求
「該標的真的沒交易的交易日 >= 2 天」（`MIN_MISSING_TRADING_DAYS`），並輸出 `halt_from`（第一個缺的交易日）
與 `missing_trading_days`。候選 29 → 21；登錄後 → 0。

## 2. 還原價支援反分割與減資

`ratio` 語意統一為**新股／舊股**（分割 7、反分割 0.25、減資 0.75）：

```
事件前價 = (前收 − cash_refund) ÷ ratio        # cash_refund 僅現金減資有
```

`cash_refund` ＝ 減資比率 × 面額 10 元。實測必要性：瑞儀 (81.3−2.5)÷0.75 = 105.07（不扣得 108.4）、
榮運 (35−5)÷0.5 = 60（不扣得 70）。新增欄位 `cash_refund`，並寫入 `stocks.json` 供前端標註。

## 3. 登錄 21 筆（registry 9 → 30 筆）

| 類型 | 檔數 | 代號 |
|------|------|------|
| split | 4 新增 | 2327 國巨 1拆4、6949 沛爾生醫 1拆20、7780 大研生醫 1拆10、8422 可寧衛 1拆10 |
| reverse_split | 4 | 00673R／00706L 0.25、00674R 0.2、00715L 0.5 |
| capital_reduction | 13 | 1516、2314、2321、2380、3057、3321、3593、6550（彌補虧損）；1563、2607、2832、6176、9927（現金減資） |

每筆都有官方來源（證交所新聞稿／MOPS 公告鏡像／公司公告）＋本站 K 線交叉驗證。
還原後 24 檔序列全部連續（邊界殘差 0~10%）。

## 4. 官方管道實測（重要）

- TWSE 143 ＋ TPEx 225 個 OpenAPI 端點**都沒有**分割／減資比率欄位 → 比率只能從公告頁面取得。
- 停牌區間：`TWTBAU1` 帶 `Reason="ETF分割"`（如 0053 `1151127~1151203`）；TPEx `tpex_spendi_history` 限當年度。
- 公告全文：`finance.biggo.com.tw/news/twse_major_*`（MOPS 鏡像）、goodinfo、money-link、Yahoo 股市新聞。
- 內建 web_search 後端在此環境回 0 筆 → 以 `html.duckduckgo.com/html/?q=` 結果頁替代檢索（實測可用）。

## 5. 前端

`mklab-stock-research.html` 標籤依類型分三種，線上實看：
`減資 25%（每股退還 2.5 元）`、`反分割 2:1`、`已分割 10:1`。

## 6. 驗證

- 測試：35（corporate_actions）＋56＋11＋16＋24 Python、145 known_errors、4 Node 全通過。
- QA Gate：ALLOW DEPLOY（三條公司行為規則全 PASS；候選 0）。
- CI：`30f0a6ee` qa-gate ✓、pages ✓；線上 `stocks.json` 1446 筆、24 檔有 `adj`、30 筆有 `corporate_action`。
- `stocks.json` 1,275.8 KB（上限 1,300 KB）。
