# MKLAB Framework v1.x — Skills First Architecture

> 本文件為 mklab-stock 專案的**架構標準規範（mklab-stock-webbase）**，所有 AI Agent 修改前必須先閱讀。

## 專案最高原則

本專案採用 **Skills First Architecture**。
本專案不是傳統 Web 專案，而是 **AI Agent First 專案**，因此所有功能均以 Skill 為核心設計。

### 最高優先順序

- ★ Fork First
- ★ GitHub Pages 原生部署
- ★ AI Agent 容易理解
- ★ Self-contained Skill（Skill 自包含）
- ★ Python 僅作輔助工具
- ★ Web Components
- ★ GrapesJS Compatible
- ★ 零 Node.js Build
- ★ 長期維護
- ★ 最少重複程式碼

---

## 專案架構

```
mklab-stock/

index.html
mklab-stock-screener.html
mklab-stock-research.html
mklab-stock-industry.html
mklab-stock-watchlist.html
mklab-stock-help.html
mklab-stock-log.html

assets/
│
├── css/
├── js/
├── icons/
└── images/

data/
│
├── history/
│
├── stocks.json
├── industry.json
├── market.json
├── markets.json
├── indices.json
├── indices-config.json
├── industry-codes.json
├── schema-version.json
└── etf-shares.json

templates/
│
├── base.html
├── header.html
├── drawer.html
├── footer.html
└── meta.html

build/
│
└── template_sync.py

skills/
│
├── README.md
├── router.md
│
├── qa-gate/
│   ├── skill.md
│   ├── qa_gate.py
│   ├── checklist.md
│   └── config.json
│
├── html-health/
│   ├── skill.md
│   ├── check_html_health.py
│   ├── checklist.md
│   └── rules.json
│
├── lint/
│   ├── skill.md
│   ├── lint.py
│   ├── checklist.md
│   └── lint-rules.json
│
├── design-system/
│   ├── skill.md
│   ├── ui-rules.md
│   └── theme.json
│
├── data/
│   ├── skill.md
│   ├── fetch_data.py
│   ├── update_overview.py
│   └── schema.md
│
├── deployment/
│   ├── skill.md
│   ├── deploy.py
│   └── github-pages.md
│
└── development/
    ├── skill.md
    ├── coding-style.md
    └── helper.py

docs/

sandbox/

vendor/

.github/
```

---

## Skills First 原則

每一個 Skill 都是一個**完整的小模組**。

Skill 內可以包含：

- `skill.md`（AI 執行規範）
- Python Script
- Checklist
- Rules
- Config
- Documentation

**所有與該 Skill 有關的檔案都放在同一資料夾。不要拆散到不同位置。**

例如：

```
skills/
    qa-gate/
        裡面就包含：
        skill.md
        qa_gate.py
        checklist.md
        config.json
```

而不是：

```
scripts/qa_gate.py
docs/checklist.md
config/config.json
```

分散於多個資料夾。

---

## Build

`build/` 僅保存：**Template Synchronizer**

例如：`template_sync.py`

用途：同步

- Header
- Drawer
- Footer
- Meta

不得負責：

- 資料抓取
- QA
- Lint
- 部署

---

## HTML

根目錄 HTML **即正式網站**。

不得建立：`pages/`
不得建立：第二份 HTML。

---

## Templates

`templates/` 只保存：

- Header
- Drawer
- Footer
- Meta
- Base

不得保存完整頁面。

---

## Assets

`assets/` 只保存：

- CSS
- JavaScript
- Images
- Icons

不得保存：

- Build Script
- Python

---

## Data

所有執行資料：統一 `data/`
所有 Schema：統一 `data/`

不得建立：`config/`

---

## 每次修改流程

Agent 必須：

1. 閱讀：`skills/README.md`
2. 閱讀：`skills/router.md`
3. 判斷：需要哪些 Skill
4. 閱讀：對應 `skill.md`
5. 執行：同資料夾內 Python Script
6. 完成：Checklist
7. 輸出：結果

---

## Repository Health

任何重大修改完成後，必須產生：**Repository Health Report**。

至少包含：

- Unused Files
- Unused Folders
- Duplicate Files
- Duplicate JSON
- Broken Links
- HTML Health
- QA Gate
- Template Sync
- Vendor Check
- Empty Directories

---

## Commit 規範

不得：直接 `git commit`
不得：`git push`

