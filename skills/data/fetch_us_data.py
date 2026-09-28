#!/usr/bin/env python3
"""
mklab-stock 美股資料抓取腳本（Build-Time, 雲端免 key，僅用 yfinance）。

⚠️ 這支腳本跟台股的 skills/data/fetch_data.py 完全獨立、互不呼叫、互不匯入：
  - 台股資料放在 data/（stocks.json、industry.json…）
  - 美股資料一律放在 data/us/（us-stocks.json、us-etfs.json），不會寫進或讀取
    任何 data/ 底下的台股檔案，也不共用任何設定檔。
  - 之所以完全分開管理，是因為兩邊的交易時間、資料源欄位、休市判斷邏輯都不同，
    分開才不會互相拖累（美股抓取失敗不會影響台股排程，反之亦然）。

設計原則（沿用本專案一貫的 GitHub-Native / Fork First / 零外部依賴 / 零 secret）：
  - 唯一資料源 yfinance（免費、免 key），無官方對應「台灣 TWSE/TPEx」的美股公家
    API，故不強求官方源，這點跟台股資料管線不同，需明確告知使用者。
  - 候選池機制：yfinance 沒有提供免費的「市值前 N 大」篩選端點，所以用一份人工
    維護、涵蓋範圍夠廣的候選代號清單（US_STOCK_CANDIDATES / US_ETF_CANDIDATES），
    抓回每檔的即時市值後在本機排序，取前 30 大寫入輸出檔。候選池需要不定期更新
    （例如新股票晉升市值前段班、舊 ETF 下市），這是這個做法唯一的維護成本。
  - Graceful Degradation：單檔抓取失敗不中斷整批，該檔案跳過並記錄警告，其餘
    正常寫入；資料不足的欄位一律 null，不推測、不冒充。
  - 沿用台股腳本的防 ban 作法：逐檔 sleep，不併發大量請求。

用法：
  python3 skills/data/fetch_us_data.py stocks   # 美股市值前 30 大個股
  python3 skills/data/fetch_us_data.py etfs     # 美股 ETF 規模前 30 大
  python3 skills/data/fetch_us_data.py all      # 兩者都跑
"""
import json
import os
import sys
import time
import datetime as dt

OUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "us"))
os.makedirs(OUT_DIR, exist_ok=True)

SLEEP_SEC = 1.2  # 逐檔間隔，防止被 Yahoo Finance 暫時封鎖
TOP_N = 30

# ===== 候選池：市值/規模夠大、實務上幾乎不會跌出前 30 名的常見標的 =====
# 涵蓋範圍故意抓寬一點（遠多於 30 檔），抓回即時市值後在本機排序取前 30，
# 這樣即使候選池排序過時，只要真正的前 30 大都還在池子裡，結果依然正確。
# 需要定期（例如每季）人工檢視一次，把新的超大型股/新 ETF 加進來。
US_STOCK_CANDIDATES = [
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "AVGO",
    "LLY", "JPM", "V", "WMT", "UNH", "XOM", "MA", "PG", "JNJ", "HD",
    "COST", "ORCL", "MRK", "ABBV", "CVX", "CRM", "BAC", "KO", "AMD", "PEP",
    "NFLX", "TMO", "ADBE", "MCD", "CSCO", "ABT", "WFC", "DIS", "PM", "INTU",
    "IBM", "GE", "CAT", "TXN", "VZ", "AMGN", "NOW", "PFE", "UNP", "LOW",
    "QCOM", "SPGI", "BX", "AXP", "BA", "HON", "GS", "T", "RTX", "NKE",
]
US_ETF_CANDIDATES = [
    "SPY", "IVV", "VOO", "VTI", "QQQ", "VUG", "VTV", "BND", "AGG", "VEA",
    "IEFA", "VWO", "IJH", "IJR", "VIG", "IWM", "GLD", "VXUS", "VO", "EFA",
    "SCHD", "SCHX", "XLK", "XLF", "XLV", "XLE", "DIA", "VYM", "SLV", "TLT",
    "HYG", "LQD", "SPYG", "SPYV", "MDY", "RSP", "VB", "VT", "SCHB", "ITOT",
]


def _log(msg):
    print(f"[fetch_us_data] {msg}", flush=True)


