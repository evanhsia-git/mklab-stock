#!/usr/bin/env python3
"""ETF 規模／受益人數等補充資料：**官方自動化抓取**（2026-11-15 導入）。

背景：`parse_etf_meta.py`（半自動）檔頭原本記載「兩站表格是 JS 動態載入、找不到穩定 API」，
因此長期靠人工下載 CSV，`data/etf-meta.json` 停在 2026-11-02。
2026-11-15 實測找到兩個可直接程式化取得的官方端點（使用者 Ivan 提供並決定自動化）：

| 市場 | 端點 | 實測 |
|---|---|---|
| TWSE | `https://wwwc.twse.com.tw/zh/ETFortune/etfExcel?...` | HTTP 200、`text/csv;charset=ms950`、約 248 列 |
| TPEx | `https://info.tpex.org.tw/api/etfFilter`（篩選頁背後的資料 API） | HTTP 200、`application/json`、約 118 檔 |

策略（Ivan 2026-11-15 決策）：**官方自動化優先，失敗才由人工 CSV 備援**。

- TWSE 成功 → 覆寫 `data/raw/twse_etf.csv`（同時更新人工備援檔）→ 用 `parse_etf_meta.parse_twse()` 解析
- TWSE 失敗 → 沿用既有的 `data/raw/twse_etf.csv`（人工匯出），並在 meta 標記 `manual`
- TPEx 成功 → 解析 JSON
- TPEx 失敗 → 依序退回 (1) 人工 `data/raw/tpex_etf.csv` (2) 上次 `etf-meta.json` 的 TPEx 資料
- 兩邊都失敗且無備援 → **不覆寫**既有檔

安全護欄：新結果檔數若比上次少 20% 以上，視為來源異常，中止不覆寫。
"""
import datetime as dt
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_etf_meta as pem  # noqa: E402  重用既有 CSV 解析器（單一解析來源）

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(DATA, "raw")
OUT_PATH = os.path.join(DATA, "etf-meta.json")
TZ = dt.timezone(dt.timedelta(hours=8))

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}

# 2026-11-23：改用無參數全量版。原 11-15 的 range 篩選參數版實測會漏 0050（248 vs 250 檔，
# TWSE 端點行為變化；0050 缺失連鎖：分類檔掉 0050 → stocks.json 降級 unverified，見當日 commit）。
TWSE_CSV_URL = "https://wwwc.twse.com.tw/zh/ETFortune/etfExcel"
TPEX_API_URL = "https://info.tpex.org.tw/api/etfFilter"
TPEX_API_REFERER = "https://info.tpex.org.tw/ETF/zh/filter.html"

MIN_KEEP_RATIO = 0.8  # 新結果 < 上次 80% → 視為異常


def http_get(url, referer=None, timeout=60):
    """回傳 bytes；失敗丟例外（呼叫端決定備援）。"""
    headers = dict(UA)
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as f:
        return f.read()


def _n(v):
    """數值安全轉換。實測 TPEx 的 `rorYTD` 是**數字**而非字串（0／171.2），
    直接丟給 pem._num 會爆 `'int' object has no attribute 'strip'`；其餘欄位都是字串。"""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return None if v != v else v  # NaN → None
    return pem._num(v)


def _s(v):
    """字串安全轉換（來源可能回數字／None）。"""
    if v is None or isinstance(v, bool):
        return None
    return str(v).strip() or None


def parse_tpex_json(payload):
    """TPEx `api/etfFilter` JSON → 與 parse_etf_meta 相同的記錄格式。"""
    out = []
    for r in (payload or {}).get("data", []) or []:
        sym = str(r.get("stockNo") or "").strip()
        if not pem._is_code(sym):
            continue
        raw_date = str(r.get("listingDate") or "").strip()
        listing = (f"{raw_date[0:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
                   if len(raw_date) == 8 and raw_date.isdigit() else None)
        out.append({
            "sym": sym,
            "name": _s(r.get("stockName")),
            "market": "TPEx",
            "listing_date": listing,
            "tracking_index": _s(r.get("indexName")),
            "net_assets_100m": _n(r.get("totalAv")),
            "close": None,  # 此 API 不提供收盤價（本站另有每日價量，不重複存）
            "avg_value_1m": _n(r.get("valueYTD")),
            "avg_volume": _n(r.get("volumeYTD")),
            "beneficiaries": _n(r.get("holders")),
            "issuer": _s(r.get("issuer")),
            "ytd_return_pct": _n(r.get("rorYTD")),
            "source_url": _s(r.get("issuerLink")),
        })
    return out


