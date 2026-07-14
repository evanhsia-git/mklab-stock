#!/usr/bin/env python3
"""mklab-stock Build-Time 資料抓取腳本（Tier1 免 key：Yahoo Finance）。

產出：
  data/stocks.json    個股池（首頁 TOP / Screener 來源），含 PE/PB/EPS/ROE/ROA/rank/spct/ind
  data/industry.json  台灣 33 產業績效（漲跌% / 個股數 / 領漲%）
  data/market.json    五國主要指數走勢
  data/schema-version.json  Data Contract 版本戳

設計原則（對照 mklab-stock-skill 紅線）：
  - 零 secret：只用 Yahoo（.TW/.HK/.SS/.SZ + 美股 + 指數）
  - Graceful Degradation：單檔失敗不中斷，標 null
  - Reproducible：每次 run 重抓重算
  - 每日一次 push（由 workflow 控制）
"""
import json
import os
import datetime as dt
import yfinance as yf

OUT = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.abspath(OUT)
os.makedirs(OUT, exist_ok=True)

# 代表性標的池（台/美/中港），覆蓋多產業
TICKERS = {
    "2330.TW": ("台積電", "半導體"),
    "2317.TW": ("鴻海", "電子代工"),
    "2454.TW": ("聯發科", "IC設計"),
    "2308.TW": ("台達電", "電源管理"),
    "3008.TW": ("大立光", "電子零組件"),
    "2303.TW": ("聯電", "半導體"),
    "2412.TW": ("中華電", "通訊"),
    "2891.TW": ("中信金", "金融"),
    "2882.TW": ("國泰金", "金融"),
    "6505.TW": ("台塑化", "塑化"),
    "AAPL": ("Apple", "美股科技"),
    "MSFT": ("Microsoft", "美股科技"),
    "NVDA": ("NVIDIA", "美股半導體"),
    "00700.HK": ("騰訊", "港股科技"),
    "0941.HK": ("中移動", "港股電信"),
    "600519.SS": ("貴州茅台", "A股消費"),
    "000858.SZ": ("五糧液", "A股消費"),
}

# 台灣 33 法定產業（用作分類標籤 + 績效聚合）
INDUSTRIES = [
    "水泥工業","食品工業","塑膠工業","紡織纖維","電機機械","電器電纜","化學工業",
    "生技醫療業","玻璃陶瓷","造紙工業","鋼鐵工業","橡膠工業","汽車工業","半導體業",
    "電腦及週邊設備業","光電業","通訊網路業","電子零組件業","電子通路業","資訊服務業",
    "其他電子業","建材營造","航運業","觀光餐旅","金融保險","貿易百貨","油電燃氣業",
    "綜合","綠能環保","數位雲端","運動休閒","居家生活","其他等",
]

# 五國主要指數
INDICES = {
    "TWII": "^TWII",      # 台灣加權
    "SPX": "^GSPC",       # S&P500
    "NASDAQ": "^IXIC",    # Nasdaq
    "HSI": "^HSI",        # 恆生
    "CSI300": "000300.SS",# 滬深300
}


def safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def fetch_stock(sym, name, ind):
    """抓單檔，回傳 dict（失敗欄位給 null）。"""
    t = yf.Ticker(sym)
    info = safe(lambda: t.info) or {}
    hist = safe(lambda: t.history(period="30d"))
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if price is None and hist is not None and len(hist):
        price = float(hist["Close"].iloc[-1])
    prev = None
    chg = None
    if hist is not None and len(hist) >= 2:
        c = float(hist["Close"].iloc[-1])
        p = float(hist["Close"].iloc[-2])
        prev = p
        chg = round((c - p) / p * 100, 2) if p else None
    # 20日漲幅（spct）
    spct = None
    if hist is not None and len(hist) >= 2:
        first = float(hist["Close"].iloc[0])
        last = float(hist["Close"].iloc[-1])
        spct = round((last - first) / first * 100, 2) if first else None
    pe = info.get("trailingPE")
    pb = info.get("priceToBook")
    eps = info.get("trailingEps")
    roe = info.get("returnOnEquity")
    roa = info.get("returnOnAssets")
    rank = None
    if roe is not None and pe is not None:
        # 簡易綜合評分（示意）：ROE 高 + PE 低 得分高
        rank = round(min(99, max(1, 50 + (roe or 0) - (pe or 30) * 0.5)), 1)
    return {
        "sym": sym, "name": name, "ind": ind,
        "price": round(price, 2) if price else None,
        "prev": round(prev, 2) if prev else None,
        "chg": chg, "spct": spct,
        "pe": round(pe, 2) if pe else None,
        "pb": round(pb, 2) if pb else None,
        "eps": round(eps, 2) if eps else None,
        "roe": round(roe * 100, 2) if roe else None,
        "roa": round(roa * 100, 2) if roa else None,
        "rank": rank,
    }


def fetch_index(sym):
    t = yf.Ticker(sym)
    hist = safe(lambda: t.history(period="30d"))
    if hist is None or len(hist) == 0:
        return None
    last = float(hist["Close"].iloc[-1])
    prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else last
    chg = round((last - prev) / prev * 100, 2) if prev else None
    return {"price": round(last, 2), "chg": chg}


def main():
    stamp = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d")
    print(f"[fetch] 基準日 {stamp}")

    # 個股池
    stocks = []
    for sym, (name, ind) in TICKERS.items():
        r = fetch_stock(sym, name, ind)
        stocks.append(r)
        print(f"  {sym:12} {name:8} price={r['price']} chg={r['chg']}")
    stocks.sort(key=lambda x: (x["rank"] is not None, x["rank"] or 0), reverse=True)

    # 產業績效（依個股 ind 聚合；未在 33 清單內的標 '其他等'）
    ind_map = {}
    for s in stocks:
        cat = s["ind"] if s["ind"] in INDUSTRIES else "其他等"
        ind_map.setdefault(cat, []).append(s)
    industry = []
    for nm in INDUSTRIES:
        members = ind_map.get(nm, [])
        cnt = len(members)
        if cnt:
            chgs = [m["chg"] for m in members if m["chg"] is not None]
            avg = round(sum(chgs) / len(chgs), 2) if chgs else 0.0
            top = round(max(chgs), 2) if chgs else 0.0
        else:
            avg, top = 0.0, 0.0
        industry.append({"nm": nm, "chg": avg, "cnt": cnt, "top": top})

    # 指數
    market = {}
    for key, sym in INDICES.items():
        r = fetch_index(sym)
        if r:
            market[key] = r
            print(f"  idx {key:8} {r['price']} ({r['chg']}%)")

    payload = {
        "meta": {
            "source": "Yahoo Finance (Tier1, 免 key)",
            "as_of": stamp,
            "note": "資料以最近交易日收盤為準（非即時）",
        },
        "stocks": stocks,
        "industry": industry,
        "market": market,
    }
    with open(os.path.join(OUT, "stocks.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    # 向前相容：industry / market 也單獨出
    with open(os.path.join(OUT, "industry.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": payload["meta"], "industry": industry}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT, "market.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": payload["meta"], "market": market}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT, "schema-version.json"), "w", encoding="utf-8") as f:
        json.dump({"schema_version": 1, "generated_at": stamp, "generator": "scripts/fetch_data.py"}, f, ensure_ascii=False, indent=2)
    print(f"[fetch] 完成 → data/ (stocks={len(stocks)} industry={len(industry)} market={len(market)})")


if __name__ == "__main__":
    main()
