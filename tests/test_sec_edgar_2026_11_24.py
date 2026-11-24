#!/usr/bin/env python3
"""fetch_sec_edgar 解析與評分回歸測試（迷你 companyfacts fixture＋手算對照）。

驗證：FY/10-K/duration 過濾、窄 tag 先佔、filed 較新勝出、股數防呆、
Piotroski 9 項手算、Altman Z 手算、缺輸入→null＋missing_inputs 如實（null 不補值）。
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sec_edgar", ROOT / "skills" / "data" / "fetch_sec_edgar.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

results = []


def check(name, cond, detail=""):
    results.append((name, cond, detail))


def fact(start, end, val, form="10-K", fp="FY", filed="2026-02-01", unit="USD"):
    return {"start": start, "end": end, "val": val, "form": form, "fp": fp, "filed": filed, "unit": unit}


# 迷你 fixture：FY2025（end 2025-12-31）與 FY2024（end 2024-12-31）
CF = {"facts": {"us-gaap": {
    "Revenues": {"units": {"USD": [
        fact("2025-01-01", "2025-12-31", 1000),
        fact("2024-01-01", "2024-12-31", 900),
        fact("2025-10-01", "2025-12-31", 300, form="10-Q", fp="Q4"),  # 季度→丟
        fact("2025-01-01", "2025-09-30", 700, form="10-Q"),           # YTD→丟
    ]}},
    # 窄 tag 先佔：RevenueFromContract... 在 Revenues 之後列出，但同週期窄 tag 應該不搶已佔欄？
    # crible 規則＝映射表順序即優先序（Revenues 在前先佔）→ TotalRevenue=1000
    "GrossProfit": {"units": {"USD": [
        fact("2025-01-01", "2025-12-31", 400),
        fact("2024-01-01", "2024-12-31", 320),
    ]}},
    "NetIncomeLoss": {"units": {"USD": [
        fact("2025-01-01", "2025-12-31", 120),
        fact("2024-01-01", "2024-12-31", 100),
    ]}},
    "OperatingCashFlow": {"units": {"USD": [  # 概念名以實際 tag 為準
        fact("2025-01-01", "2025-12-31", 150),
    ]}},
    "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [
        fact("2025-01-01", "2025-12-31", 150),
        fact("2024-01-01", "2024-12-31", 130),
    ]}},
    "Assets": {"units": {"USD": [
        fact("2025-01-01", "2025-12-31", 5000),   # 時點事實也掛 FY 標籤（10-K 全期）
        fact("2024-01-01", "2024-12-31", 4500),
    ]}},
    "Liabilities": {"units": {"USD": [
        fact("2025-01-01", "2025-12-31", 2000),
        fact("2024-01-01", "2024-12-31", 2100),   # 槓桿下降
    ]}},
    "AssetsCurrent": {"units": {"USD": [
        fact("2025-01-01", "2025-12-31", 1200),
        fact("2024-01-01", "2024-12-31", 1100),
    ]}},
    "LiabilitiesCurrent": {"units": {"USD": [
        fact("2025-01-01", "2025-12-31", 600),
        fact("2024-01-01", "2024-12-31", 700),    # 流動比 2.0 → 2.0？1200/600=2.0, 1100/700=1.571 升 ✓
    ]}},
    "RetainedEarningsAccumulatedDeficit": {"units": {"USD": [
        fact("2025-01-01", "2025-12-31", 1500),
    ]}},
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": {"units": {"USD": [fact("2025-01-01", "2025-12-31", 160)]}},
    "InterestExpense": {"units": {"USD": [fact("2025-01-01", "2025-12-31", 20)]}},
    "CommonStockSharesOutstanding": {"units": {"shares": [
        fact("2025-01-01", "2025-12-31", 100_000, unit="shares"),
        fact("2024-01-01", "2024-12-31", 100_000, unit="shares"),  # 未增發
    ]}},
    "CommonStockSharesOutstandingBad": {"units": {"shares": [
        fact("2025-01-01", "2025-12-31", 713, unit="shares"),  # <10,000 防呆測（非映射概念，僅示意）
    ]}},
}}}

years = m.parse_companyfacts(CF)
check("年度數＝2（10-Q/YTD 丟）", len(years) == 2, f"{sorted(years)}")
y25 = years.get("2025-12-31") or {}
check("TotalRevenue 先佔制＝1000", y25.get("TotalRevenue") == 1000, str(y25.get("TotalRevenue")))
check("OCF 取 NetCashProvidedByUsedInOperatingActivities", y25.get("OperatingCashFlow") == 150,
      str(y25.get("OperatingCashFlow")))
check("FY2024 事實在", (years.get("2024-12-31") or {}).get("TotalRevenue") == 900)

# 股數防呆：<10,000 丟（用單獨 fixture 驗證）
CF2 = {"facts": {"us-gaap": {"CommonStockSharesOutstanding": {"units": {"shares": [
    fact("2025-01-01", "2025-12-31", 713, unit="shares"),
]}}}}}
years2 = m.parse_companyfacts(CF2)
check("股數<10,000 丟棄（MCD 單位錯誤防呆）",
      not ((years2.get("2025-12-31") or {}).get("OrdinarySharesNumber")),
      str((years2.get("2025-12-31") or {}).get("OrdinarySharesNumber")))

# ── 評分手算 ──
scores, missing = m.compute_scores(years, price=25.0)
p = scores.get("piotroski_detail") or {}
# ROA: 120/5000=2.4%>0 ✓(1)；CFO 150>0 ✓(1)；ΔROA 2.4% vs 100/4500=2.22% ✓(1)
# CFO 150>NI 120 ✓(1)；槓桿 2000/5000=0.4 < 2100/4500=0.4667 ✓(1)
# 流動比 2.0>1.571 ✓(1)；毛利率 0.4>0.3556 ✓(1)；週轉 0.2>0.2？1000/5000=0.2, 900/4500=0.2 → 相等不升 → 0
# 股數 100k=100k 未增 ✓(1) → F=8
check("Piotroski F＝8（手算）", scores.get("piotroski_f") == 8,
      f"{scores.get('piotroski_f')} detail={p}")
check("Δ週轉＝0（相等不升）", p.get("Δ週轉升") == 0, str(p.get("Δ週轉升")))
check("covered＝9/9", scores.get("piotroski_covered") == "9/9", str(scores.get("piotroski_covered")))
check("EBIT＝Pretax+Interest＝180", scores.get("ebit") == 180, str(scores.get("ebit")))
# Altman：WC=600, RE=1500, TA=5000, EBIT=180, TL=2000, MVE=25×100000=2,500,000, Rev=1000
# Z = 1.2×0.12 + 1.4×0.3 + 3.3×0.036 + 0.6×1250 + 1.0×0.2 = 0.144+0.42+0.1188+750+0.2
z_expect = round(1.2 * 600 / 5000 + 1.4 * 1500 / 5000 + 3.3 * 180 / 5000
                 + 0.6 * 2_500_000 / 2000 + 1.0 * 1000 / 5000, 4)
check("Altman Z 手算對照", scores.get("altman_z") == z_expect,
      f"{scores.get('altman_z')} vs {z_expect}")
check("Sloan＝(120-150)/4750", scores.get("sloan_accruals") == round((120 - 150) / 4750, 6),
      str(scores.get("sloan_accruals")))

# 缺輸入→null 不補（fixture 無 Inventory/Goodwill 等，Altman 有全輸入；造缺 OCF 情境）
CF3 = {"facts": {"us-gaap": {
    "Assets": {"units": {"USD": [fact("2025-01-01", "2025-12-31", 5000), fact("2024-01-01", "2024-12-31", 4500)]}},
    "NetIncomeLoss": {"units": {"USD": [fact("2025-01-01", "2025-12-31", 120), fact("2024-01-01", "2024-12-31", 100)]}},
}}}
years3 = m.parse_companyfacts(CF3)
s3, miss3 = m.compute_scores(years3, price=10.0)
check("缺 OCF→部分評分（covered 如實）＋missing 如實",
      s3.get("piotroski_f") == 2 and s3.get("piotroski_covered") == "2/9"
      and any("OperatingCashFlow" in x for x in miss3),
      f"F={s3.get('piotroski_f')} covered={s3.get('piotroski_covered')} miss={miss3[:3]}")
check("sloan 缺輸入→null", "sloan_accruals" not in s3, str(s3.get("sloan_accruals")))

fails = [r for r in results if not r[1]]
for name, cond, detail in results:
    print(f"{'PASS' if cond else 'FAIL'}  {name}  {detail}")
print(f"\n合計 {len(results)} 項，PASS {len(results) - len(fails)}，FAIL {len(fails)}")
sys.exit(1 if fails else 0)
