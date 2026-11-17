#!/usr/bin/env python3
"""ETF 發行張數／受益權單位自動更新腳本（2026-11-16 導入）

策略（ Ivan 方案 A，根治 etf-shares.json 人工維護過期）：
- 優先抓取官方來源：
  - TWSE: https://openapi.twse.com.tw/v1/opendata/t187ap47_L （278 檔，含「發行單位數/轉換數」＝受益權單位數）
  - TPEx: https://info.tpex.org.tw/api/etfFilter （118 檔，官方 ETF 宣告；此端點不含發行單位數，shares_stock 留 null，絕不捏造）
- 任一來源失敗時，保留既有 etf-shares.json（不覆寫成空白檔）
- 產出型式與既有 data/etf-shares.json 完全相容：
  etf[code] = {name, full_name, market, shares, unit="張", shares_stock}
  market_cap（億元）由 fetch_data.py 估算：price * shares_stock / 100,000,000
"""

import datetime as dt
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(DATA, "raw")
OUT_PATH = os.path.join(DATA, "etf-shares.json")

TWSE_API_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap47_L"
TPEX_API_URL = "https://info.tpex.org.tw/api/etfFilter"
TPEX_API_REFERER = "https://info.tpex.org.tw/ETF/zh/filter.html"

MIN_KEEP_RATIO = 0.8
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def http_get(url, referer=None, timeout=60):
    headers = dict(UA)
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as f:
        return f.read()


def _is_code(sym):
    return sym is not None and len(str(sym)) >= 4 and str(sym).strip() != ""


def _num(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return None if v != v else v
    s = str(v).replace(",", "").strip()
    try:
        f = float(s)
        return f if f == f else None
    except ValueError:
        return None


def fetch_twse():
    """TWSE 官方 openapi t187ap47_L → 基金基本資料（含發行單位數）"""
    body = http_get(TWSE_API_URL)
    rows = json.loads(body.decode("utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("TWSE openapi 回傳 0 檔或非列表")
    out = []
    for r in rows:
        sym = str(r.get("基金代號", "")).strip()
        if not _is_code(sym):
            continue
        raw_units = str(r.get("發行單位數/轉換數", "") or "").replace(",", "").strip()
        units = int(raw_units) if raw_units.isdigit() else None
        out.append({
            "sym": sym,
            "name": r.get("基金簡稱", ""),
            "full_name": r.get("基金中文名稱", ""),
            "market": "TWSE",
            "shares": units // 1000 if units is not None else None,
            "unit": "張",
            "shares_stock": units,
            "source_url": TWSE_API_URL,
        })
    return out, "auto"


def fetch_tpex():
    """TPEx 官方 ETF 宣告（api/etfFilter）→ 名稱與淨資產；無發行單位數官方欄位"""
    body = http_get(TPEX_API_URL, TPEX_API_REFERER, timeout=30)
    payload = json.loads(body.decode("utf-8"))
    if isinstance(payload, list):
        payload = {"data": payload}
    rows = (payload or {}).get("data", []) or []
    out = []
    for r in rows:
        sym = str(r.get("stockNo") or "").strip()
        if not _is_code(sym):
            continue
        out.append({
            "sym": sym,
            "name": str(r.get("stockName") or "").strip() or None,
            "full_name": "",
            "market": "TPEx",
            "shares": None,
            "unit": "張",
            "shares_stock": None,
            "net_assets_100m": _num(r.get("totalAv")),
            "source_url": TPEX_API_URL,
        })
    if not out:
        raise ValueError("TPEx 回傳 0 檔")
    return out, "auto"


def main():
    prev_etf = {}
    prev_twse, prev_tpex = [], []
    if os.path.exists(OUT_PATH):
        prev = json.load(open(OUT_PATH, encoding="utf-8"))
        prev_etf = prev.get("etf", {}) or {}
        prev_twse = [e for e in prev_etf.values() if e.get("market") == "TWSE"]
        prev_tpex = [e for e in prev_etf.values() if e.get("market") == "TPEx"]

    notes, provenance = {}, {}

    # TWSE：官方 API 直接取得（無人工備援，因為此資料只有官方 API 有）
    try:
        twse, provenance["TWSE"] = fetch_twse()
        notes["TWSE"] = f"TWSE 官方 openapi 自動抓取 {len(twse)} 檔"
    except Exception as e:  # noqa: BLE001
        print(f"[warn] TWSE 自動抓取失敗（{e}）", file=sys.stderr)
        twse, provenance["TWSE"] = [], "failed"
        notes["TWSE"] = f"TWSE 自動失敗（{e}）"

    # TPEx：官方 API → 人工備援（raw/tpex_etf.csv）→ 上次結果
    try:
        tpex, provenance["TPEx"] = fetch_tpex()
        notes["TPEx"] = f"TPEx 官方 API 自動抓取 {len(tpex)} 檔"
    except Exception as e:  # noqa: BLE001
        print(f"[warn] TPEx API 失敗（{e}）-> 回退", file=sys.stderr)
        tpex, provenance["TPEx"] = [], "failed"
        notes["TPEx"] = f"TPEx 自動失敗（{e}）"

    if not twse and not tpex:
        print("兩邊都沒有資料，中止不覆寫", file=sys.stderr)
        return 2

    etfs = twse + tpex
    for market, new_rows, prev_rows in (("TWSE", twse, prev_twse), ("TPEx", tpex, prev_tpex)):
        if prev_rows and len(new_rows) < len(prev_rows) * MIN_KEEP_RATIO:
            print(f"{market} 檔數 {len(new_rows)} 少於上次 {len(prev_rows)} 的 "
                  f"{MIN_KEEP_RATIO:.0%}（總計 {len(etfs)}），視為來源異常，中止不覆寫",
                  file=sys.stderr)
            return 2

    transformed = {}
    for r in etfs:
        transformed[r["sym"]] = {k: v for k, v in r.items() if k != "sym"}

    doc = {
        "source": "TWSE openapi t187ap47_L（官方，含發行單位數）＋ TPEx api/etfFilter（官方宣告，無單位數，shares_stock=null）",
        "updated": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d"),
        "note": ("ETF market_cap（億元）= 收盤價 × shares_stock / 100,000,000，由 fetch_data.py 計算。"
                 "TPEx ETF 暫無官方發行單位數 API，shares_stock 為 null，market_cap 待補充；"
                 "本檔案僅紀錄官方可驗證之發行張數，絕不捏造。"),
        "etf": transformed,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    print(f"✅ 已寫入 {OUT_PATH}（共 {len(transformed)} 檔，TWSE {len(twse)}({provenance['TWSE']}) + TPEx {len(tpex)}({provenance['TPEx']})）")
    for k, v in notes.items():
        print("   " + v)
    return 0


if __name__ == "__main__":
    sys.exit(main())
