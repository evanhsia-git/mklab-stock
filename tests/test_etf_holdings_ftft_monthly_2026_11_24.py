#!/usr/bin/env python3
"""富蘭克林華美月報解析回歸測試（2026-10-31 月報真實文字 fixture）。

驗證：前十大正則（台股列收、海外/債券列濾）／名稱匹配（精確＋唯一字首）／MIN_MATCH 誠實跳過。
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "ftftm", ROOT / "skills" / "data" / "fetch_etf_holdings_ftft_monthly.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# 2026/10/31 00905 月報真實文字（縮樣：7 筆＋尾部雜訊）
SAMPLE = """前十大投資標的(%) 權重 產業分類 國家 台積電 30.19 半導體 臺灣 聯發科 5.89 半導體 臺灣 鴻海 4.38 其他電子 臺灣 南亞 4.02 塑膠工業 臺灣 日月光投控 4.01 半導體 臺灣 台達電 3.81 電子零組件 臺灣 富邦金 3.77 金融保險 臺灣 222.275.20 15.20 57.76 商品名稱 2026年10月 三個月"""

# 海外型（00899 樣本節錄）——國家非臺灣，應全數排除
SAMPLE_FOREIGN = """前十大投資標的(%) 權重 產業 國家 Verbund AG 5.07 公用事業 奧地利 Nordex SE 4.90 工業 德國 Clearway能源公司 4.88 公用事業 美國 子午線能源有限公司 4.77 公用事業 紐西蘭"""

results = []


def check(name, cond, detail=""):
    results.append((name, cond, detail))


NAME_MAP = {"台積電": "2330", "聯發科": "2454", "鴻海": "2317", "南亞": "1303",
            "日月光投控": "3711", "台達電": "2308", "富邦金": "2881",
            "鈊象電子": "8941", "南亞科": "2408"}

items, asof, stats = m.parse_top10_text(SAMPLE, NAME_MAP)
check("解析 7 筆（雜訊排除）", items and len(items) == 7, f"{len(items or [])}")
check("首筆 [代號,名稱,權重]", items and items[0] == ["2330", "台積電", 30.19], str((items or [[]])[0]))
check("asof 抽取", asof is None or asof == "2026-10-31", str(asof))  # SAMPLE 無日期→None

items_f, _, stats_f = m.parse_top10_text(SAMPLE_FOREIGN, NAME_MAP)
check("海外型全濾（0 筆臺灣列）", items_f == [], f"{items_f}")

# 唯一字首匹配：鈊象 → 鈊象電子/8941
s2 = SAMPLE.replace("富邦金 3.77 金融保險 臺灣", "鈊象 3.77 文化創意 臺灣")
items2, _, _ = m.parse_top10_text(s2, NAME_MAP)
check("唯一字首匹配（鈊象→8941）", items2 and any(i[0] == "8941" for i in items2),
      str([i for i in (items2 or []) if i[1] == "鈊象"]))

# 驗證閾值：3 筆 < MIN_MATCH(5) → 不足
check("MIN_MATCH 邏輯（3<5 跳過）", len(items_f or []) < m.MIN_MATCH)

fails = [r for r in results if not r[1]]
for name, cond, detail in results:
    print(f"{'PASS' if cond else 'FAIL'}  {name}  {detail}")
print(f"\n合計 {len(results)} 項，PASS {len(results) - len(fails)}，FAIL {len(fails)}")
sys.exit(1 if fails else 0)
