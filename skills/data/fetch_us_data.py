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
    抓回每檔的即時市值/規模後在本機排序：個股取前 600 大、ETF 取前 120 大（2026-11-25 擴充）。
    （例如新股票晉升市值前段班、舊 ETF 下市），這是這個做法唯一的維護成本。
  - Graceful Degradation：單檔抓取失敗不中斷整批，該檔案跳過並記錄警告，其餘
    正常寫入；資料不足的欄位一律 null，不推測、不冒充。
  - 沿用台股腳本的防 ban 作法：逐檔 sleep，不併發大量請求。

用法：
  python3 skills/data/fetch_us_data.py stocks   # 美股市值前 600 大個股（2026-11-25 擴充）
  python3 skills/data/fetch_us_data.py etfs     # 美股 ETF 規模前 120 大（2026-11-25 擴充）
  python3 skills/data/fetch_us_data.py all      # 兩者都跑
"""
import json
import os
import sys
import time
import datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data_rules  # 2026-11-13 共用資料品質規則

OUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "us"))
os.makedirs(OUT_DIR, exist_ok=True)

SLEEP_SEC = 0.8  # 逐檔間隔，防止被 Yahoo Finance 暫時封鎖（2026-11-25：擴充到 600 檔，縮短間隔控管總時長）
TOP_N_STOCKS = 600  # 2026-11-25：美股個股擴充——universe（S&P500＋index-holdings 併入）全量抓取，上限 600
TOP_N_ETFS = 120    # 2026-11-25：美股 ETF 擴充——候選池 130+ 取規模前 120 大

# ===== 候選池：市值/規模夠大、實務上幾乎不會跌出前 30 名的常見標的 =====
# 涵蓋範圍故意抓寬一點（遠多於 30 檔），抓回即時市值後在本機排序取前 30，
# 這樣即使候選池排序過時，只要真正的目標標的都還在池子裡，結果依然正確。
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
    # 寬基美股
    "SPY", "IVV", "VOO", "VTI", "QQQ", "QQQM", "VUG", "VTV", "VOOG", "VOOV",
    "SCHX", "SCHB", "ITOT", "VT", "SPTM", "VXF", "SPYG", "SPYV", "SCHG", "SCHV",
    "IWF", "IWD", "IWM", "IJH", "IJR", "VB", "VO", "MDY", "RSP", "EWMC",
    # 智慧貝塔／因子
    "SCHD", "VYM", "SPHD", "SPYD", "USMV", "MTUM", "QUAL", "VLUE", "SIZE", "RDVY",
    "VIG", "DGRO", "NOBL", "SDY", "VIGI",
    # 產業
    "XLK", "XLF", "XLV", "XLE", "XLU", "XLI", "XLP", "XLRE", "XLC", "XLB",
    "SMH", "SOXX", "XSD", "IBB", "XBI", "XPH", "IHI", "ITA", "XME", "XOP",
    "OIH", "GDX", "SIL", "JETS", "IYT", "XHB", "ITB", "KIE", "IAI", "IYT",
    # 債券
    "BND", "AGG", "TLT", "IEF", "SHY", "VGIT", "VGSH", "BIV", "BSV", "VCIT",
    "VCSH", "GOVT", "TIP", "SCHP", "LQD", "HYG", "BNDX", "VTEB", "MUB", "SHYG",
    "JNK", "EMB", "AGGY", "SPAB",
    # 國際
    "VEA", "IEFA", "VWO", "EFA", "EEM", "IEMG", "VXUS", "VPL", "VGK", "EWJ",
    "MCHI", "INDA", "EWZ", "EWG", "EWU", "ACWI", "ACWX", "AIA", "EWH", "EWW",
    # 商品
    "GLD", "SLV", "IAU", "GLDM", "USO", "UNG", "DBC", "PDBC", "GDXJ",
    # 其他規模大檔
    "DIA", "VWOB", "BIL", "SGOV", "PDBC", "SCHO", "AVUV", "AVDV", "GSIG", "IEF",
]


UNIVERSE_PATH = os.path.join(OUT_DIR, "index-universe.json")


def _log(msg):
    print(f"[fetch_us_data] {msg}", flush=True)


def _load_stock_candidates():
    """優先用 fetch_us_universe.py 產生的四大指數成分股清單（涵蓋面更完整、更即時），
    該檔案不存在（例如還沒跑過 fetch_us_universe.py）時，退回內建的 US_STOCK_CANDIDATES。
    2026-11-25：再併入 data/index-holdings/ 的 VOO/QQQ/SOXX/DIA 成分股 ticker
    （Ivan 指定的五 ETF 擴充來源；SMH 官網 cookie 牆，與 SOXX 重疊度高不影響）。"""
    syms = set()
    if os.path.exists(UNIVERSE_PATH):
        try:
            with open(UNIVERSE_PATH, encoding="utf-8") as f:
                doc = json.load(f)
            syms |= {s.strip().upper() for s in (doc.get("membership") or {}).keys() if s.strip()}
        except Exception as e:
            _log(f"⚠️ 讀取 index-universe.json 失敗：{e}")
    for sym in ("VOO", "QQQ", "SOXX", "DIA"):
        p = os.path.join(os.path.dirname(OUT_DIR), "index-holdings", f"{sym}.json")
        try:
            d = json.load(open(p, encoding="utf-8"))
            for h in d.get("holdings") or []:
                t = (h.get("ticker") or h.get("symbol") or h.get("Ticker") or "").strip().upper()
                if t:
                    syms.add(t)
        except Exception:
            continue
    if syms:
        _log(f"候選池：index-universe + index-holdings(VOO/QQQ/SOXX/DIA) 去重合計 {len(syms)} 檔")
        return sorted(syms)
    return US_STOCK_CANDIDATES


def _fetch_one_stock(yf, sym):
    try:
        t = yf.Ticker(sym)
        info = t.info or {}
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        chg = None
        if price is not None and prev_close:
            chg = round((price - prev_close) / prev_close * 100, 2)
        # 2026-11-22：同時抓取 cashflow 與 balance_sheet DataFrame，用於補齊 DCF 財務欄位
        try:
            df_cashflow = t.cashflow if t.cashflow is not None else None
        except Exception:
            df_cashflow = None
        try:
            df_balance_sheet = t.balance_sheet if t.balance_sheet is not None else None
        except Exception:
            df_balance_sheet = None
        return {
            "sym": sym,
            "name": info.get("shortName") or info.get("longName") or sym,
            "price": price,
            "chg": chg,
            "pe": info.get("trailingPE"),
            "pb": data_rules.us_price_to_book(info),  # 2026-11-13：舊值 priceToBook 對 BRK-B 等會失真
            "roe": round(info["returnOnEquity"] * 100, 2) if info.get("returnOnEquity") is not None else None,
            "eps": info.get("trailingEps"),
            "div": data_rules.us_dividend_yield_pct(info),  # 2026-11-13：yfinance dividendYield 已是百分比，不可再乘 100
            "market_cap": info.get("marketCap"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "currency": info.get("currency", "USD"),
            "exchange": info.get("exchange"),
            # 2026-11-17：DCF 估值輸入（百萬），缺值為 null；2026-11-22：改用 DataFrame 補齊缺失欄位
            **data_rules.us_valuation_inputs(info, df_cashflow=df_cashflow, df_balance_sheet=df_balance_sheet),
        }
    except Exception as e:
        _log(f"⚠️ {sym} 抓取失敗：{e}")
        return None


def _fetch_one_etf(yf, sym):
    try:
        t = yf.Ticker(sym)
        info = t.info or {}
        # 2026-11-13 修正：price 必須是「市場收盤價」，不可用 navPrice（淨值）。
        # 舊版 navPrice 優先 → 顯示的是淨值而非市價，且淨值通常晚一天才更新，
        # 導致 16/30 檔與市場收盤差 >0.5%（最大 3.64%），而 chg 卻是用市價的
        # previousClose 算的，價格與漲跌幅口徑不一致。淨值改存 nav 欄位供參考。
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        # 2026-11-27 修正（daily-update run 45940073429 事故）：Schwab/SPDR 等 ETF 在
        # 盤後／iNAV 換算時段，yfinance 的 currentPrice／regularMarketPrice 會回傳與
        # navPrice 位元級相同的值 → price 欄實際上是淨值（QA US_ETF_PRICE_IS_NAV 攔截）。
        # 此時改用近 5 日日 K 的最後收盤（真實成交價）作為市價；僅對異常標的多打一次
        # history API，正常標的零額外成本。
        if price is not None and info.get("navPrice") is not None \
                and abs(float(price) - float(info["navPrice"])) < 1e-9:
            try:
                h5 = t.history(period="5d", interval="1d")
                if h5 is not None and not h5.empty:
                    closes = h5.dropna(subset=["Close"])["Close"]
                    if len(closes):
                        price = float(closes.iloc[-1])
                        _log(f"ℹ️ {sym} info 價格等於淨值，改用日 K 收盤 {price}")
            except Exception as e:
                _log(f"⚠️ {sym} 日 K 收盤備援失敗：{e}")
        chg = None
        if price is not None and prev_close:
            chg = round((price - prev_close) / prev_close * 100, 2)
        return {
            "sym": sym,
            "name": info.get("shortName") or info.get("longName") or sym,
            "price": price,
            "nav": info.get("navPrice"),  # 淨值（僅供參考，不用於 price）
            "chg": chg,
            "net_assets": info.get("totalAssets"),  # 基金規模（近似市值，用於排序前 120 大）
            # 2026-11-13：改用 netExpenseRatio（annualReportExpenseRatio 實測 30/30 都回 None）
            "expense_ratio": data_rules.us_expense_ratio_pct(info),
            "yield": round(info["yield"] * 100, 2) if info.get("yield") is not None else None,
            "ytd_return": data_rules.us_ytd_pct(info.get("ytdReturn")),  # 2026-11-13：ytdReturn 已是百分比，不可再乘 100
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

    candidates = _load_stock_candidates()
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    _log(f"開始抓美股個股候選池（{len(candidates)} 檔候選，取市值前 {TOP_N_STOCKS} 大）")

    results = []
    for i, sym in enumerate(candidates):
        row = _fetch_one_stock(yf, sym)
        if row and row.get("market_cap") is not None:
            results.append(row)
        if i < len(candidates) - 1:
            time.sleep(SLEEP_SEC)

    results.sort(key=lambda r: r["market_cap"], reverse=True)
    top = results[:TOP_N_STOCKS]

    doc = {
        "meta": {
            "as_of": stamp,
            "source": "Yahoo Finance (yfinance)",
            "note": "候選池=index-universe(S&P500)＋index-holdings(VOO/QQQ/SOXX/DIA) 成分股，抓即時市值後本機排序取前 600 大；非官方交易所資料，僅供研究參考，非投資建議。",
            "candidate_pool_size": len(candidates),
            "count": len(top),
        },
        "stocks": top,
    }
    out_path = os.path.join(OUT_DIR, "us-stocks.json")
    carry_return_fields(out_path, top)
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
    _log(f"開始抓美股 ETF 候選池（{len(US_ETF_CANDIDATES)} 檔候選，取規模前 {TOP_N_ETFS} 大）")

    results = []
    etf_syms = list(dict.fromkeys(US_ETF_CANDIDATES))  # 去重保持順序
    for i, sym in enumerate(etf_syms):
        row = _fetch_one_etf(yf, sym)
        if row and row.get("net_assets") is not None:
            results.append(row)
        if i < len(etf_syms) - 1:
            time.sleep(SLEEP_SEC)

    results.sort(key=lambda r: r["net_assets"], reverse=True)
    top = results[:TOP_N_ETFS]

    doc = {
        "meta": {
            "as_of": stamp,
            "source": "Yahoo Finance (yfinance)",
            "note": "候選池=規模前 130 大美國 ETF 清單（含債券/商品/國際型），抓 net_assets 後本機排序取前 120 大；非官方交易所資料，僅供研究參考，非投資建議。",
            "candidate_pool_size": len(etf_syms),
            "count": len(top),
        },
        "etfs": top,
    }
    out_path = os.path.join(OUT_DIR, "us-etfs.json")
    carry_return_fields(out_path, top)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    _log(f"✅ 已寫入 {out_path}（{len(top)} 檔，候選池 {len(results)} 檔取得有效規模）")
    return True


RETURN_FIELDS = ("chg_1m", "chg_ytd", "chg_1y")


def carry_return_fields(out_path, rows):
    """2026-11-17：fetch_us_data 每日整檔覆寫，會把 fetch_us_returns.py 算好的月／年漲跌清掉。
    這裡先讀取舊檔，把同代號的報酬欄位帶回新資料；抓取失敗時仍保留前次數值。"""
    if not os.path.exists(out_path):
        return
    try:
        with open(out_path, encoding="utf-8") as f:
            old = {r.get("sym"): r for r in json.load(f).get("stocks" if out_path.endswith("stocks.json") else "etfs", [])}
    except Exception:
        return
    for r in rows:
        prev = old.get(r.get("sym"), {})
        for k in RETURN_FIELDS:
            if k not in r and k in prev:
                r[k] = prev[k]


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
