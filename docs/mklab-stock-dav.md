---
title: "mklab-stock DAV（設計 vs 實際 vs 待開發 · React 功能向）"
description: "比對設計主文 mklab-stock.md v3.0 §10 React 規劃與目前實際開發差異，列出 React 相關待開發項目、推薦排序、難易度。"
type: analysis
status: active
tags:
  - mklab-stock
  - react
  - dav
  - 待開發
  - 差異比對
created: 2026-07-15
updated: 2026-07-15
---

# mklab-stock DAV（Design vs Actual vs 待開發）

> 比對對象：設計主文 [[mklab-stock|mklab 簡化架構 v3.0]] §10 預設檔案結構（React + Vite 終態）
> 實際基準：2026-07-15 本機 repo `/root/Documents/mklab-stock` 實測狀態
> 目的：確認「還能開發哪些與 React 功能有關的項目」，給出推薦排序與難易度

---

## 一、現狀事實（實測，2026-07-15）

| 項目 | 實際狀態 |
|------|----------|
| 前端形態 | **5 個靜態 HTML**（`index.html` + `mklab-stock-{research,screener,industry,watchlist}.html`）+ `prototypes/`（舊原型）+ 空 `src/` |
| React 工程 | **無**：無 `web/`、無 `package.json`、無 `node_modules`、無 `.tsx`、無 Vite 配置 |
| 圖表實作 | vanilla JS 直接操作 DOM（`LightweightCharts` 掛 `window`，`vendor/lightweight-charts.min.js`），無 React 元件封裝 |
| 資料載入 | 各頁內聯 `fetch('data/*.json')`，無統一 DataClient |
| 路由 | 多頁 `<a href>` 跳轉（非 SPA），無 router |
| 結論 | 目前是「**靜態 HTML 原型**」階段；主文 §10 的 React 終態**完全未實作** |

---

## 二、差異比對表（設計規劃 vs 實際開發）

