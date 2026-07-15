# mklab-stock Handoff（2026-07-15）

> 本檔記錄當前進度與待修項目。新 session 接手時先讀此檔 + 執行導航（SCHEMA/policy/index/log）。

## 當前 Git 狀態
- Branch: `master`（推送到 `origin/main`）
- 最新 commit: `d023442` (fix: export_db.py 漏匯出 roa + 全量補齊 ROE/ROA)
- 工作區可能有未提交修改（Research 頁重構中，見下方待修）

## 一、已完成事項

### 1. ROE/ROA 全量補齊 ✅
- 腳本 `scripts/update_overview.py` 改善：新增 `--cron` 增量模式、`--daily-limit N`、`--skip-etf`（自動排除 ETF，因 yfinance 無 ETF 財報）、`--skip-finmind`、`JSON log + exit code`
- 全量跑完（proc_52b495f58a7c）：更新 1084 檔
- **DB 現狀**：`/root/Documents/database/tw_stock_all.db` 的 stock_overview：
  - roa 有值 **1085/1486**（ETF 無財報跳過，正常）
  - roe 有值 **1088/1486**
- **匯出後** `data/stocks.json`：roa=1085、roe=1088（已修 export_db.py 漏匯出 roa 的 bug）
- 範例 2330：roe=31.7 / roa=21.4 / eps=22.08

### 2. 本機自動化抓 roa ✅
- 系統 crontab 已設定（cron 服務 active）：
  ```
  0 3 * * 6 cd /root/Documents/mklab-stock && python3 scripts/update_overview.py --cron --skip-finmind >> /var/log/mklab_roa.log 2>&1
  ```
- 雲端：GitHub Actions `daily-update.yml` 的 `weekly-roe` job 每週六 18:00 台灣時間跑 fetch_data.py weekly
- FinMind 當前不可用（匿名模式 IP rate-limit + FINMIND_TOKEN 環境變數過期），暫用 yfinance 備援

### 3. README 目錄 tree ✅
- 已擴寫完整 `data/` 結構 + 資料源頭說明（bedf439）

### 4. Wiki ✅
- `Obsidian Vault/finance/mklab-stock/mklab-stock-schema.md` §7.1 修正 FinMind 錯標、§7.5 抓取上限實測、§7.6 cron 友善、§7.8 本機自動化、§7.9 問題解決記錄
- 已同步到 Quartz + repo docs/

## 二、待修項目（重要，下次優先處理）

### 🔴 待修 A：Research 頁 MACD/KD 指標（mklab-stock-research.html）
**現狀（確認 line 221-225 真實狀態）**：
- `klRender` line 221 有**錯誤字串**需修正：
  ```js
  // 錯誤（當前）：
  function klRender(s){ ... klInit(s); if(rSeries) { klineData=genKData('TWII_FAKE'); } }
  // 應改為：
  function klRender(s){ ... klInit(s); if(rSeries) { klineData=genKData(250, STOCKS[s]?STOCKS[s].price:100); } }
  ```
- `klAddIndicator` line 222 用 `rSeries.getData()` 在 LightweightCharts v4.1.3 **不存在** → 指標永遠加不上：
  ```js
  // 錯誤（當前）：
  function klAddIndicator(name){ if(!rChart||!rSeries) return; const d=rSeries.getData?rSeries.getData():[]; if(!d.length) return;
  // 應改為（用全域 klineData 變數，已在 line 194 宣告 let klineData=[]）：
  function klAddIndicator(name){ if(!rChart||!klineData.length) return; const d=klineData;
  ```
- `klineData` 全域變數已在 line 194 宣告，klInit line 217 已正確寫入 `klineData=genKData(250,...)`