def _fetch_one_stock(yf, sym):
    try:
        t = yf.Ticker(sym)
        info = t.info or {}
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        chg = None
        if price is not None and prev_close:
            chg = round((price - prev_close) / prev_close * 100, 2)
        return {
            "sym": sym,
            "name": info.get("shortName") or info.get("longName") or sym,
            "price": price,
            "chg": chg,
            "pe": info.get("trailingPE"),
            "pb": info.get("priceToBook"),
            "roe": round(info["returnOnEquity"] * 100, 2) if info.get("returnOnEquity") is not None else None,
            "eps": info.get("trailingEps"),
            "div": round(info["dividendYield"] * 100, 2) if info.get("dividendYield") is not None else None,
            "market_cap": info.get("marketCap"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "currency": info.get("currency", "USD"),
            "exchange": info.get("exchange"),
        }
    except Exception as e:
        _log(f"⚠️ {sym} 抓取失敗：{e}")
        return None


def _fetch_one_etf(yf, sym):
    try:
        t = yf.Ticker(sym)
        info = t.info or {}
        price = info.get("navPrice") or info.get("currentPrice") or info.get("regularMarketPrice")
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        chg = None
        if price is not None and prev_close:
            chg = round((price - prev_close) / prev_close * 100, 2)
        return {
            "sym": sym,
            "name": info.get("shortName") or info.get("longName") or sym,
            "price": price,
            "chg": chg,
            "net_assets": info.get("totalAssets"),  # 基金規模（近似市值，用於排序前 30 大）
            "expense_ratio": round(info["annualReportExpenseRatio"] * 100, 3) if info.get("annualReportExpenseRatio") is not None else None,
            "yield": round(info["yield"] * 100, 2) if info.get("yield") is not None else None,
            "ytd_return": round(info["ytdReturn"] * 100, 2) if info.get("ytdReturn") is not None else None,
            "category": info.get("category"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "currency": info.get("currency", "USD"),
            "exchange": info.get("exchange"),
        }
    except Exception as e:
        _log(f"⚠️ {sym} 抓取失敗：{e}")
        return None


def run_stocks():
    try:
        import yfinance as yf
    except ImportError:
        _log("❌ yfinance 未安裝，無法抓美股資料")
        return False

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    _log(f"開始抓美股個股候選池（{len(US_STOCK_CANDIDATES)} 檔候選，取市值前 {TOP_N} 大）")

    results = []
    for i, sym in enumerate(US_STOCK_CANDIDATES):
        row = _fetch_one_stock(yf, sym)
        if row and row.get("market_cap") is not None:
            results.append(row)
        if i < len(US_STOCK_CANDIDATES) - 1:
            time.sleep(SLEEP_SEC)

    results.sort(key=lambda r: r["market_cap"], reverse=True)
    top = results[:TOP_N]

    doc = {
        "meta": {
            "as_of": stamp,
            "source": "Yahoo Finance (yfinance)",
            "note": "候選池排序取前 30 大市值；非官方美股交易所資料，僅供研究參考，非投資建議。",
            "candidate_pool_size": len(US_STOCK_CANDIDATES),
            "count": len(top),
        },
        "stocks": top,
    }
    out_path = os.path.join(OUT_DIR, "us-stocks.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    _log(f"✅ 已寫入 {out_path}（{len(top)} 檔，候選池 {len(results)} 檔取得有效市值）")
    return True


def run_etfs():
    try:
        import yfinance as yf
    except ImportError:
        _log("❌ yfinance 未安裝，無法抓美股 ETF 資料")
        return False

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    _log(f"開始抓美股 ETF 候選池（{len(US_ETF_CANDIDATES)} 檔候選，取規模前 {TOP_N} 大）")

    results = []
    for i, sym in enumerate(US_ETF_CANDIDATES):
        row = _fetch_one_etf(yf, sym)
        if row and row.get("net_assets") is not None:
            results.append(row)
        if i < len(US_ETF_CANDIDATES) - 1:
            time.sleep(SLEEP_SEC)

    results.sort(key=lambda r: r["net_assets"], reverse=True)
    top = results[:TOP_N]

    doc = {
        "meta": {
            "as_of": stamp,
            "source": "Yahoo Finance (yfinance)",
            "note": "候選池排序取前 30 大基金規模（net_assets 近似值）；非官方交易所資料，僅供研究參考，非投資建議。",
            "candidate_pool_size": len(US_ETF_CANDIDATES),
            "count": len(top),
        },
        "etfs": top,
    }
    out_path = os.path.join(OUT_DIR, "us-etfs.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    _log(f"✅ 已寫入 {out_path}（{len(top)} 檔，候選池 {len(results)} 檔取得有效規模）")
    return True


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    ok = True
    if mode in ("stocks", "all"):
        ok = run_stocks() and ok
    if mode in ("etfs", "all"):
        ok = run_etfs() and ok
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
