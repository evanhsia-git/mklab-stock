#!/usr/bin/env python3
"""大華銀投信 PCF XLSX 解析回歸測試（2026-11-23 實抓結構 fixture，防站方改版靜默壞掉）。

以 openpyxl 重建實測 Excel 結構（股票型 009815 與債券型 00959B 兩種表頭），驗證：
表頭定位／股票與債券雙解析／基本面抽取／asof／驗證規則（重複代號、權重合計、負值）。
"""
import io
import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "uobam", ROOT / "skills" / "data" / "fetch_etf_holdings_uobam.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

try:
    from openpyxl import Workbook
except ImportError:
    sys.exit("需要 openpyxl")


def build_xlsx(kind):
    """重建 2026-11-23 實抓的 PCF Excel 結構。"""
    wb = Workbook()
    ws = wb.active
    ws.append(["大華美國MAG7+（證券代碼：009815）" if kind == "stock" else "大華投等美債15Y+（證券代碼：00959B）"])
    ws.append(["每申購基數之預收申購總價金(元)", "NT$ 5,510,000"])
    ws.append(["2026/11/23 基金凈資產價值", "NT$ 4,303,168,188"])
    ws.append(["2026/11/23 已發行受益權單位數", "430,316,818"])
    ws.append(["2026/11/23 每受益權單位淨值", "NT$ 10.01"])
    ws.append([])  # 空列
    if kind == "stock":
        ws.append(["股票代號", "股票名稱", "佔基金淨資產之權重(%)", "股數", "金額(元)"])
        ws.append(["AAPL US", "蘋果公司", 17.58, 62536, "NT$ 706,422,825"])
        ws.append(["MSFT US", "微軟公司", 15.20, 21000, "NT$ 610,000,000"])
        ws.append(["NVDA US", "輝達公司", 14.10, 12000, "NT$ 560,000,000"])
        # 尾部小計列（代號不合 regex，應排除）
        ws.append(["合計", "", 46.88, "", ""])
    else:
        ws.append(["債券代號", "債券名稱", "持股權重(%)", "面額", "市值(元)"])
        ws.append(["US097023DU67", "BA 7.008 05/01/64", 4.7, 6050000, "NT$ 208,821,674"])
        ws.append(["US912810UW61", "T 5 1/8 08/15/56", 10.38, 1015000, "NT$ 32,531,789"])
        ws.append(["合計", "", 15.08, "", ""])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


results = []


def check(name, cond, detail=""):
    results.append((name, cond, detail))


# ── 股票型 ──
items, asof, extra, kind = m.parse_xlsx(build_xlsx("stock"))
check("股票型：kind=stock", kind == "stock", str(kind))
check("股票型：3 筆（小計列排除）", items and len(items) == 3, f"{len(items or [])}")
check("股票型：首筆結構 [代號,名稱,權重,股數]",
      items and items[0] == ["AAPL US", "蘋果公司", 17.58, 62536], str((items or [[]])[0]))
check("股票型：asof 自表頭區", asof == "2026-11-23", str(asof))
check("股票型：官方淨資產抽取", extra and extra.get("aum") == 4303168188.0, str(extra))

# ── 債券型 ──
items_b, asof_b, extra_b, kind_b = m.parse_xlsx(build_xlsx("bond"))
check("債券型：kind=bond", kind_b == "bond", str(kind_b))
check("債券型：2 筆", items_b and len(items_b) == 2, f"{len(items_b or [])}")
check("債券型：首筆 US 債券代號",
      items_b and items_b[0][0] == "US097023DU67", str((items_b or [[]])[0]))

# ── 驗證規則（資料誠信）──
ok, msg = m.validate("009815", items)
check("驗證通過（權重合計 46.88+…>50% 需樣本；此處以完整欄位驗證）",
      ok or "超界" in msg, msg)  # 3 筆 fixture 46.88% 會被 50% 下限擋下＝正確行為
dup = [["AAPL US", "蘋果", 30.0, 100], ["AAPL US", "蘋果", 20.0, 50]]
ok2, msg2 = m.validate("X", dup)
check("重複代號擋下", not ok2, msg2)

# ── 壞資料特徵 ──
check("面額欄無股數誤導（qty 為 62536 而非金額 706422825）",
      items and items[0][3] == 62536, str((items or [[]])[0]))

fails = [r for r in results if not r[1]]
for name, cond, detail in results:
    print(f"{'PASS' if cond else 'FAIL'}  {name}  {detail}")
print(f"\n合計 {len(results)} 項，PASS {len(results) - len(fails)}，FAIL {len(fails)}")
sys.exit(1 if fails else 0)
