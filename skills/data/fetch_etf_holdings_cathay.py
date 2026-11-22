#!/usr/bin/env python3
"""國泰投信官方持股 → data/etf-holdings.json（官方來源升級）。

來源鏈位置：富邦／元大官方 → **國泰官方（本腳本，2026-11-22 新增）** → CMoney → yfinance。
此前國泰系 ~44 檔全靠 CMoney（只有前 10 大）；本腳本改用國泰官方 API 取完整持股。

流程：
  1. GET api/ETF/GetRealTimeEstimateNavList → stockCode→fundCode 對照（44/44，含加掛股共用碼）
  2. GET api/ETF/DownloadETFWeightExcel?FundCode={內部碼}&SearchDate={YYYY/MM/DD} → 官方 Excel
     （ SearchDate 由今天往回試最多 4 天；以 Excel 內「YYYY/MM/DD基金持股權重」日期為 asof ）
  3. 解析完整持股（代號/名稱/股數/權重），更新 data/etf-holdings.json 對應檔
     （entry 結構不變：name/market/issuer/n/src/asof/items/n_listed；src='CATHAY'）

用法：/root/venvs/quant/bin/python3 skills/data/fetch_etf_holdings_cathay.py [--dry-run]
注意：需要 pandas/openpyxl（quant venv）。無效 FundCode 的特徵是 HTTP 200 + 0 bytes。
"""
import io
import json
import re
import sys
import time
import datetime as dt
from pathlib import Path

import requests

try:
    import pandas as pd
except ImportError:
    sys.exit("需要 pandas＋openpyxl（請用 /root/venvs/quant/bin/python3 執行）")

ROOT = Path(__file__).resolve().parents[2]
HOLDINGS_PATH = ROOT / "data" / "etf-holdings.json"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
BASE = "https://cwapi.cathaysite.com.tw/api/ETF"
DELAY = 0.35  # 禮貌間隔
BREAK_WORDS = {"項目", "債券", "基金代號", "現金", "合計", "小計"}
BACK_DAYS = 4


def get_fundcode_map():
    """GetRealTimeEstimateNavList → {stockCode: fundCode}（全部國泰 ETF）。"""
    r = requests.get(f"{BASE}/GetRealTimeEstimateNavList", headers=UA, timeout=20)
    r.raise_for_status()
    d = r.json()
    if d.get("returnCode") != "2000":
        raise RuntimeError(f"GetRealTimeEstimateNavList returnCode={d.get('returnCode')}")
    return {x.get("stockCode"): x.get("fundCode")
            for x in (d.get("result") or [])
            if x.get("stockCode") and x.get("fundCode")}


def fetch_excel(fund_code):
    """由今天往回試 SearchDate；回 (df, asof) 或 (None, None)。"""
    today = dt.date.today()
    for back in range(BACK_DAYS):
        day = today - dt.timedelta(days=back)
        r = requests.get(f"{BASE}/DownloadETFWeightExcel",
                         params={"FundCode": fund_code, "SearchDate": day.strftime("%Y/%m/%d")},
                         headers=UA, timeout=20)
        if r.status_code != 200 or len(r.content) < 1000:
            continue
        try:
            df = pd.read_excel(io.BytesIO(r.content), header=None)
        except Exception:
            continue
        if df.empty:
            continue
        return df, day
    return None, None


