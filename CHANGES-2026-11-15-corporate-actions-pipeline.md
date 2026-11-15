# CHANGES 2026-11-15 — 公司行為 pipeline（QA 規則、每日排程、前端標註）

延續同日 `b8a2c1bc`（還原價＋死值列＋自動偵測），本批補上「上線所需的三件事」。

## 1. QA Gate 新增三條規則（`skills/qa-gate/qa_gate.py`）

| 規則 | 等級 | 內容 |
|------|------|------|
| `CORPORATE_ACTION_UNSOURCED` | ERROR | done 條目須有 source/type/ratio>0/resume_date；pending/planned 至少 source |
| `DEAD_VALUE_RUN` | WARNING | 最近 20 個快照中「連續同價＋同量」≥3 天的死值列 |
| `CORPORATE_ACTION_DETECTED` | WARNING | 跳空候選未登錄為公司行為時提醒 |

設計：ERROR 只擋「已執行卻無來源」，規劃中事件只要求來源——否則 00757／006208
（官方尚未給倍數與換發日）會讓整個部署永遠被擋。

## 2. 每日排程接入（`.github/workflows/daily-update.yml`）

daily job 在 `compute_indicators` **之前**新增：

```yaml
- name: 修復歷史快照死值列與公司行為偵測
  run: python skills/data/repair_history.py && python skills/data/detect_corporate_actions.py
```

原因：指標要用「乾淨且還原後」的序列，所以修復與偵測必須先跑。

## 3. 前端標註（「已分割 N:1」）

- `mklab-stock-research.html`：個股資訊卡標題加徽章，資料取自 `corporate_action`。
- `assets/css/component.css`：`.ca-badge` 只用設計令牌（`--border`／`--card`／`--muted`）。
- 線上實看（browser）：`0052 富邦科技 +1.46% 已分割 7.0:1`。

## 4. 修掉的兩個自身缺陷

1. **K 線死值列復活**：`repair_history.py` 冪等重跑時把 `removed_cells` 覆寫成空，
   `build_kline.py` 便無清單可剔除。→ 改為**累積**（與舊 log 取聯集），並由 git HEAD
   差異回復當時遺失的 265 格。
2. **誤套還原價**：未來事件（0053、00662）被整段除 → 均線與股價脫節。
   → `adjust_rows` 只套用「序列內同時有事件前後資料」者。

## 5. 驗證

- `tests/test_corporate_actions_2026_11_15.py` 26 項、`test_known_errors.py` 145 項、
  其他 Python 單元 133 項、Node 4 項全通過；QA Gate：ALLOW DEPLOY。
- 線上（commit `e71ba900`）：qa-gate ✓、pages ✓；`stocks.json` 1446 筆、
  0052/00631L/00685L 有 `adj`、0053/00662 無 `adj`、0052 K 線死值列 0 筆。

## 6. 未結案（需 Ivan 確認）

偵測器 27 檔候選中，疑似未登錄的公司行為：00673R ≈1:4、00674R ≈1:5、00706L ≈1:4、
00715L ≈1:1.93、2327 國巨 ÷3.82、8422 可寧衛 ÷10.1、7780 大研生醫 ÷9.09。
**未登錄前不套用還原價**（避免用錯誤倍數污染指標）。
