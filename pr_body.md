## 重構總結

### ✅ 核心架構變更
- **Template Framework**: templates/ + pages/ + build/ + assets/ 架構
- **7 頁內容片段化**: 含 {{TITLE}}/{{DESCRIPTION}} 標記
- **CSS 分層**: mklab-theme.css, layout.css, component.css, mobile.css
- **統一資料層**: assets/js/data-client.js (IIFE, 快取, ETag)
- **Web Components**: mklab-wc.js 註冊 kline/datatable/drawer/router
- **Build 系統**: build/build_pages.py 支援 placeholder 預設值

### 🎯 核心優勢
- **零 Node.js 依賴**: 純 Python Build
- **GitHub Pages 原生部署**: 輸出根目錄靜態 HTML
- **單一資料來源**: 所有頁面統一使用 MKLAB.data
- **元件化**: Web Components 封裝圖表、表格、抽屜、路由

### ✅ QA Gate 全綠
- HTML 結構檢查通過
- JS 語法檢查通過
- CSS Design Token 一致性通過
- 連結驗證通過
- 資料 Schema 驗證通過

合併後 GitHub Actions 將自動部署至 GitHub Pages。