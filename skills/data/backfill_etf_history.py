#!/usr/bin/env python3
"""
ETF 上市以來歷史回補（一次性／可重跑，非每日排程）。

用途：把指定 TPEx 上櫃 ETF 的「上市以來」日線補進 mklab-stock。
- 來源：Yahoo Finance（yfinance，免 key），代號用 .TWO 後綴（上櫃）。實測 .TW 無資料。
- 價格口徑：auto_adjust=False（原始收盤）；yfinance 1.x 預設 auto_adjust=True 會做股利調整，
  數值會比官方收盤低 6~8%，不可用。
- 清洗：丟棄上市前 volume=0 的 NAV 佔位列、以及盤中無成交（volume=0）的日子，只留真實交易日。
- 裁切：所有寫入（kline / stocks.json）一律裁到 stocks.json 的 meta.as_of，確保與全站資料日一致。

寫入檔案：
  data/kline/{代號}.json      全歷史 K 線（format 與 build_kline.py 產出一致）
  data/stocks.json            新增／更新該代號的紀錄（含 MA/RSI/MACD/KD 等指標）
  data/etf-meta.json          補 close（現價）與 avg_volume（月均量）
  data/symbol-map.json        補代號 → yfinance 對照（.TWO）

用法：
  python3 skills/data/backfill_etf_history.py                 # 回補預設 14 檔
  python3 skills/data/backfill_etf_history.py --codes 006201,00858
  python3 skills/data/backfill_etf_history.py --dry-run       # 只抓取與試算，不寫檔
  python3 skills/data/backfill_etf_history.py --cache /tmp/x.json  # 用先前抓好的資料

注意：本腳本只「新增／更新」指定代號，不會刪除任何既有紀錄或檔案。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, "data")
KLINE_DIR = os.path.join(DATA, "kline")

sys.path.insert(0, HERE)
from compute_indicators import (  # noqa: E402
    sma, calc_rsi, calc_macd, calc_kd, calc_chg, CHG_PERIODS, calc_pos52,
    MIN_FOR_RSI, MIN_FOR_KD,
)

# 用戶指定回補的 TPEx 上櫃 ETF
DEFAULT_CODES = ["006201", "00858", "00877", "00886", "00887", "00888",
                 "00928", "00955", "009806", "009807", "009814", "009815",
                 "009822", "009823"]

SOURCE = "Yahoo Finance"
QUALITY = "yfinance_fallback"


def _load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def fetch_history(code):
    """抓單一 ETF 全歷史日線。回傳 [(date, o, h, l, c, v), ...]（已清洗，舊→新）。"""
    try:
        import yfinance as yf
    except ImportError:
        raise SystemExit("需要 yfinance：pip install yfinance")
    h = yf.Ticker(code + ".TWO").history(period="max", interval="1d", auto_adjust=False)
    if h is None or h.empty:
        return []
    rows = []
    for ts, r in h.iterrows():
        vals = [r.get("Open"), r.get("High"), r.get("Low"), r.get("Close")]
        if any(v is None or v != v for v in vals):
            continue
        vol = r.get("Volume")
        vol = 0 if (vol is None or vol != vol) else int(vol)
        rows.append((str(ts.date()), round(float(vals[0]), 2), round(float(vals[1]), 2),
                     round(float(vals[2]), 2), round(float(vals[3]), 2), vol))
    rows.sort(key=lambda x: x[0])
    # 上市前 volume=0 的 NAV 佔位列 → 從第一筆真實成交日開始
    start = next((i for i, r in enumerate(rows) if r[5] > 0), None)
    if start is None:
        return []
    rows = rows[start:]
    # 盤中無成交（停牌／來源補值）逐日剔除，避免畫出假 K 棒
    return [r for r in rows if r[5] > 0]


def clip_to(rows, asof):
    """裁到 asof（含）為止；asof 之後的資料不寫入，維持全站同一資料日。"""
    return [r for r in rows if r[0] <= asof]


def to_kline_rows(rows):
    """(YYYY-MM-DD, o,h,l,c,v) → kline 格式 [[date,o,h,l,c], ...]（不含量）。"""
    return [[r[0], r[1], r[2], r[3], r[4]] for r in rows]


def to_indicator_rows(rows):
    """→ (YYYYMMDD, o,h,l,c)：compute_indicators 的函式吃這個格式。"""
    return [(r[0].replace("-", ""), r[1], r[2], r[3], r[4]) for r in rows]


def build_indicators(irows):
    """用 repo 既有函式算指標，確保與其他標的口徑一致。"""
    closes = [r[4] for r in irows]
    highs = [r[2] for r in irows]
    lows = [r[3] for r in irows]
    dif, dea, hist = calc_macd(closes)
    k, d = calc_kd(highs, lows, closes, 9) if len(closes) >= MIN_FOR_KD else (None, None)
    out = {
        **{k: calc_chg(irows, d) for k, d in CHG_PERIODS.items()},
        "ma5": sma(closes, 5), "ma10": sma(closes, 10),
        "ma20": sma(closes, 20), "ma30": sma(closes, 30),
        "rsi14": calc_rsi(closes, 14) if len(closes) >= MIN_FOR_RSI else None,
        "macd_dif": dif, "macd_dea": dea, "macd_hist": hist,
        "kd_k": k, "kd_d": d,
    }
    out.update(calc_pos52(irows))
    return out


def build_record(code, meta, rows, asof):
    """建立／更新 stocks.json 用的紀錄（欄位對齊既有 ETF 紀錄）。"""
    last = rows[-1]
    prev = rows[-2] if len(rows) > 1 else last
    chg = None
    if prev[4]:
        chg = round((last[4] - prev[4]) / prev[4] * 100, 2)
    aum = meta.get("net_assets_100m")
    mc = round(aum * 1e8) if aum else None
    rec = {
        "sym": code,
        "name": meta.get("name"),
        "price": last[4], "open": last[1], "high": last[2], "low": last[3],
        "volume": float(last[5]),
        "pe": None, "pb": None, "div": None,
        "roe": None, "roa": None, "eps": None, "capital_stock": None,
        "market_cap": mc, "ind": None,
        "is_etf": True, "security_type": "etf",
        "chg": chg, "rank": None,
        "source": SOURCE, "quality": QUALITY, "last_updated": asof,
    }
    rec["market_cap_source"] = "etf-meta.net_assets_100m（官方 CSV 資產規模 ×1e8）"
    rec.update(build_indicators(to_indicator_rows(rows)))
    return rec


def write_kline(code, rows, asof):
    """輸出 data/kline/{code}.json，格式與 build_kline.py 完全一致。"""
    payload = {"sym": code, "asof": asof,
               "fields": ["date", "open", "high", "low", "close"],
               "rows": to_kline_rows(rows)}
    os.makedirs(KLINE_DIR, exist_ok=True)
    path = os.path.join(KLINE_DIR, code + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    return path


def write_json(path, doc, indent=None):
    """寫回 JSON。indent=None → 壓縮格式（data/stocks.json 原格式即為壓縮），
    避免只加幾筆資料卻讓整個檔案重新排版、產生巨大 diff。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=None if indent else (",", ":"),
                  indent=indent)
    return path


