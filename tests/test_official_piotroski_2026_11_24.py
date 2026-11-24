#!/usr/bin/env python3
"""台股 Piotroski 層回歸測試（compute_piotroski 手算對照，2026-11-24）。

驗證：9 項手算（YTD 同期比）、同期鎖（prev 期別不符→Δ 項 null）、
項缺不計＋covered 如實、null 不補值（輸入 None → 項不計不炸）。
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "of", ROOT / "skills" / "data" / "import_official_fundamentals.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

results = []


def check(name, cond, detail=""):
    results.append((name, cond, detail))


# 手算 fixture（單位：千元）——本期 2026Q2 vs 去年同期 2025Q2
CUR = {"ni_total_ytd_thousand": 120.0, "assets_total_thousand": 5000.0,
       "cfo_ytd_thousand": 150.0, "revenue_ytd_thousand": 1000.0,
       "gross_profit_ytd_thousand": 400.0, "liabilities_total_thousand": 2000.0,
       "current_assets_thousand": 1200.0, "current_liabilities_thousand": 600.0,
       "capital_thousand": 259_000.0}
# 去年同期：ROA 100/4500=2.22%<本期 2.4%；槓桿 2100/4500=46.7%>本期 40%；流動比 1100/700=1.57<2.0；
# 毛利率 320/900=35.6%<40%；週轉 900/4500=0.2=0.2（相等→0）；股本 258,000<259,000（增發→0）
PREV = {"period": "2025Q2", "ni": 100.0, "assets": 4500.0, "cfo": 130.0,
        "revenue": 900.0, "gross": 320.0, "liabilities": 2100.0,
        "current_assets": 1100.0, "current_liabilities": 700.0, "capital": 258_000.0}

scores, missing = m.compute_piotroski(CUR, PREV, prev_period_ok=True)
p = scores.get("piotroski_detail") or {}
check("Piotroski F＝7（手算）", scores.get("piotroski_f") == 7,
      f"F={scores.get('piotroski_f')} detail={p}")
check("Δ週轉＝0（相等不升）", p.get("Δ週轉升") == 0, str(p.get("Δ週轉升")))
check("股本未增＝0（259,000>258,000 增發）", p.get("股本未增") == 0, str(p.get("股本未增")))
check("CFO>NI＝1（150>120 應計健康）", p.get("CFO>NI") == 1)
check("covered＝9/9", scores.get("piotroski_covered") == "9/9", str(scores.get("piotroski_covered")))

# 同期鎖：prev_period_ok=False → Δ 項全 null（拿 Q2 YTD 比 Q1 YTD 是語意錯誤）
s2, miss2 = m.compute_piotroski(CUR, PREV, prev_period_ok=False)
check("同期鎖：僅 3 項可算（ROA/CFO×2），covered=3/9",
      s2.get("piotroski_f") == 3 and s2.get("piotroski_covered") == "3/9",
      f"F={s2.get('piotroski_f')} covered={s2.get('piotroski_covered')}")
check("同期鎖：missing 含 prev_year 提示", any("prev_year" in x for x in miss2), str(miss2[:2]))

# 項缺不計：金融業無毛利（gp=None）＋缺 CFO → covered 降、不炸
CUR_FIN = dict(CUR, gross_profit_ytd_thousand=None, cfo_ytd_thousand=None)
s3, miss3 = m.compute_piotroski(CUR_FIN, PREV, prev_period_ok=True)
check("金融業（無毛利）＋缺 CFO：F=4 covered=6/9",
      s3.get("piotroski_f") == 4 and s3.get("piotroski_covered") == "6/9",
      f"F={s3.get('piotroski_f')} covered={s3.get('piotroski_covered')} miss={miss3}")

# 全缺 → 無分（0/9 如實，不產生假 0 分）
s4, _ = m.compute_piotroski({}, {}, prev_period_ok=False)
check("全缺輸入→無 piotroski_f（不造假 0 分）", "piotroski_f" not in s4, str(list(s4)))

fails = [r for r in results if not r[1]]
for name, cond, detail in results:
    print(f"{'PASS' if cond else 'FAIL'}  {name}  {detail}")
print(f"\n合計 {len(results)} 項，PASS {len(results) - len(fails)}，FAIL {len(fails)}")
sys.exit(1 if fails else 0)
