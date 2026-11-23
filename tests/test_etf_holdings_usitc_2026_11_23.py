#!/usr/bin/env python3
"""聯邦投信 PCF 解析回歸測試（2026-11-23 實抓結構 fixture，防站方改版靜默壞掉）。"""
import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "usitc", ROOT / "skills" / "data" / "fetch_etf_holdings_usitc.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# ── 真實頁面結構 fixture（2026-11-24 實抓縮樣）──
HTML = """
<table><tr><td>現金申購買回清單公告</td></tr>
<tr><td>基金淨資產價值(元)</td><td>NT$ 2,779,169,815</td></tr></table>
<table><tr><td>基金淨資產價值</td><td>基金在外流通單位數</td><td>基金每單位淨值</td></tr>
<tr><td>NT$ 2,779,169,815</td><td>159,392,000</td><td>NT$ 17.44</td></tr></table>
<table><tr><td>期貨代碼</td><td>期貨名稱</td><td>口數</td><td>權重(%)</td><td>契約年月</td></tr>
<tr><td>TX</td><td>台指期貨</td><td>2</td><td>0.5153</td><td>202612</td></tr></table>
<table><tr><td>股票代號</td><td>股票名稱</td><td>股數</td><td>權重(%)</td></tr>
<tr><td>2330</td><td>台積電</td><td>453,653</td><td>32.6467</td></tr>
<tr><td>2454</td><td>聯發科</td><td>83,665</td><td>10.0849</td></tr>
<tr><td>2317</td><td>鴻海</td><td>703,887</td><td>5.3187</td></tr>
<tr><td>2308</td><td>台達電</td><td>111,322</td><td>3.6050</td></tr>
<tr><td>查無任何資料</td></tr></table>
<p>資料日期：2026-11-20</p>
"""

results = []


def check(name, cond, detail=""):
    results.append((name, cond, detail))


# 1) 解析：成分股＋期貨分離、淨值/單位數入 extra
items, asof, extra = m.parse(HTML)
check("成分股 4 筆", items and len(items) == 4, f"{len(items or [])}")
check("items 首筆結構 [代號,名稱,權重,股數]",
      items and items[0] == ["2330", "台積電", 32.6467, 453653], str((items or [[]])[0]))
check("期貨不混入持股", items and all(i[0] != "TX" for i in items))
check("期貨入 extra", extra and extra.get("futures") and extra["futures"][0][0] == "TX",
      str(extra.get("futures") if extra else None))
check("官方淨值/單位數", extra and extra.get("nav") == 17.44 and extra.get("units") == 159392000.0,
      str({k: v for k, v in (extra or {}).items() if k != "futures"}))
check("asof 取頁面日期", asof == "2026-11-20", str(asof))

# 2) 海外代號剝國別後綴（同台新規則）
check("CHYM US → CHYM", m.strip_country("CHYM US") == "CHYM")
check("本國代號不動", m.strip_country("2330") == "2330")
check("含點代號不動", m.strip_country("BRK.B US") == "BRK.B")

# 3) 驗證規則（資料誠信）
ok, msg = m.validate("009804", items, (extra or {}).get("futures", []))
check("驗證通過（權重合計含期貨 99.95%）", ok, msg)
dup = [["2330", "台積電", 50.0, 100], ["2330", "台積電", 30.0, 50]]
ok2, msg2 = m.validate("X", dup, [])
check("重複代號擋下", not ok2, msg2)
over = [["2330", "台積電", 200.0, 100]]
ok3, msg3 = m.validate("X", over, [])
check("權重合計超界擋下", not ok3, msg3)

# 4) 壞資料特徵（「查無任何資料」列不收）
check("查無列不收", all(i[0] != "查無任何資料" for i in items))

fails = [r for r in results if not r[1]]
for name, cond, detail in results:
    print(f"{'PASS' if cond else 'FAIL'}  {name}  {detail}")
print(f"\n合計 {len(results)} 項，PASS {len(results) - len(fails)}，FAIL {len(fails)}")
sys.exit(1 if fails else 0)