除非：我明確批准。

Agent 必須先提供：

- 修改摘要
- Repository Tree
- QA Report
- Repository Health Report
- 相容性分析

等待確認。

---

## AI Agent 開發原則

所有功能：**優先建立 Skill。不要先建立 Script。**

先思考：這是不是一個可以重複利用的 Skill？

如果是，建立：`skills/xxx/`，並將：

- 規範
- Python
- Checklist
- Config

全部放在同一資料夾。

讓每一個 Skill 都能**獨立維護、獨立執行、獨立擴充**。

---

## 最終目標

打造一個：

**AI Agent First · Skills First · Fork First · GitHub Pages Native · Web Components · GrapesJS Compatible · Python Tool Assisted · Long-term Maintainable · Low Maintenance · High Readability**

的 MKLAB 股票分析平台。

---

## 執行記錄（2026-07-20）

### 架構重構：方案 A（Skills First 反向重構）

將專案從「scripts/ 集中式」重構為「Skills First 自包含」架構，完全符合本規範。

**變更摘要：**
- 刪除 `scripts/` 資料夾，6 個 Python 腳本搬入對應 Skill：
  - `qa_gate.py` / `validate_data.py` → `skills/qa-gate/`
  - `check_html_health.py` → `skills/html-health/`
  - `fetch_data.py` / `update_overview.py` / `export_db.py` → `skills/data/`
- 新建 7 個 Skill（自包含 skill.md / Python / checklist / config / rules）：
  - `qa-gate` `html-health` `lint` `design-system` `data` `deployment` `development`
- 新增入口：`skills/README.md`（索引）、`skills/router.md`（路由決策）
- 移除 `mklab-stock-lint/`（舊結構），其規範併入 `lint/`
- `build/build_pages.py` → 改名 `build/template_sync.py`（Template Synchronizer）
- 移除：`pages/`、`config/`、`wiki/`、`prototypes/`（→ `sandbox/`）、`repair_*.zip`、`handoff.md`（→ 統一 HANDOFF.md）、`vendor/` 重複
- `data/market.json` → 改名 `data/markets.json`（符合架構清單）

**路徑修正：**
- 所有搬移腳本的 ROOT 計算加深一層（`..` → `../..`），已驗證解析正確
- `.github/workflows/qa-gate.yml`、`html-health.yml` 路徑改指 `skills/`
- `qa_gate.py` 內部 `py_files` 清單更新為新 Skill 路徑

**QA 結果（重構後）：**
| 檢查 | 結果 |
|------|------|
| `build/template_sync.py` | ✅ 冪等（0 變更） |
| `skills/qa-gate/qa_gate.py` | ✅ ALLOW DEPLOY（0 Critical, 1 WARNING 已知） |
| `skills/html-health/check_html_health.py` | ✅ 7/7 健康 |
| `skills/lint/lint.py` | ✅ 通過 |
| Broken Links | ✅ 通過 |

**Repository Health（重構後）：**
- Unused Folders: 無（已清理 components/src/tests/tools/config/pages/wiki）
- Duplicate JSON: 無（config/ 已刪，data/ 為單一來源）
- Vendor Duplicate: 無（僅 lightweight-charts.min.js）
- Empty Directories: assets/icons/、assets/images/（保留結構，git 不追蹤）
- Broken References: 無

**相容性：**
- GitHub Pages：根目錄 HTML 結構不變，`<base href="/mklab-stock/">` 保留 ✅
- Fork First：clone 即跑，無 scripts/ 依賴 ✅
- Web Components / GrapesJS：未改 `mklab-wc.js`、未改元件用法 ✅
- 既有 UI 修復（8 項）：已含於根目錄 HTML，未被同步覆寫 ✅

### 補遺修正（同輪，確保 CI 不中斷）

- `.github/workflows/daily-update.yml`：4 處 `scripts/fetch_data.py` → `skills/data/fetch_data.py`
- `.github/workflows/html-health.yml`：push block paths 殘留 `scripts/` → 改 `skills/html-health/`
- `README.md` / `docs/mklab-stock-schema.md` / `mklab-stock-log.html`：舊 `scripts/`、`pages/`、`build_pages.py` 引用更新為 Skills First 架構
- 上述修正經 QA 全 PASS（ALLOW DEPLOY, 7/7 健康, lint 通過, broken links 通過）
