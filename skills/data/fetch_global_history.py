#!/usr/bin/env python3
"""
美股、全球指數與市場情緒的每日收盤資料庫（月檔）。
儲存結構（依使用者指定）：
  data/us-history-2026/us-history-2026-10.json        美股指數（2026 年 10 月）
  data/global-history-2026/global-history-2026-10.json 全球指數與市場情緒（2026 年 10 月）
每個月一個檔案，檔內每個交易日一列；同一日重跑會覆寫該日（upsert），不會重複。
來源：yfinance（非官方備援）。抓不到的代號保留為 missing，不填假值。
用法：python3 skills/data/fetch_global_history.py [YYYY-MM-DD]（省略則用最近交易日）
"""
import datetime as dt, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TZ = dt.timezone(dt.timedelta(hours=8))
US = {"^DJI": "道瓊工業", "^GSPC": "S&P 500", "^IXIC": "那斯達克綜合", "^NDX": "那斯達克100", "^SOX": "費城半導體"}
GLOBAL = {"^TWII": "台股加權", "^HSI": "恆生", "^N225": "日經225", "^KS11": "韓國KOSPI", "^VIX": "VIX恐慌指數",
          "TWD=X": "美元兌台幣", "GC=F": "黃金", "CL=F": "WTI原油", "BTC-USD": "比特幣"}

def month_path(base, prefix, date):
    folder = os.path.join(ROOT, "data", f"{prefix}-history-{date.year}")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"{prefix}-history-{date.year}-{date.month:02d}.json")

def upsert(path, date_str, tickers, missing, source):
    doc = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"rows": []}
    rows = [r for r in doc["rows"] if r["date"] != date_str]
    rows.append({"date": date_str, "close": tickers, "missing": missing})
    rows.sort(key=lambda r: r["date"])
    doc = {"month": date_str[:7], "source": source, "updated_at": dt.datetime.now(TZ).isoformat(), "rows": rows}
    json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def fetch_closes(symbols, date):
    """以 yfinance 取得指定日收盤；失敗的代號回傳 None（不推測）。"""
    import yfinance as yf
    out = {}
    start = date - dt.timedelta(days=7)
    for sym in symbols:
        try:
            h = yf.Ticker(sym).history(start=start.isoformat(), end=(date + dt.timedelta(days=1)).isoformat())
            row = h[h.index.date == date]
            out[sym] = float(row["Close"].iloc[-1]) if len(row) else None
        except Exception:
            out[sym] = None
    return out

def run(date, fetch=fetch_closes):
    date_str = date.isoformat()
    for prefix, table in [("us", US), ("global", GLOBAL)]:
        closes = fetch(list(table.keys()), date)
        tickers = {s: {"name": table[s], "close": closes.get(s)} for s in table}
        missing = [s for s in table if closes.get(s) is None]
        upsert(month_path(None, prefix, date), date_str, tickers, missing, "yfinance（非官方備援）")
    return date_str

if __name__ == "__main__":
    d = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.datetime.now(TZ).date()
    print("寫入", run(d))
