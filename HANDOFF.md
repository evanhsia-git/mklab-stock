# mklab-stock 架構總覽（Skills First）

## 專案定位
手機優先的台股/美股/全球指數靜態儀表板，零密鑰、Build-Time 預先處理，fork 即可獨立運作。

## 設計原則
- 靜態優先：資料以 JSON 進 repo，前端 vanilla JS + Web Components。
- 零密鑰：不含 API key/token，資料源為公開 API 或排程抓取。
- GitHub‑Native / Fork‑First：fork 後開啟 GitHub Pages 即可運作。
- Build‑Time 優先：所有資料由 GitHub Actions 排程預算寫入 `data/`，前端只讀取呈現。

## 目錄結構（核心）
mklab-stock/
├─ *.html               # 11 功能頁 + 說明/日誌
├─ assets/              # CSS/JS（含資料層、Shell、Drawer、Web Components）
├─ data/                # Build-Time 產出的 JSON（stocks.json、industry.json 等）
├─ docs/                # 設計依據／欄位說明
├─ skills/              # Skills First（qa-gate、data、deployment、design-system、development、html-health、lint 等）
├─ vendor/              # 第三方 JS（lightweight-charts）
├─ .github/workflows/   # daily-update.yml、qa-gate.yml
├─ HANDOFF.md           # 本檔案
└─ README.md

## 資料來源
- TWSE OpenAPI（每日收盤、PE/PB/殖利率）
- TWSE 營益分析／資產負債表（ROE/ROA/EPS），週六 yfinance 備援
- yfinance（全球指數／代表 ETF、TWII K 線 260 日）
- 臺證所 33 類產業對照表

## 綜合評分規則（Market 首頁）
依 ROE（40）、PE（20）、PB（15）、EPS（10）、漲跌%（15）加權計算 0–100 分，任一欄位 null 則排除。

## Skills First 工作流程
1. 閱讀 skills/README.md 與 skills/router.md 判斷所需 Skill。
2. 閱讀對應 skill.md 了解規範。
3. 在同資料夾內執行 Python Script（如 fetch_data.py、deploy.py）。
4. 按 Checklist 完成。
5. 提交前產出 Repository Health Report（見 HANDOFF.md）。

## 品質門禁（QA Gate）
執行 python skills/qa-gate/qa_gate.py --json qa-result.json，檢查資料完整性、Schema、HTML 結構、CSS 主題變數一致性、JavaScript 語法等，必須為 ALLOW DEPLOY（0 Critical）才能推送。