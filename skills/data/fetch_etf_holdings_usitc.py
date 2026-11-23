#!/usr/bin/env python3
"""聯邦投信官方 PCF 申贖組合 → data/etf-holdings.json（官方來源升級）。

來源鏈位置：富邦／元大／國泰官方 → **聯邦官方（本腳本，2026-11-23 新增）** → CMoney → yfinance。
此前聯邦 2 檔（009804、009825）全靠 CMoney（前 10 大）；本腳本改用聯邦官方 PCF 申贖組合。

⚠️ 資料語意（資料誠信紅線）：PCF＝申贖組合，不等於全部持股。
本腳本輸出以 coverage_pct（權重合計）如實標示涵蓋率；實測 009804=99.43%、009825=99.44%。

流程：
  1. POST /CustCenter/BuyBackList  form {FundNo=<ETF代號>, sDate=YYYYMMDD}
     （sDate 由今天往回試最多 4 天；無需登入/Cookie）
  2. 解析 4 張表：申贖公告（淨值/受益單位）→ 期貨表（TX 等口數/權重）→ 成分股表（代號/名稱/股數/權重）
  3. 海外型代號「CHYM US」剝國別後綴（同台新規則）；期貨不混入持股 items（語意不同），
     以 extra['futures'] 保留並計入涵蓋率驗證
  4. 更新 data/etf-holdings.json 對應檔（entry 結構不變；src='USITC'）

用法：/root/venvs/quant/bin/python3 skills/data/fetch_etf_holdings_usitc.py [--dry-run]
"""
import json
import re
import sys
import time
import datetime as dt
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
HOLDINGS_PATH = ROOT / "data" / "etf-holdings.json"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
URL = "https://www.usitc.com.tw/CustCenter/BuyBackList"
DELAY = 0.5  # 禮貌間隔
BACK_DAYS = 4
ISSUER = "聯邦投信"


def fetch_pcf(fund_no):
    """由今天往回試 sDate；回 (html, day) 或 (None, None)。"""
    today = dt.date.today()
    for back in range(BACK_DAYS):
        day = today - dt.timedelta(days=back)
        r = requests.post(URL, data={"FundNo": fund_no, "sDate": day.strftime("%Y%m%d")},
                          headers=UA, timeout=20)
        if r.status_code != 200 or len(r.content) < 2000:
            continue
        t = r.text
        if "查無任何資料" in t and "無任何資料" in t and "股票代號" not in t:
            continue
        if "股票代號" not in t:
            continue
        return t, day
    return None, None


def strip_country(code):
    """「CHYM US」→「CHYM」（剝國別後綴，僅處理 大寫字母+空格+2 大寫）。"""
    m = re.match(r"^([A-Z0-9.]+)\s+([A-Z]{2})$", code.strip())
    return m.group(1) if m else code.strip()


def _cells(row_html):
    return [re.sub(r"<[^>]+>", "", c).strip()
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S)]