def fetch_twse():
    """官方 CSV → 寫入 data/raw/twse_etf.csv（同時更新人工備援檔）→ 解析。"""
    body = http_get(TWSE_CSV_URL)
    text = body.decode("cp950", "ignore")
    # 防呆：必須含表頭關鍵字，否則視為失敗（避免把錯誤頁存成 CSV）
    if "ETF" not in text or "受益人數" not in text:
        raise ValueError("TWSE CSV 內容不含預期表頭（可能被擋或改版）")
    os.makedirs(RAW, exist_ok=True)
    with open(pem.TWSE_CSV, "w", encoding="cp950", errors="replace") as f:
        f.write(text)
    rows = pem.parse_twse()
    if not rows:
        raise ValueError("TWSE CSV 解析後 0 檔")
    return rows, "auto"


def load_prev():
    if not os.path.exists(OUT_PATH):
        return {}
    try:
        return json.load(open(OUT_PATH, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def compute_etf_fees(net_assets_100m):
    """依 AUM 階梯計算經理費/保管費（2026-11-17）。

    經理費：0億含以上 0.15% / 1000億不含以上 0.10% / 5000億不含以上 0.08% / 10000億不含以上 0.05%
    保管費：0億含以上 0.03% / 10000億不含以上 0.025%
    回傳 (management_fee, custody_fee, total_fee)；AUM 為 None 時三者皆 None。
    """
    mgmt = None
    cust = None
    if net_assets_100m is not None:
        if net_assets_100m >= 10000:
            mgmt = 0.05
            cust = 0.025
        elif net_assets_100m >= 5000:
            mgmt = 0.08
            cust = 0.03
        elif net_assets_100m >= 1000:
            mgmt = 0.10
            cust = 0.03
        else:
            mgmt = 0.15
            cust = 0.03
    total = (mgmt + cust) if (mgmt is not None and cust is not None) else None
    return mgmt, cust, total


def main():
    prev = load_prev()
    prev_etfs = prev.get("etfs") or []
    prev_twse = [e for e in prev_etfs if e.get("market") == "TWSE"]
    prev_tpex = [e for e in prev_etfs if e.get("market") == "TPEx"]

    notes, provenance = [], {}

    # 2026-11-23：核心 ETF 存在性／檔數驟降防護（學自 active-etf 的 count-drop guard）。
    # HTTP 200 不代表內容完整：當日來源短暫異常可能缺 0050 等大戶（2026-11-23 凌晨實例：
    # 官方 CSV 缺 0050 被當成功寫入 → 分類檔連鎖掉 0050 → stocks.json 0050 降級 unverified）。
    # 缺核心 ETF 或檔數驟降 >10% 一律視同抓取失敗，走人工 CSV → 再不行沿用上次結果。
    prev_syms = {e.get("sym") for e in prev_twse}

    def _twse_ok(rows):
        syms = {e.get("sym") for e in rows}
        missing = [s for s in ("0050", "006208", "009816") if s in prev_syms and s not in syms]
        if missing:
            return False, f"缺核心 ETF {missing}"
        if prev_twse and len(rows) < len(prev_twse) * 0.9:
            return False, f"檔數驟降 {len(prev_twse)}→{len(rows)}"
        return True, ""

    # --- TWSE：官方自動 → 人工 CSV 備援 → 上次結果 ---
    try:
        twse, provenance["TWSE"] = fetch_twse()
        ok, why = _twse_ok(twse)
        if not ok:
            raise ValueError(f"官方 CSV 內容異常（{why}）")
        notes.append(f"TWSE 官方 CSV 自動抓取 {len(twse)} 檔")
    except Exception as e:  # noqa: BLE001
        print(f"[warn] TWSE 自動抓取失敗（{e}），改用人工 CSV 備援", file=sys.stderr)
        twse, provenance["TWSE"] = pem.parse_twse(), "manual"
        ok, why = _twse_ok(twse)
        if not ok:
            # 人工備援檔可能已被壞資料覆寫（fetch_twse 會同步更新 raw CSV）→ 沿用上次結果
            twse, provenance["TWSE"] = prev_twse, "previous"
            notes.append(f"TWSE 自動與人工 CSV 皆異常（{why}）→ 沿用上次結果 {len(twse)} 檔")
        else:
            notes.append(f"TWSE 自動抓取失敗（{e}）→ 人工 CSV 備援 {len(twse)} 檔")

    # --- TPEx：官方 API → 人工 CSV → 上次結果 ---
    try:
        tpex = parse_tpex_json(json.loads(http_get(TPEX_API_URL, TPEX_API_REFERER).decode("utf-8")))
        if not tpex:
            raise ValueError("TPEx API 回傳 0 檔")
        provenance["TPEx"] = "auto"
        notes.append(f"TPEx 官方 API 自動抓取 {len(tpex)} 檔")
    except Exception as e:  # noqa: BLE001
        print(f"[warn] TPEx 自動抓取失敗（{e}），改用備援", file=sys.stderr)
        tpex, provenance["TPEx"] = pem.parse_tpex(), "manual"
        if not tpex:
            tpex, provenance["TPEx"] = prev_tpex, "previous"
            notes.append(f"TPEx 自動失敗（{e}）→ 沿用上次結果 {len(tpex)} 檔")
        else:
            notes.append(f"TPEx 自動失敗（{e}）→ 人工 CSV 備援 {len(tpex)} 檔")

    if not twse and not tpex:
        print("兩邊都沒有資料，中止不覆寫", file=sys.stderr)
        return 2

    etfs = twse + tpex
    # 2026-11-17：依 AUM 階梯計算經理費/保管費/合計費率
    for r in etfs:
        mgmt, cust, total = compute_etf_fees(r.get("net_assets_100m"))
        r["management_fee"] = mgmt
        r["custody_fee"] = cust
        r["total_fee"] = total
    # 2026-11-22：一律不寫 close（TPEx 早已如此；見 parse_tpex_json 的設計註解
    # 「本站另有每日價量，不重複存」）。TWSE CSV 雖帶收盤欄，但週更會讓它過期
    # （實例：0050 停在分割前 180.0）。全站無任何頁面顯示 etf-meta 的 close，
    # 價格一律以 stocks.json 的 price 為準。
    for r in etfs:
        r.pop("close", None)
    # 護欄：來源異常導致檔數大減時不覆寫。
    # **逐市場**比對，不能只看總數——否則「TWSE 全掛、TPEx 正常」會通過護欄，
    # 寫出一份 TWSE 空掉的檔（前端會少掉一整個市場的 ETF）。
    for market, new_rows, prev_rows in (("TWSE", twse, prev_twse), ("TPEx", tpex, prev_tpex)):
        if prev_rows and len(new_rows) < len(prev_rows) * MIN_KEEP_RATIO:
            print(f"{market} 檔數 {len(new_rows)} 少於上次 {len(prev_rows)} 的 "
                  f"{MIN_KEEP_RATIO:.0%}（總計 {len(etfs)}），視為來源異常，中止不覆寫",
                  file=sys.stderr)
            return 2

    doc = {
        "meta": {
            "as_of": dt.datetime.now(TZ).strftime("%Y-%m-%d"),
            "fetched_at": dt.datetime.now(TZ).isoformat(timespec="seconds"),
            "source": "TWSE ETF投資篩選器（官方 CSV）＋ TPEx ETF投資篩選器（官方 api/etfFilter）"
                      "；自動化優先、失敗由人工 CSV 備援",
            "provenance": provenance,  # auto / manual / previous
            "count": len(etfs),
            "counts": {"TWSE": len(twse), "TPEx": len(tpex)},
            "endpoints": {"TWSE": TWSE_CSV_URL, "TPEx": TPEX_API_URL},
            "manual_source_urls": {"TWSE": pem.TWSE_SOURCE_URL, "TPEx": pem.TPEX_SOURCE_URL},
            "note": "資產規模、受益人數為抓取當下的快照值（非即時）。"
                    "上市/上櫃日期、發行人為低頻變動欄位。人工備援方式見 parse_etf_meta.py 檔頭。"
                    "經理費/保管費係依 AUM 階梯試算（0億含以上0.15%、1000億不含以上0.10%、"
                    "5000億不含以上0.08%、10000億不含以上0.05%；保管費0億含以上0.03%、"
                    "10000億不含以上0.025%），實際費率請以各發行機構官方披露為準。",
            "log": notes,
        },
        "etfs": etfs,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"✅ 已寫入 {OUT_PATH}（共 {len(etfs)} 檔，TWSE {len(twse)}({provenance['TWSE']}) "
          f"+ TPEx {len(tpex)}({provenance['TPEx']})）")
    for n in notes:
        print("   " + n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