| 主文規劃（§10 / §5） | 實際現狀 | 缺口嚴重度 |
|----------------------|----------|------------|
| `web/` React + Vite + TS + Tailwind 工程 | 不存在 | 🔴 整體未開始 |
| `web/app/App.tsx` + `router.tsx`（SPA 路由） | 多頁 HTML 跳轉 | 🔴 未實作 |
| `web/shared/data-client.ts`（讀 data/*.json + 新鮮度 banner） | 各頁散落 fetch | 🔴 未實作 |
| `web/routes/dashboard.tsx`（首頁 4 問複合視圖） | `index.html` 靜態實作（功能可用，但 vanilla） | 🟡 邏輯在，需搬移 |
| `web/routes/market.tsx`（Heatmap View） | `index.html` Market Health 區塊（K線已可用） | 🟡 邏輯在，需搬移 |
| `web/routes/asset.tsx`（個股/ETF + Screener/Compare） | `mklab-stock-{research,screener}.html`（vanilla） | 🟡 邏輯在，需搬移 |
| `web/routes/portfolio.tsx` | `mklab-stock-watchlist.html`（部分） | 🟡 邏輯在，需搬移 |
| `web/routes/learning.tsx`（Phase2） | 無 | 🔴 未實作 |
| `web/routes/research.tsx`（回測報告，預設隱藏） | `mklab-stock-research.html`（K線+MACD/KD 已可用） | 🟡 邏輯在，需搬移 |
| `web/components/`（共用元件） | `assets/mklab-core.js`（vanilla 共用模組） | 🟡 需 React 化 |
| 圖表層封裝（KLineChart 自託管 + 小圖 SVG/Chart.js） | vanilla 直接 DOM 操作 | 🔴 需 React wrapper |
| `shared/`（前端型別 schema.ts/types.ts/version.ts） | 無（前端無 TS） | 🟡 未實作 |
| `tests/`（Vitest + Playwright e2e） | 僅 `scripts/qa_gate.py`（Python 靜態檢查） | 🟠 缺前端測試 |
| `npm run build → dist/` → GitHub Pages | `python -m http.server` 直讀 HTML（無 build 步驟） | 🔴 未實作 |

> 關鍵認知：**功能邏輯多已存在於靜態 HTML（首頁/Market/Research 的 K線、MACD/KD、財報摘要均可用）**，缺口主要是「工程化封裝成 React SPA」而非「從零開發功能」。

---

## 三、React 相關待開發項目（推薦排序 + 難易度）

評分標準：
- **推薦度**：高 = MVP 核心 / 每日用 / 維護成本可接受（憲法閘門全過）；中 = Phase2 或 Optional；低 = 低頻或違憲法（主文已規劃故最低為中）
- **難易度**：低 = 純配置/型別/fetch（<1天）；中 = 邏輯重構但模式清楚（1–3天）；高 = DOM 操作重構/狀態管理/需決策（>3天）

| # | 項目 | 對應主文章節 | 現狀 | 推薦度 | 難易度 | 備註 |
|---|------|--------------|------|--------|--------|------|
| 1 | **遷移策略決策**（逐步替換 vs 全重寫 SPA） | §10 | 未決 | **高** | 低 | 先定方向再動工；建議「先 scaffold SPA + DataClient，再逐頁搬移」降低風險 |
| 2 | **React 工程初始化**（Vite+TS+Tailwind+router+App 骨架） | §10 `web/` | 無 | **高** | 中 | 一次性 scaffold；含 `vite.config.ts`/`tailwind.config.ts`/`tsconfig.json` |
| 3 | **DataClient 統一資料層**（`data-client.ts` 讀 JSON + 新鮮度 banner） | §10 `web/shared/` | 散落 fetch | **高** | 低 | 取代各頁內聯 fetch；純 TS，風險低 |
| 4 | **圖表層 React 封裝**（KLineChart/Chart.js 包成元件） | §5 分層策略 | vanilla DOM | **高** | 高 | 目前 `LightweightCharts` 直接操作 DOM，重構為 React 元件風險最高；建議先封裝 K線 wrapper |
| 5 | **首頁 dashboard.tsx**（4 問複合視圖） | §1/§9 圖1 | 邏輯在 HTML | **高** | 中 | 搬移 `index.html` 區塊為 React 元件 |
| 6 | **Market route**（Heatmap View） | §2/§10 | 邏輯在 HTML | **高** | 中 | K線大圖已可用，搬移 + Heatmap 元件化 |
| 7 | **Asset route**（個股/ETF + Screener/Compare） | §1/§10 | 邏輯在 HTML | **高** | 高 | Screener 評分模型 + Compare Tool 搬移，邏輯最重 |
| 8 | **Portfolio route**（持倉/績效/集中度） | §1/§10 | 部分在 HTML | **高** | 中 | watchlist + 集中度警示搬移 |
| 9 | **shared/ 前後端型別對齊**（schema.ts/types.ts/version.ts） | §10 `shared/` | 無 | 中 | 低 | 對齊 `scripts/shared/`，防漂移；純型別 |
| 10 | **Learning route**（學習中心） | §1/§6 Phase2 | 無 | 中 | 中 | Phase2 進階；財報辭典/行事曆/試算 |
| 11 | **Research route**（回測報告，預設隱藏） | §1/§6 Phase2 | 邏輯在 HTML | 中 | 中 | 現有 K線+MACD/KD 搬移 + 回測報告 View（Phase2） |
| 12 | **CI 前端測試**（Vitest + Playwright e2e） | §10 `tests/` | 僅 Python qa_gate | 中 | 中 | 補 `unit`+`contract`+`e2e`；質量門禁 |

---

## 四、推薦執行路線（依上表序）

1. **先決策遷移策略**（#1，低難度高推薦）→ 避免返工
2. ** scaffold + DataClient**（#2 #3）→ 打下 React 基礎，風險低
3. **圖表層封裝**（#4）→ 最高風險項，早做早穩
4. **逐頁搬移**（#5→#6→#8→#7）→ 從最核心（首頁/Market）到最重（Asset）
5. **Phase2 頁**（#10 #11）→ Learning/Research 進階
6. **型別對齊 + CI**（#9 #12）→ 長期維護保障

> 守則：全程 Static First（React 只 render `data/*.json`，禁直打 API）；符合憲法「Fork First / 易維護 / Long-term」。

---

## 五、與憲法閘門對照（新增功能評估）

所有 React 化項目屬「**重構既有功能為終態工程**」，非「新增功能」，故不觸發 §8 新增功能閘門；但遷移本身增加 Build Time（npm build）與 Workflow（deploy.yml），需評估：
- Build Time：Vite build 數秒~分鐘級，可接受（閘門 #4 過）
- Workflow：新增 `deploy.yml`（GitHub Pages 部署），屬既有模式複製（閘門 #5 微影響）
- 結論：React 化整體**不違憲法**，且主文 §10 已預設，屬規劃內執行

---

*建立：2026-07-15 — 比對 mklab-stock.md v3.0 §10 與實際靜態 HTML 原型，列出 React 待開發 12 項 + 推薦度/難易度。*
