# mklab-stock

手機優先的台股 / 美股 / A股（滬深+港股）股市儀表板。靜態優先（Static-First）、Build-Time 預算、零密鑰（zero-secret）即可上線。

## 設計原則（架構憲法）
- **不問「能不能做」，只問「應不應該做」**——每個功能過 8 題閘門，≥2 否則延後/轉 Optional/刪除。
- **最容易維護 > Fork 即跑 > 易理解 > 長期發展**（非功能最多）。
- **靜態優先**：資料以 JSON 進 repo，不依賴外部 DB；衍生資料進 repo，原始日線留外部。
- **零密鑰**：所有已實作功能不含 API key / token / secret；需要授權的資料源走 Build-Time 預算或公開 API。
- **執行效率第一，好維護第二**：輕量庫、少外部依賴。

## 頁面（Domain）
| 頁面 | 檔名 | 說明 |
|------|------|------|
| Market（首頁） | `prototypes/mklab-stock-home-prototype-v11.html` | 五國股市走勢卡 + KLineChart（K線/MACD/KD/畫線）+ 精選個股表 |
| Screener | `prototypes/mklab-stock-screener-prototype-v11.html` | 多條件篩選 + 策略模板（價值/品質/成長/動能/高股息）+ 滑動桿即時篩選 |
| Research | `prototypes/mklab-stock-research-prototype-v11-full.html` | 個股研究中心（KLineChart + 財務指標） |
| Industry | `prototypes/mklab-stock-industry-prototype-v11.html` | 台灣 33 法定產業動態（漲跌績效 + 成分股） |
| Watchlist | `prototypes/mklab-stock-watchlist-prototype-v11.html` | 自選股追蹤 |

## 当前狀態
- **v11 原型**（HTML + 原生 JS，無框架）：5 頁可互動，自包含無外部網路依賴（KLineChart 已 vendor 化）。
- 市場：TW + US + China（A股滬深 / 港股）。
- 歷史基線：3 年。
- 資料以 2026-07-13 收盤為準（前一日，非即時）。

## 目錄
```
mklab-stock/
├── prototypes/          # 五頁 HTML 原型 + vendor/
│   └── vendor/klinecharts.min.js
├── docs/                # 設計依據 / 資源 / 可部署 Skill 正文
│   ├── design.md        # 架構主文（為什麼這樣設計）
│   ├── resource.md      # 資源彙整（我們狀態對照）
│   └── SKILL.md         # 可部署 Skill 執行規範（觸發後做什麼）
├── src/                 # （預留）React 階段實作
└── data/                # （預留）Build-Time 生成的 JSON
```

## 本地預覽
直接用瀏覽器開 `prototypes/mklab-stock-home-prototype-v11.html` 即可（file:// 協議可跑，無需 server）。

## 上線（GitHub Pages / 靜態託管）
1. Fork 或 clone 本 repo。
2. 靜態託管根目錄指向 `prototypes/`（或自行 Build 到 `docs/`）。
3. 無構建步驟需求——原型即靜態成品。

## License
見 LICENSE（預設 MIT，待補）。