def parse_excel(df):
    """解析官方 Excel → (items, asof, extra)。items=[[代碼,名稱,權重],…]（完整清單，不截斷）。"""
    if df is None or df.empty:
        return None, None, None
    # ⚠️ pandas 3.0 的 astype(str) 會保留 NaN 為 float（str dtype 語義）——必須逐格轉換
    flat = [[("" if pd.isna(c) else str(c)) for c in row] for row in df.values.tolist()]

    # 1) 持股基準日：找「YYYY/M/D 基金持股權重」
    asof = None
    for row in flat[:12]:
        for cell in row:
            m = re.search(r"(\d{4}/\d{1,2}/\d{1,2})\s*基金持股權重", str(cell))
            if m:
                asof = dt.datetime.strptime(m.group(1), "%Y/%m/%d").date().isoformat()
                break
        if asof:
            break

    # 2) 表頭列：同時含「股票代號」「股票名稱」
    start = None
    for i, row in enumerate(flat):
        vals = [c.strip() for c in row if c and c.strip() not in ("nan", "None")]
        if any("股票代號" in v for v in vals) and any("股票名稱" in v for v in vals):
            start = i + 1
            break
    if start is None:
        return None, asof, None

    # 3) 資料列（讀到斷行詞或空列）
    items = []
    for row in flat[start:]:
        code = str(row[0]).strip() if len(row) > 0 else ""
        name = str(row[1]).strip() if len(row) > 1 else ""
        if code in ("", "nan", "None"):
            continue
        if code in BREAK_WORDS or any(w in name for w in ("合計", "小計")):
            break
        try:
            weight = float(str(row[3]).replace("%", "").replace(",", "").strip())
        except (ValueError, IndexError, TypeError):
            continue  # 無權重的列不收（寧缺勿假）
        try:
            shares = float(str(row[2]).replace(",", "").strip())
        except (ValueError, TypeError):
            shares = None
        items.append([code, name, weight])

    # 4) 附加資訊：每單位淨值（官方值，供對照）
    nav = None
    for row in flat:
        for j, cell in enumerate(row):
            if "基金每單位淨值" in str(cell):
                tail = [str(c) for c in row[j:] if c and str(c) != "nan"]
                m = re.search(r"NT\$?\s*([\d.]+)", " ".join(tail))
                if m:
                    nav = float(m.group(1))
                break
        if nav is not None:
            break

    if not items:
        return None, asof, None
    return items, asof, {"nav": nav}


def main():
    dry = "--dry-run" in sys.argv
    with open(HOLDINGS_PATH, encoding="utf-8") as f:
        doc = json.load(f)
    holdings = doc.get("holdings") or {}
    syms = sorted(holdings.keys())
    print(f"[cathay] etf-holdings.json 現有 {len(syms)} 檔")

    fc_map = get_fundcode_map()
    print(f"[cathay] 官方對照表：{len(fc_map)} 檔（GetRealTimeEstimateNavList）")
    targets = [s for s in syms if s in fc_map]
    print(f"[cathay] 可升級為官方來源：{len(targets)} 檔")

    ok, fail = [], []
    stats = {"rows": 0, "navs": 0}
    for i, sym in enumerate(targets, 1):
        fc = fc_map[sym]
        df, tried_day = fetch_excel(fc)
        items, asof, extra = parse_excel(df)
        if not items:
            fail.append(sym)
            print(f"  [{i}/{len(targets)}] {sym}（{fc}）❌ 無持股資料")
        else:
            ok.append(sym)
            stats["rows"] += len(items)
            if extra and extra.get("nav"):
                stats["navs"] += 1
            if not dry:
                e = holdings.get(sym) or {}
                holdings[sym] = {
                    "name": e.get("name") or "",
                    "market": e.get("market") or "TWSE",
                    "issuer": "國泰投信",
                    "n": len(items),
                    "src": "CATHAY",
                    "asof": asof or (tried_day.isoformat() if tried_day else None),
                    "items": items,
                    "n_listed": len(items),
                }
            print(f"  [{i}/{len(targets)}] {sym}（{fc}）✅ {len(items)} 檔持股, asof={asof}, 官方淨值={extra.get('nav') if extra else None}")
        time.sleep(DELAY)

    print(f"\n[cathay] 成功 {len(ok)}／失敗 {len(fail)}；總持股列數 {stats['rows']}；含官方淨值 {stats['navs']} 檔")
    if fail:
        print(f"[cathay] 失敗清單: {fail}")
    if dry:
        print("[cathay] --dry-run：未寫入")
        return 0
    if ok:
        doc["holdings"] = holdings
        # 來源分布
        from collections import Counter
        src_count = Counter((v or {}).get("src") for v in holdings.values())
        doc.setdefault("meta", {})["src_counts"] = dict(src_count)
        doc["meta"]["note"] = ("n = 可證實的成份股總數（官方直出完整清單者）；只取得權重前 10 大、"
                               "無法證實總數時為 null。src：CATHAY/FUBON/YUANTA＝投信官方直出，"
                               "CMoney＝第三方備援（前 10 大），YFINANCE＝yfinance 備援。")
        out = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        HOLDINGS_PATH.write_bytes(out)
        print(f"[cathay] ✅ 已寫入 {HOLDINGS_PATH}（{len(out)/1024:.0f} KB），src_counts={dict(src_count)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