def update_symbol_map_text(path, entries):
    """把代號對照「插進」symbol_map 物件尾端，不動檔案其他任何一個字元。

    為什麼不用 json.dump 整檔重寫：原始檔的既有條目有手寫單行格式（如
    `"0050": { "name": "元大台灣50", ... }`）與緊湊陣列，用 json.dump 重排會
    產生大量與本次任務無關的格式 churn。這裡只做文字插入，維持最小 diff。
    已存在的代號會跳過（可重複執行）。
    """
    raw = open(path, encoding="utf-8").read()
    marker = '"symbol_map": {'
    i = raw.index(marker)
    j = raw.index("{", i)
    depth, k = 0, j
    while k < len(raw):
        if raw[k] == "{":
            depth += 1
        elif raw[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    todo = {c: e for c, e in entries.items() if '"%s": {' % c not in raw[j:k]}
    if not todo:
        return 0
    blocks = []
    for code, e in todo.items():
        body = json.dumps(e, ensure_ascii=False, indent=2)
        body = "\n".join("    " + ln if idx else ln for idx, ln in enumerate(body.split("\n")))
        blocks.append('    "%s": %s' % (code, body))
    new = raw[:k].rstrip() + ",\n" + ",\n".join(blocks) + "\n  " + raw[k:]
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)
    return len(todo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", default=",".join(DEFAULT_CODES))
    ap.add_argument("--cache", help="改用先前抓好的 JSON（{code:[date,o,h,l,c,v],...}）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]

    stocks_path = os.path.join(DATA, "stocks.json")
    meta_path = os.path.join(DATA, "etf-meta.json")
    smap_path = os.path.join(DATA, "symbol-map.json")

    stocks_doc = _load_json(stocks_path) or {"meta": {}, "stocks": []}
    asof = stocks_doc.get("meta", {}).get("as_of")
    if not asof:
        raise SystemExit("stocks.json 缺少 meta.as_of，無法決定裁切日")
    etf_doc = _load_json(meta_path) or {"meta": {}, "etfs": []}
    etf_by_sym = {e["sym"]: e for e in etf_doc.get("etfs", [])}
    cache = json.load(open(args.cache, encoding="utf-8")) if args.cache else None
    records, report, full_rows = [], [], {}
    for code in codes:
        rows = [tuple(r) for r in cache[code]] if cache and code in cache else fetch_history(code)
        full_rows[code] = rows                      # 未裁切：算 etf-meta 最新 close 用
        rows = clip_to(rows, asof)                  # 裁到全站資料日：寫 kline / stocks.json
        if not rows:
            report.append((code, "無資料", 0, None, None))
            continue
        meta = etf_by_sym.get(code, {})
        rec = build_record(code, meta, rows, asof)
        records.append(rec)
        if not args.dry_run:
            write_kline(code, rows, asof)
        report.append((code, meta.get("name"), len(rows), rows[0][0], rows[-1][0]))

    # ---- data/stocks.json：新增或就地更新（依市值降序，None 排尾）----
    new_by_sym = {r["sym"]: r for r in records}
    merged, seen = [], set()
    for s in stocks_doc.get("stocks", []):
        if s.get("sym") in new_by_sym:
            merged.append(new_by_sym[s["sym"]])
            seen.add(s["sym"])
        else:
            merged.append(s)
    merged.extend(r for r in records if r["sym"] not in seen)
    merged.sort(key=lambda x: (x.get("market_cap") if x.get("market_cap") is not None else -1),
                reverse=True)
    stocks_doc["stocks"] = merged
    stocks_doc.setdefault("meta", {})["count"] = len(merged)
    stocks_doc["meta"]["backfill_note"] = (
        "已用 skills/data/backfill_etf_history.py 回補 TPEx 上櫃 ETF 上市以來日線；"
        "K 線見 data/kline/{代號}.json")

    # ---- data/etf-meta.json：補 close（最新收盤，不裁切，對齊其自身 as_of）與 avg_volume ----
    for code in new_by_sym:
        e = etf_by_sym.get(code)
        full = full_rows.get(code) or []
        if not e or not full:
            continue
        tail = [r for r in full if r[5] > 0][-30:]
        e["close"] = full[-1][4]
        e["avg_volume"] = round(sum(r[5] for r in tail) / len(tail)) if tail else None
        e["price_asof"] = full[-1][0]

    # ---- data/symbol-map.json：補代號 → Yahoo（上櫃 .TWO）----
    smap_new = {}
    for code, rec in new_by_sym.items():
        smap_new[code] = {"twse": None, "tpex": code, "yfinance": code + ".TWO",
                          "market": "TW", "type": "etf", "exchange": "TPEX",
                          "name": rec["name"], "industry": None}

    if args.dry_run:
        print("[dry-run] 未寫入任何檔案")
    else:
        write_json(stocks_path, stocks_doc, indent=None)
        write_json(meta_path, etf_doc, indent=2)
        n = update_symbol_map_text(smap_path, smap_new)
        print(f"[symbol-map] 新增 {n} 筆代號對照")

    print(f"\n{'代號':<8}{'名稱':<16}{'筆數':<7}{'起':<12}{'迄':<12}")
    for code, name, n, f, l in report:
        print(f"{code:<8}{(name or '')[:14]:<16}{n:<7}{f or '-':<12}{l or '-':<12}")
    print(f"\n共 {len(records)} 檔、{sum(r[2] for r in report)} 筆；裁切日 asof={asof}")


if __name__ == "__main__":
    main()