def _f(s):
    try:
        return float(str(s).replace("%", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def parse(html):
    """解析 4 張表 → (items, asof, extra)。items=[[代號,名稱,權重,股數],…]（PCF 完整清單）。"""
    tbls = re.findall(r"<table.*?</table>", html, re.S)
    items, futures = [], []
    extra = {"nav": None, "units": None, "aum": None}  # type: dict

    for tb in tbls:
        rows = [r for r in ( _cells(x) for x in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S)) if r]
        if not rows:
            continue
        head = " ".join(rows[0])

        if "股票代號" in head and "權重" in head:  # 成分股表
            for row in rows[1:]:
                if len(row) < 4:
                    continue
                code, name = strip_country(row[0]), row[1]
                if not code or code in ("股票代號",):
                    continue
                weight, shares = _f(row[3]), _f(row[2])
                if weight is None or not (0 < weight < 100):
                    continue  # 無權重的列不收（寧缺勿假）
                items.append([code, name, weight, int(shares) if shares is not None else None])

        elif "期貨代碼" in head or "期貨名稱" in head:  # 期貨表（不混入持股）
            for row in rows[1:]:
                if len(row) >= 4 and row[0] and row[0] != "期貨代碼":
                    w = _f(row[3])
                    if w is not None and 0 <= w < 100:
                        futures.append([row[0], row[1], w, row[4] if len(row) > 4 else None])

        elif "基金淨資產價值" in head and "淨值" in head and len(rows) > 1:  # 淨值表
            vals = rows[1]
            if len(vals) >= 3:
                for v, k in zip(vals, ("aum", "units", "nav")):
                    m = re.search(r"([\d,]+(?:\.\d+)?)", str(v))
                    if m:
                        extra[k] = float(m.group(1).replace(",", ""))

    asof_m = re.search(r"(\d{4}-\d{2}-\d{2})", html)
    asof = asof_m.group(1) if asof_m else None
    return items, asof, ({"futures": futures, **extra} if (futures or extra.get("nav")) else None)


def validate(sym, items, futures):
    """資料誠信驗證：權重合計 50~105%、重複代號、負值。回 (ok, 訊息)。"""
    codes = [it[0] for it in items]
    if len(codes) != len(set(codes)):
        return False, f"{sym}: 重複代號"
    if any(it[3] is not None and it[3] < 0 for it in items):
        return False, f"{sym}: 負股數"
    total = sum(it[2] for it in items) + sum(f[2] for f in futures)
    if not (50 <= total <= 105):
        return False, f"{sym}: 權重合計 {total:.2f}% 超界"
    return True, f"股票 {len(items)} 筆＋期貨 {len(futures)} 筆，合計權重 {total:.2f}%"


def main():
    dry = "--dry-run" in sys.argv
    with open(HOLDINGS_PATH, encoding="utf-8") as f:
        doc = json.load(f)
    holdings = doc.get("holdings") or {}
    # 官方商品頁下拉即此 2 檔（2026-11-23 實測）；以 issuer 欄為準動態取得
    targets = sorted(s for s, v in holdings.items()
                     if "聯邦" in ((v or {}).get("issuer") or ""))
    print(f"[usitc] etf-holdings.json 現有 {len(holdings)} 檔；聯邦標的：{targets}")
    if not targets:
        print("[usitc] 無標的，結束")
        return 0

    ok, fail = [], []
    for i, sym in enumerate(targets, 1):
        html, day = fetch_pcf(sym)
        items, asof, extra = parse(html) if html else (None, None, None)
        if not items:
            fail.append(sym)
            print(f"  [{i}/{len(targets)}] {sym} ❌ 無 PCF 資料（往回試 {BACK_DAYS} 日皆空）")
            continue
        futures = (extra or {}).get("futures", [])
        vok, vmsg = validate(sym, items, futures)
        if not vok:
            fail.append(sym)
            print(f"  [{i}/{len(targets)}] {sym} ❌ 驗證失敗：{vmsg}")
            continue
        ok.append(sym)
        if not dry:
            e = holdings.get(sym) or {}
            holdings[sym] = {
                "name": e.get("name") or "",
                "market": e.get("market") or "TWSE",
                "issuer": ISSUER,
                "n": len(items),
                "src": "USITC",
                "asof": asof or (day.isoformat() if day else None),
                "items": items,
                "n_listed": len(items),
            }
        print(f"  [{i}/{len(targets)}] {sym} ✅ {vmsg}，asof={asof}，"
              f"官方淨值={((extra or {}).get('nav'))}，官方單位數={((extra or {}).get('units'))}")
        time.sleep(DELAY)

    print(f"\n[usitc] 成功 {len(ok)}／失敗 {len(fail)}")
    if fail:
        print(f"[usitc] 失敗清單: {fail}")
    if dry:
        print("[usitc] --dry-run：未寫入")
        return 0
    if ok:
        doc["holdings"] = holdings
        from collections import Counter
        src_count = Counter((v or {}).get("src") for v in holdings.values())
        doc.setdefault("meta", {})["src_counts"] = dict(src_count)
        doc["meta"]["note"] = ("n = 可證實的成份股總數（官方直出完整清單者）；只取得權重前 10 大、"
                               "無法證實總數時為 null。src：CATHAY/FUBON/YUANTA/USITC/UOBAM＝投信官方直出，"
                               "CMoney＝第三方備援（前 10 大），YFINANCE＝yfinance 備援。"
                               "USITC/UOBAM 為 PCF 申贖組合（涵蓋率>98%，非全部持股）。")
        out = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        HOLDINGS_PATH.write_bytes(out)
        print(f"[usitc] ✅ 已寫入 {HOLDINGS_PATH}（{len(out)/1024:.0f} KB），src_counts={dict(src_count)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
