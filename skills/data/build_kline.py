#!/usr/bin/env python3
"""
個股 K 線小檔產生（Build-Time）：為 data/stocks.json 內每檔股票輸出 data/kline/{代號}.json。
來源：data/history/ 近約一年的日快照（已套用離群值過濾）。格式：{"sym","asof","fields","rows":[[日期,開,高,低,收],...]}
缺高低價或開盤價的日子，以收盤價補值（不推測其他數字）。
"""
import datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compute_indicators import load_series


def merge_kline_rows(path, new_rows):
    """與既有 K 線檔合併（以日期為鍵，新資料優先）。

    為什麼需要：本檔只從 data/history/（約 366 天）重建 K 線，若某代號的既有檔案含有
    更長的歷史（例如 skills/data/backfill_etf_history.py 補的「上市以來」日線），
    直接覆寫會把長歷史截短成一年。合併可確保既有較早的資料不會被每日重建吃掉。
    """
    if not os.path.exists(path):
        return new_rows
    try:
        old = json.load(open(path, encoding="utf-8")).get("rows", [])
    except (OSError, json.JSONDecodeError):
        return new_rows
    if not old:
        return new_rows
    by_date = {r[0]: r for r in old}
    for r in new_rows:
        by_date[r[0]] = r  # 重建結果來自官方歷史快照，優先於既有值
    return [by_date[d] for d in sorted(by_date)]
def strip_padded_prefix(rows, min_run=3):
    """移除開頭「連續同價且完全平盤」的補值列（2026-11-12 新增）。

    為什麼需要：merge_kline_rows() 會保留既有 K 線檔內、history/ 已經沒有的更早資料
    （原本是為了保護 backfill_etf_history.py 補的「上市以來」長歷史），但這也讓
    **已被清除的偽造補值列在 K 線檔裡存活下來**。實測：009816 凱基台灣TOP50 的
    history 已正確從 2026-02-03（close 10.27）起，kline 卻仍留著 142 天
    close=15.0 的假列 → research 頁 YTD 基準價算成 15 元。

    判定：開頭連續 >= min_run 天都 o=h=l=c 且 close 與首列完全相同 → 視為補值。
    ⚠️ K 線檔沒有 volume 欄，只能用價格形狀判斷；真實的一字漲/跌停連續天數
      價格會逐日變動（天天漲停＝每天不同價），不會「同價」連續 3 天以上，
      所以不會誤殺。全部為 null 的空佔位列也適用（None == None）。
    """
    if len(rows) < min_run:
        return rows
    c0 = rows[0][4]
    n = 0
    for r in rows:
        if r[1] == r[2] == r[3] == r[4] == c0:
            n += 1
        else:
            break
    return rows[n:] if n >= min_run else rows


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "kline")
os.makedirs(OUT, exist_ok=True)
doc = json.load(open(os.path.join(ROOT, "data", "stocks.json"), encoding="utf-8"))
asof = doc["meta"]["as_of"]
series = load_series(limit=None)  # K 線吃 history/ 全部，不受指標用的 280 日回看限制
n = 0; total = 0
for s in doc["stocks"]:
    rows = series.get(s["sym"])
    if not rows:
        continue
    # 2026-11-09：不再用「最後一天 −366 日曆天」截斷。
    # 舊版會把 history/ 已經有的資料整段丟掉（實測 2330 少了 71 個交易日：
    # history/ 有 316 天、kline/ 只剩 245 天），因為 366 日曆天 ≈ 只有 245 個交易日。
    # data/history/ 本身就是本站的行情真相來源，這裡全數採用；長度由 history/ 決定。
    out = []
    for d, o, h, l, c in rows:
        out.append([f"{d[:4]}-{d[4:6]}-{d[6:8]}", o if o is not None else c, h if h is not None else c, l if l is not None else c, c])
    if not out:
        continue
    path = os.path.join(OUT, f"{s['sym']}.json")
    out = merge_kline_rows(path, out)  # 不讓只有近一年的重建結果截短既有長歷史
    out = strip_padded_prefix(out)     # 但 merge 保留的舊資料也要剔除「前導補值列」
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"sym": s["sym"], "asof": asof, "fields": ["date", "open", "high", "low", "close"], "rows": out}, f, ensure_ascii=False, separators=(",", ":"))
    n += 1; total += len(out)
print(f"個股 K 線檔 {n} 檔，共 {total} 筆（資料日 {asof}）")
