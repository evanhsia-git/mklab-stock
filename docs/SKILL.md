---
title: "mklab-stock 可部署 Skill 正文（SKILL.md 規範）"
description: "ivanhsia/mklab-stock 公開股市儀表板——Fork-First/GitHub-Native/Static-First。觸發：建股市儀表板/部署mklab-stock/這功能違反哪條原則。內含P1-P8/雙排程/Provider Layer v2(統一Registry+能力感知路由)/5 Domain(3核心+2進階)/2 Phase/紅線/新手友善補強。本頁為可上線 skill 正文，架構細節見主文。"
summary: "Hermes skill 正文（隨時可註冊上線）。觸發即引導建站/部署/架構合規檢查，依據架構主文 v3.0 執行，不重複設計細節。"
type: project
status: active
tags:
  - etf
  - finance
  - skills
created: 2026-07-13
updated: 2026-07-14
---

# mklab-stock — 可部署 Skill 正文

> **本頁即 Hermes skill 正文**，隨時可複製至 `~/.hermes/skills/mklab-stock-skill/SKILL.md` 註冊上線（註冊時將本頁 Obsidian 前置元改為 Hermes 前置元 `name`/`description` 即可，正文不變）。
> **架構規劃主文（設計依據，含完整理由與檔案樹）**：[[finance/mklab-stock|mklab-stock 架構主文 v3.0]]
> 兩者分工：**本頁 = 觸發後「做什麼 / 怎麼做」的可執行規範；主文 = 「為什麼這樣設計」的架構規劃**。修改設計先看主文，修改執行流程改本頁。

## 一、觸發條件
| 用戶說 | 動作 |
|--------|------|
| 建股市儀表板 / 部署 mklab-stock | 初始化 repo + Phase0 契約（依主文 §8 / §10 樹） |
| 更新公開分析站 / 跑每日更新 | 觸發 Actions 三排程（08:30 美股 / 17:00 台股 / 19:00 中國市場 A股滬深+港股） |
| 這功能違反哪條原則 / 合規檢查 | 對照 P1-P8 與架構憲法閘門（第八節） |

## 二、技能目標

將「匿名公開台股/美股/中國市場(A股滬深+港股)儀表板」從零建起或持續維護。

| 維度 | 設定 |
|------|------|
| 定位 | 匿名公開台股/美股/中國市場(A股滬深+港股)儀表板 |
| 運算模式 | 全 Build-Time（Actions 運算 → Pages 展示 → React SPA） |
| 後端 | 無常駐後端 |
| 零 secret | 可跑滿 3 核心 Domain（Market / Asset / Portfolio）+ 首頁；China 經 Yahoo/Stooq 符號零新增契約 |
| 維護範圍 | 從零建起 / 持續維護 |

**技術棧**（細節見主文 §5）

| 層    | 選擇                           | 說明                                      |
| ---- | ---------------------------- | --------------------------------------- |
| 前端框架 | React + TS + Vite            | SPA，Static First                        |
| UI   | Tailwind + shadcn/ui         | 元件庫                                     |
| 圖表   | ECharts                      | 視覺化                                     |
| 表格   | TanStack Table               | 虛擬化渲染                                   |
| 後端腳本 | Python 3.11 純腳本              | 產 `data/*.json`，免 DB                    |
| 部署   | Actions artifact-based Pages | + `make deploy` 一鍵串接雙排程 / Build / Pages |

## 三、執行流程（觸發後步驟）
1. **辨識意圖**：建站 / 部署 / 架構合規檢查（見第一節）。
2. **讀取設計依據**：先讀 [[finance/mklab-stock|架構主文 v3.0]] 對應章節（Domain / Provider / Phase / 檔案樹），不在本頁重複設計。
3. **套用憲法閘門**：任何新增功能先過第八節 8 項閘門；任兩項「否」→ 延後 / Optional / 刪除。
4. **依 Phase 範圍產出**：Phase0 骨架 → Phase1 核心 → Phase2 進階（見第九節），不跨 Phase 預先做。
5. **遵守紅線**：第七節 12 條鐵律 + 第五節 Provider 紅線，逐條核對。
6. **驗證**：跑第十節驗證清單；CI 斷言 `data/*.json` 通過 Pydantic `schema_version`。

