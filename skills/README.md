# mklab-stock Skills Index

本專案採用 **Skills First Architecture**。所有功能以 Skill 為核心，每個 Skill 自包含於 `skills/<name>/`。

## 使用順序（每次修改必讀）

1. 讀本文件 `skills/README.md`
2. 讀 `skills/router.md` 判斷需要哪些 Skill
3. 讀對應 `skill.md`
4. 執行同資料夾內的 Python Script
5. 完成 `checklist.md`
6. 輸出結果

## Skill 清單

| Skill | 職責 | 入口 |
|-------|------|------|
| `qa-gate` | 品質門禁（Python/資料/JSON/HTML/CSS/JS/Chart/連結/視覺） | `qa-gate/skill.md` |
| `html-health` | HTML 結構健康檢查（防空白頁） | `html-health/skill.md` |
| `lint` | 程式碼/結構 Lint 規則 | `lint/skill.md` |
| `design-system` | UI/Theme 規範 | `design-system/skill.md` |
| `data` | 資料抓取/匯出/結構 | `data/skill.md` |
| `deployment` | GitHub Pages 部署 | `deployment/skill.md` |
| `development` | 開發輔助/編碼風格 | `development/skill.md` |

## 原則

- Skill 內含：skill.md / Python / checklist.md / config.json / rules / 文件，**不拆散**
- 優先建立 Skill，不要先建立散落 Script
- 每個 Skill 獨立維護、獨立執行、獨立擴充
