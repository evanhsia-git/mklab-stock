# ETF 補充資料改為「官方自動化抓取」— 2026-11-15

## 一、問題

`data/etf-meta.json`（ETF **資產規模、受益人數、發行人、標的指數、掛牌日**）
長期停在 **2026-11-02**，因為它是**半自動**流程：

1. 人工到 TWSE／TPEx 的「ETF 投資篩選器」各按一次 CSV 下載
2. 存成 `data/raw/twse_etf.csv`、`data/raw/tpex_etf.csv`
3. 手動執行 `parse_etf_meta.py`

**沒有任何 workflow 會跑它**。`parse_etf_meta.py` 檔頭記載不自動化的理由：
「兩個頁面的表格是瀏覽器端 JS 動態載入，沒有找到穩定、允許程式化存取的公開 API」。

## 二、新發現：兩個端點其實都可程式化取得

Ivan 提供來源後實測：

| 市場 | 端點 | 實測結果 |
|---|---|---|
| TWSE | `https://wwwc.twse.com.tw/zh/ETFortune/etfExcel?...`（篩選頁的 CSV 匯出） | HTTP 307→200、`text/csv;charset=ms950`、約 248 列 |
| TPEx | `https://info.tpex.org.tw/api/etfFilter`（**篩選頁背後的資料 API**） | HTTP 200、`application/json`、118 檔 |

TPEx 那頁的「下載」是瀏覽器即時產生的 `blob:`（無法直接抓），真正資料源是 `api/etfFilter`
（從頁面的 resource 清單挖出來）。兩個端點的欄位與人工匯出的 CSV 完全對應。

## 三、決策（Ivan 2026-11-15）

> 以官方自動化獲取為原則，獲取失敗再由人工提供資料備援。

## 四、實作

新增 `skills/data/fetch_etf_meta.py`：

- **TWSE**：抓官方 CSV → 覆寫 `data/raw/twse_etf.csv`（同時更新人工備援檔）→
  呼叫**既有的** `parse_etf_meta.parse_twse()` 解析（單一解析來源，不另寫一份 parser）
- **TPEx**：抓 `api/etfFilter` JSON → `parse_tpex_json()` 轉成相同記錄格式
- **備援鏈**：TWSE 失敗→人工 CSV；TPEx 失敗→人工 CSV→上次 `etf-meta.json` 的 TPEx 資料
- **記錄來源**：`meta.provenance` 標示每個市場是 `auto`／`manual`／`previous`
- 防呆：TWSE 回應不含表頭關鍵字（`受益人數`）→ 視為失敗，不把錯誤頁存成 CSV

排程（`.github/workflows/daily-update.yml` 新增 `etf-meta` job，**每週日 18:00**）：

```
fetch_etf_meta.py  →  classify_etf.py  →  compute_indicators.py  →  QA gate  →  push
```

`classify_etf.py` 一併接上：它讀 `etf-meta.json` 產生 `etf-classified.json`，
但**原本沒有任何 workflow 會呼叫它**（`etf-classified.json` 也停在 2026-11-02）。

## 五、實作中發現並修掉的問題

### 1. 逐市場護欄（第一版漏洞）

第一版護欄只比對**總檔數**。若「TWSE 全掛、TPEx 正常」，總數變化不大就會通過，
寫出一份 **TWSE 空掉**的 `etf-meta.json`（前端整批少掉上市 ETF）。
已改為逐市場比對：任一市場的新檔數 < 上次的 80% 即中止不覆寫。

### 2. TPEx 的 `rorYTD` 是數字不是字串

第一版把每個欄位都丟給 `parse_etf_meta._num()`（內部做 `raw.strip()`），
遇到 `rorYTD: 0`（int）就爆 `'int' object has no attribute 'strip'`，TPEx 自動抓取整批失敗
（備援正確接手，所以只看到 warning）。已加型別安全的 `_n()`／`_s()`。

### 3. 新上市 ETF 停在 `unverified`（連帶發現）

刷新 `etf-meta.json` 後，`test_known_errors` 立刻抓到
`00413A 主動玉山關鍵科技`、`00418A 主動復華台灣新星` 兩檔在 `stocks.json` 是
`security_type=unverified`、`is_etf=false` —— 因為 `classify_etf.py` 從未被排程執行，
`etf-classified.json` 停在 2026-11-02。接上分類步驟後已修正。

## 六、驗證（2026-11-15 實跑）

| 項目 | 結果 |
|---|---|
| 自動抓取 | TWSE **247(auto)** ＋ TPEx **118(auto)** = **365 檔**（原 363） |
| `as_of` | 2026-11-02 → **2026-11-15** |
| 資料合理性 | 0050 規模 24,556 → **25,608 億**；受益人數 374.1 萬 → **395.7 萬** |
| 新增／遺失 | 新增 00413A、00418A；**無遺失** |
| 分類修正 | 00413A／00418A → `security_type=etf`、`is_etf=true` |
| `test_etf_meta_2026_11_15.py` | **11/11** |
| `test_data_rules` ＋ `test_market_extras` ＋ `test_etf_meta` | **94/94** |
| `test_known_errors.py` | **145/145** |
| `test_fake_data_regression` | 全通過 |
| Node 4 支 | 全 PASS |
| QA Gate | **🟢 ALLOW DEPLOY** |

## 七、注意事項

- `parse_etf_meta.py` 檔頭記載「兩站使用條款禁止自動化擷取」——
  Ivan 2026-11-15 已知悉並決定採官方端點自動化，屬**低頻（每週）**，
  且保留人工 CSV 為備援；若日後要停止，移除 workflow 的 `etf-meta` job 即可。
- 資產規模／受益人數是**抓取當下的快照值**，非即時。
- 站上 ETF 每日價量仍來自 TWSE／TPEx 每日行情，與本檔無關。