## 四、核心原則 P1-P8（速查）
| # | 原則 | 落實 |
|---|------|------|
| P1 Fork First | 零 secret 跑滿 3 核心 Domain + 首頁 |
| P2 GitHub Native | Actions→Pages→Releases→Artifacts→Issues→Discussions→Wiki→Projects |
| P3 Static First | React 只 render，零商業邏輯 |
| P4 Optional Backend | Hermes/AI 全 Optional，無後端仍正常 |
| P5 Progressive Enhancement | 核心 Domain + 首頁純 Build-Time；空狀態一律有文案不報錯 |
| P6 Build>Run Time | 運算全 Build Time |
| P7 OSS Friendly | 主源僅免 key（TWSE/TPEX/Yahoo/Stooq） |
| P8 Long-term Maintainability | Provider Pattern + Data Contract + Registry + Reproducible + 一鍵部署 |

## 五、Data Provider Layer v2（速查）
目標：Fork/Actions/Pages 相容；零 API Key；Provider 互換；Strategy 不知來源。能力感知路由：過濾（五條件全部滿足：tier 且 secret 且 市場 且 方法 且 健康）再排序。

| Provider | Tier | 市場 | 方法 | Key |
|----------|------|------|------|-----|
| TWSE | 1 | TW | price,history | 無 |
| TPEx | 1 | TPEX | price,history | 無 |
| Yahoo | 1 | TW,US,GLOBAL,指數 | price,history,dividend,financial,news | 無 |
| Stooq | 1 | US,GLOBAL,指數 | price,history | 無 |
| FinMind | 2 | TW | price,history,dividend,financial,news | FINMIND_TOKEN |
| Alpha Vantage | 2 | US,GLOBAL | price,history,dividend,financial | ALPHAVANTAGE_KEY |
| FMP | 2 | US,GLOBAL | price,history,dividend,financial | FMP_KEY |
| Finnhub | 2 | US,GLOBAL | price,history,financial,news | FINNHUB_KEY |
| Polygon | 3 | US,GLOBAL | price,history,dividend,financial | POLYGON_KEY |
| Bloomberg | 3 | GLOBAL | price,history,dividend,financial,news | BLOOMBERG_KEY |

- **Registry**：`build_registry()` — Tier1 永進池；Tier2/3 僅 secret 存在才實例化。Fork 即只用 Tier1。
- **Facade**：路由（market 解析）+ 斷路器（連敗≥3→冷卻 300s）+ 超時（20s）+ 同 run 快取。全失敗 → `DataUnavailable(tried=[...])`，標記缺失不中斷。
- **紅線**：① Strategy 只依賴 DataProvider facade ② Tier1 永不依賴 secret；Tier2/3 無 key 不進池 ③ Failover 透明 ④ 能力感知路由：不對不支援市場/方法發請求 ⑤ 斷路器+超時防卡死 ⑥ Reproducible：每次 run 重抓重算。
- **檔案結構**：`scripts/providers/{base,facade,registry,exceptions}.py` + `builtin/{twse,tpex,yahoo,stooq,china}.py`（china.py：A股滬深 `.SS`/`.SZ` + 港股 `.HK` 符號對應，路由走 Yahoo/Stooq，零新增契約） + `optional/{finmind,alphavantage,fmp,finnhub,polygon,bloomberg}.py`
- 詳細型別與方法、各 Domain 子目錄（market/asset/portfolio/research/learning）、`shared/`、`data/user.json`、`schema-version.json`、`docs/` 見主文 §10 樹。

## 六、5 Domain 契約（速查，3 核心 + 2 進階）
| Domain | Phase | 只回答問題 | 契約 |
|--------|-------|-----------|------|
| 首頁 | 1 | 今天市場？持股有無問題？哪些值得注意/有風險？ | market.json(meta:狀態/新鮮度/dataState) + portfolio.json(含 watchlist) |
| Market | 1 | 今天市場怎麼樣？ | market.json（Heatmap View；無 Ranking，市場層級只看好壞；Breadth 廣度指標 ±4% 動能/趨勢窗，參考 stock-screener，見 resource §十） |
| Asset | 1 | 這檔值得研究嗎？我想找股票？ | asset.json（stock+etf 同構；screener[]/ranking[]/compare/news[] 為內嵌欄位；評分模型 Minervini/CANSLIM 綜合評分，參考 stock-screener，見 resource §十） |
| Portfolio | 1 | 我的投資現在如何？ | portfolio.json（user.json 內建 demo 驅動，含 watchlist；真實持倉不 push） |
| Research | 2 | 我的策略有效嗎？ | research.json（backtest+strategies；Report 為 View） |
| Learning | 2 | 我想學習什麼？ | learning.json（calendar 為 Tool）— 低頻功能，閘門#2 判定進階 |
| System | 1 | 平台狀態/治理 | 首頁狀態條（market.json meta）+ GitHub Issues/Projects（不佔導覽） |

news/status/etf_meta/watch 已併入上述 4 份，不獨立成契約。