**已完成的部分**（瀏覽器實測確認）：
- ✅ 區塊順序：個股摘要 → 歷史價格圖 → 財報摘要（PE Band 區塊已移除）
- ✅ 財報摘要讀真實資料（stocks.json），表格顯示 ROE%/ROA%/EPS/殖利率%/PE/PB 真實值
- ✅ K 線蠟燭圖渲染成功（LightweightCharts v4.1.3，掛在 window.LightweightCharts）
- ⚠️ 圖表庫真相：`vendor/lightweight-charts.min.js`（原誤命名 klinecharts.min.js，已於 2026-07-15 修正）實為 **LightweightCharts v4.1.3**（結尾 `window.LightweightCharts=Oe`）

**修法**：
1. 修正 line 221 的 `genKData('TWII_FAKE')` → `genKData(250, STOCKS[s]?STOCKS[s].price:100)`
2. 修正 line 222 的 `rSeries.getData()` → 改用 `klineData`
3. 瀏覽器實測：點 MACD/KD 按鈕 → 確認 rMacd/rKD 變 true + 圖表出現指標線
4. 畫線功能（畫線/水平線/費波那契）：LightweightCharts v4 免費版無 overlay，klDraw 目前只 console.info 提示（可接受，或換 klinecharts 庫）

### 🔴 待修 B：index.html Market Health 大圖表（標題1年但空白）
**根因**：line 342 `klSeries.setData(TWII_KDATA)` 中 `TWII_KDATA` **從未定義** → 圖表空白
**解決方案（未動工）**：
- 用 `data/history/*.json` 的 **006204 永豐臺灣加權**（追蹤加權指數，261 天真實收盤）拼出 1 年 TWII K 線
- 改 `export_db.py` 新增匯出 `data/twii-kline.json`（約 250 日 K 線）
- 前端 `index.html` 讀真實資料，標題「近 1 年」才名實相符
- 注意：本機 DB 無 TWII 加權指數本身日線，只有 ETF 006204 等代理

### 🟡 待確認 C：commit/push Research 頁
- Research 頁重構修改尚未 commit（工作區有未提交變更）
- 修完待修 A 後，瀏覽器實測通過再 commit + push

## 三、關鍵事實（防踩坑）
1. **FinMind 不可用**：匿名模式 IP rate-limit（每 3-4 檔鎖）、FINMIND_TOKEN 過期。別再浪費時間測 FinMind，直接用 yfinance。
2. **vendor/lightweight-charts.min.js 實為 LightweightCharts v4.1.3**（原檔名 klinecharts.min.js 已於 2026-07-15 修正）：全局變數是 `LightweightCharts`，不是 `klinecharts`。別用 `klinecharts.init()`。
3. **LightweightCharts v4 無 `series.getData()`**：要存 K 線資料用全域變數。
4. **history JSON 一行 minified 是有意設計**（你決定保持，效能優先）。檢視用 `python3 -m json.tool data/history/YYYYMMDD.json`。
5. **本機 DB 是權威源**：`/root/Documents/database/tw_stock_all.db`（38MB），`data/*.json` 是 export_db.py 匯出產物。
6. **local server**：`python3 -m http.server 8765`（背景 proc_f7c0115624f5 可能還在跑）。

## 四、上次 session 已修復的 bug（避免重複）
- export_db.py 漏匯出 roa（已修，SELECT 加 roa + stocks 組裝加 roa）
- sel() 裡 `getElementById('peChart')` 在 peChart div 移除後報錯（已移除該行）
- update_overview.py 重複舊迴圈導致 --skip-finmind 無效（已重寫 main）

## 五、用戶偏好/決策
- Wiki：所有遇到的問題+解決方法都要寫進 Wiki（先查類似頁面併入，不開新頁）
- 資料源原則：TWSE/TPEX 優先，yfinance 備援，FinMind 待有效 token
- history JSON 保持 minified（執行效率）
- ROE/ROA 是季度/年度資料，每週六補一次即可（非每日）
- Research 頁區塊順序：個股摘要 → 歷史價格圖 → 財報摘要 → 個股選擇（左側）
