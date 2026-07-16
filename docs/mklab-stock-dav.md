---
title: "mklab-stock DAV（Web Components 路線 · 決策 2026-07-15）"
description: "比對設計主文 mklab-stock.md v3.0 §10 與目前實際開發差異；2026-07-15 決議放棄 React 化，改採原生 Web Components / ES Modules 元件化，守零外部依賴 / fork 即維護原則。"
type: analysis
status: active
tags:
  - mklab-stock
  - web-components
  - dav
  - 待開發
  - 零依賴
created: 2026-07-15
updated: 2026-07-15
---

# mklab-stock DAV（Web Components 路線）

> 比對對象：設計主文 [[mklab-stock|mklab 簡化架構 v3.0]] §10 React 規劃
> 決策（2026-07-15）：**放棄 React 化**（需 Node/npm/Vite，違反「不依賴外部軟體」），改採**原生 Web Components / ES Modules 元件化**
> 分支策略：`backup/static-2026-07-15`（靜態頁備份/主要上線版）+ `dev/web-components`（開發分支）

---

## 一、現狀事實（實測，2026-07-15）

| 項目 | 實際狀態 |
|------|----------|
| 前端形態 | 5 個靜態 HTML（index + mklab-stock-{research,screener,industry,watchlist}）+ prototypes/ + 空 src/ |
| 元件基礎 | `assets/mklab-core.js` = **IIFE 全域 `MKLAB.*`**（plain `<script>`，刻意支援 file:// 直接開，無 ES module CORS 問題） |
| 圖表實作 | vanilla JS 直接操作 DOM（`vendor/lightweight-charts.min.js` = LightweightCharts v4.1.3） |
| 資料載入 | 各頁內聯 `fetch('data/*.json')` |
| React 工程 | **無**（無 web/、package.json、node_modules、.tsx） |
| 結論 | 靜態 HTML 原型階段；主文 §10 React 終態**決議不採行** |

---

## 二、決策轉向（React → Web Components）

**原因**：用戶原則「fork 就能使用，不依賴外部工具/軟體，友善執行與維護」。React+Vite 需 Node.js+npm+Vite 工具鏈（開發/預覽），違反「不依賴外部軟體」。

**選 2 定義**：瀏覽器原生 **Custom Elements + Shadow DOM**（+ 可選 ES Modules），把 `MKLAB.*` 進一步封裝成 `<mklab-kline>`、`<mklab-datatable>` 等標籤。

**關鍵相容約束**：
- `mklab-core.js` 現為 plain script 支援 `file://` 直接開。Web Components 的 `customElements.define()` 在 **classic script 也能用**（不強制 ES module）→ 仍可 file:// 開，守零依賴。
- 若用 ES module（`type="module"`），`file://` 有 CORS 限制；用戶以 `python -m http.server` 預覽則無礙。決議：**WC 元件用 classic script 註冊**（最大相容），`data-client` 可用 IIFE。