## 七、執行鐵律（紅線，逐條核對）
1. Fork 即跑：零 secret 可全功能（3 核心 Domain + 首頁）
2. Static First：計算全 Build Time
3. Offline Friendly：JSON 進 repo，內建 demo user.json
4. Graceful Degradation：無 Hermes/AI 相關隱藏；無資料時顯示 `dataState: empty` 引導文案，不留白/不報錯
5. Optional Secret：無 key 產 null 不報錯
6. 每日一次 push
7. 匿名：真實持倉不 push
8. Data Contract 單一真相（schema_version + CI 斷言）
9. SQLite 非必需
10. Provider 不可穿透：禁 import 具體 provider / 直打 API
11. 每個 View 渲染資料新鮮度 banner，不得讓使用者誤判為即時
12. 五年後接手者只需 `make deploy` 即可重建雙排程/Build/Pages

## 八、架構憲法與新增功能閘門（合規檢查用）
核心思維：**不問「能不能做」，只問「應不應該做」**。
1. 新增功能前先問：能否共用現有功能？
2. 新增模組前先問：能否共用現有 Domain？
3. 新增 Workflow 前先問：能否共用現有 Workflow？
4. 新增 JSON 前先問：能否共用現有 Data Contract？
5. 新增 Provider/Registry 前先問：Tier1 是否已足夠？
6. 少數人用/低頻功能 → 預設 Optional，非 Core（如 Learning）
7. 增加 Workflow/Provider/Schema/Build Time/維護成本 → 重新評估是否值得
8. 一律遵守：Simple>Complex，Less is More，User First，Fork First，Long-term Maintainability First

**新增功能閘門**（全「是」才進 MVP；任兩項「否」→ 延後/Optional/刪除）：
| # | 閘門問題 | 否的含意 |
|---|---------|---------|
| 1 | 是 MVP？ | 非核心，延後 |
| 2 | 每天有人用？ | 低頻，進階/Optional |
| 3 | 值得增加維護成本？ | 刪除 |
| 4 | 值得增加 Build Time？ | 延後/刪除 |
| 5 | 值得增加 Workflow？ | 延後/刪除 |
| 6 | 值得增加 JSON？ | 合併進既有/刪除 |
| 7 | 值得增加 Provider/Registry？ | 延後/Tier 外不進核心 |
| 8 | 值得增加 Schema？ | 合併進既**有**/刪除 |

目標優先序：最容易維護 > 最容易 Fork > 最容易理解 > 最容易長期發展（非功能最多）。

## 九、Phase 路線（範圍）
| Phase | 範圍 |
|-------|------|
| 0 骨架 | repo+Pages+shared/(schema.ts/types.ts/version.ts)+scripts/shared/schema.py(schema_version)+data/schema-version.json+**三排程骨架(daily-tw/daily-us/daily-cn)**+providers/套件+README Quickstart+demo user.json+`make deploy` |
| 1 核心 | fetch_tw/fetch_us→JSON（Tier1 寫死順序）；calc_factor/screener/heatmap；首頁+Market+Asset+Portfolio+System 狀態條（4 核心 JSON，含 dataState/新鮮度）；pytest+CI contract 斷言；build→Pages |
| 2 進階選配 | Research(回測)+Learning 學習中心(research.json)；因子中性化/Compare/Replay；AI 摘要設 Key 才啟用；Vitest+Playwright |

## 十、驗證清單（上線前 / 每次修改後）
- [ ] **Fork 即跑**：零 secret 可全功能（3 核心 Domain + 首頁）
- [ ] **新鮮度 banner**：每個 View 渲染資料新鮮度（來源 market.json.meta）
- [ ] **空狀態**：各 Domain 無資料時顯示引導文案（dataState: empty），無空白/報錯
- [ ] **Data Contract**：data/*.json 通過 Pydantic schema_version 斷言（CI job）
- [ ] **Provider 不可穿透**：無程式碼 import 具體 provider / 直打 API
- [ ] **Optional Secret**：無 key 時相關欄位產 null 不報錯
- [ ] **每日一次 push**；真實持倉不 push
- [ ] **make deploy** 可重建雙排程/Build/Pages
- [ ] **新增功能過閘門**：第八節 8 項全「是」或僅 ≤1 項「否」才進 MVP

## 相關資源
- [[finance/mklab-stock|架構規劃主文 v3.0（設計依據）]]
- [[finance/mklab-stock-prompt|實作紀錄]]
- [[finance/mklab-stock-qa-1|Q&A 第一批]]
- [[finance/mklab-stock-qa-2|多角色審查]]
- [[finance/mklab-stock-resource|資源清單]]