**與最高原則符合性**：
- 零外部依賴 ✅（無 npm/Node/Vite）
- fork 即維護 ✅（改 `.js` 即生效，無 build）
- Static First ✅（仍只讀 data/*.json）
- 新手心態 / 系統維護 ✅（元件復用減漂移）

---

## 三、差異比對（主文§10 React 規劃 vs 實際 vs 選2後）

| 主文規劃（React） | 實際 | 選 2 對應（Web Components） |
|-------------------|------|----------------------------|
| `web/` React+Vite | 無 | `assets/mklab-wc.js`（plain script Custom Elements） |
| `router.tsx` SPA | 多頁跳轉 | `<mklab-router>`（History API，classic） |
| `data-client.ts` | 散落 fetch | `assets/data-client.js`（IIFE，統一 fetch） |
| `routes/dashboard.tsx` | index.html 邏輯 | `<mklab-dashboard>` 元件 |
| `routes/market.tsx` | 邏輯在 HTML | `<mklab-market>` 元件 |
| `routes/asset.tsx` | 邏輯在 HTML | `<mklab-asset>` 元件 |
| `components/` | `MKLAB.*` IIFE | `<mklab-*>` Custom Elements |
| 圖表 React wrapper | vanilla DOM | `<mklab-kline>` 封裝 LightweightCharts |
| `shared/` TS 型別 | 無 | JSDoc `@typedef` + 手動 schema 對照 |
| `tests/` Vitest+Playwright | 僅 Python qa_gate | 擴充 qa_gate + HTML 健康檢查 |

---

## 四、Web Components 待開發項目（推薦排序 + 難易度）

評分：推薦度（高=MVP核心/每日用；中=Phase2/Optional）｜難易度（低=配置/型別<1d；中=邏輯重構1-3d；高=DOM重構/需決策>3d）

| # | 項目 | 對應主文 | 現狀 | 推薦度 | 難易度 | 備註 |
|---|------|----------|------|--------|--------|------|
| 1 | 遷移策略決策（WC 版） | §10 | 已決選2 | 高 | 低 | 漸進並行：現有頁不動，新增 wc.js |
| 2 | WC 基礎（mklab-wc.js + customElements.define） | §10 | 無 | 高 | 中 | plain script 註冊機制，不破壞 MKLAB.* |
| 3 | data-client.js 統一資料層 | §10 shared | 散落 fetch | 高 | 低 | 取代各頁內聯 fetch |
| 4 | `<mklab-kline>` 圖表封裝 | §5 圖表層 | vanilla DOM | 高 | 高 | 解白屏風險；Shadow DOM+LightweightCharts 需外掛 container |
| 5 | `<mklab-datatable>` 表格元件 | §3.1 | MKLAB.DataTable | 高 | 中 | 轉 Custom Element，sort/pager 屬性化 |
| 6 | `<mklab-drawer>` 抽屜/主題 | §3.2/3.4 | MKLAB.Drawer/Shell | 中 | 中 | 主題/語言狀態內聚 |
| 7 | `<mklab-sparkline>` 迷你走勢 | — | 內聯 SVG | 中 | 低 | Watchlist/表格趨勢列 |
| 8 | `<mklab-freshness>` 新鮮度 banner | §4.1 | 無統一 | 中 | 低 | System 狀態條 |
| 9 | SPA 路由（History API） | §10 router | 多頁跳轉 | 中 | 中 | 無 React Router；深鏈接+狀態 |
| 10 | 首頁 `<mklab-dashboard>` | §1/§9 | 邏輯在 HTML | 高 | 中 | 4 問複合視圖元件化 |
| 11 | Market/Asset/Portfolio 元件化 | §1 | 邏輯在 HTML | 高 | 高 | 最重邏輯搬移 |
| 12 | CI 前端檢查擴充 | §10 tests | 僅 qa_gate | 中 | 中 | 加 HTML 健康/元件掛載檢查 |

---

## 五、執行路線（依上表序，守漸進不破壞）

1. **#1–#3 基礎**：決策已定 → 建 `mklab-wc.js` + `data-client.js`（不改現有頁）
2. **#4 `<mklab-kline>`**：最高風險項早做；先 demo 頁驗證，再接入 research/index
3. **#5–#8 元件**：表格/抽屜/迷你圖/新鮮度
4. **#9–#11 路由與頁面**：逐頁接入（並行過渡期：WC 頁與靜態頁共存）
5. **#12 驗證**：superpowers verification + qa_gate
6. **上線**：dev → main merge + push → GitHub Pages 自動部署

---

## 六、風險與緩解

| 風險 | 緩解 |
|------|------|
| 瀏覽器相容（Custom Elements 需現代瀏覽器） | 使用者手機現代瀏覽器→無礙；必要加 `@webcomponents/webcomponentsjs` polyfill（仍零 build） |
| mklab-core.js 重構成本（IIFE→WC） | 漸進：先抽 data-client 與 `<mklab-kline>`，其餘保留 MKLAB.* 並行 |
| 無 TS 型別 | JSDoc `@typedef` + 手動 schema 對照（犧牲自動檢查） |
| Shadow DOM + 圖表庫衝突 | `<mklab-kline>` 內用外部 div 掛 LightweightCharts（不進 shadowRoot） |
| 過度工程化 | 守憲法「Simple is Better」：只封裝真復用的（表格/圖表/抽屜） |

---

## 七、與原 React 路線對比總結

| | React 路線 | 選 2 Web Components |
|--|-----------|---------------------|
| 零外部依賴 | ❌ 需 Node/npm | ✅ 符合 |
| fork 即維護 | ⚠️ 終端零依賴/維護者需 Node | ✅ 全符合 |
| 元件化/可維護 | ✅ 最佳 | ✅ 良好（略遜 TS/HMR） |
| 型別安全 | ✅ TS | ❌ JSDoc |
| 生態 | ✅ npm 豐富 | ❌ 精簡 |

> 選 2 在守住「零外部依賴 / fork 即維護」前提下，拿到 React 化核心好處（元件復用、樣式隔離、SPA 路由），代價是放棄 TS 與 HMR——對本專案規模可接受。

---

*建立：2026-07-15 — 初版 React DAV；同日決議轉 Web Components 路線，重寫本文件。分支：backup/static-2026-07-15 + dev/web-components。*
