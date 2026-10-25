#!/usr/bin/env python3
"""
mklab-stock 美股四大指數成分股清單抓取（Build-Time，與 fetch_us_data.py 分工合作）。

⚠️ 跟 fetch_us_data.py 的分工：
  - 這支腳本負責「誰是誰的成分股」（道瓊工業指數 DJI / 那斯達克 100 指數 / S&P 500 /
    費城半導體指數 SOX 各自的成分股名單），輸出 data/us/index-universe.json
  - fetch_us_data.py 負責「市值前 30 大」排行，兩者互不依賴；fetch_us_data.py 可以
    選擇性讀取這份清單當作更完整的候選池，缺這份檔案時會自動退回原本內建的候選池

為什麼用 Wikipedia 而不是像台股那樣找官方 API：
  - 美股這四個指數都沒有官方免費、允許程式化存取的成分股清單 API（S&P/Nasdaq/Dow
    Jones 這些指數編制機構的官方資料都要付費訂閱）
  - Wikipedia 的「List of S&P 500 companies」「Nasdaq-100」「Dow Jones Industrial
    Average」「PHLX Semiconductor Sector」這幾頁有結構化表格、採用 CC BY-SA 授權
    （可重製利用），而且是業界公認拿來程式化取得這些清單的慣用做法（例如官方
    datasets/s-and-p-500-companies GitHub 專案就是這樣做的），跟 TWSE ETF
    投資篩選器那種明文禁止自動化擷取的網站性質不同，這裡沒有合規疑慮
  - 缺點：Wikipedia 是社群維護，理論上可能有更新延遲或筆誤，不是「官方」來源；
    如果要更嚴謹，之後可以改訂閱付費資料源，這支腳本先解決「免費、能動、能自動
    更新」的問題

用法：
  python3 skills/data/fetch_us_universe.py
"""
import datetime as dt
import json
import os
import re

OUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "us"))
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, "index-universe.json")

SOURCES = {
    "sp500": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
    "nasdaq100": "https://en.wikipedia.org/wiki/Nasdaq-100",
    "dji": "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average",
    "sox": "https://en.wikipedia.org/wiki/PHLX_Semiconductor_Sector",
}

HEADERS = {"User-Agent": "mklab-stock/1.0 (GitHub Actions; https://github.com/evanhsia-git/mklab-stock)"}


def _log(msg):
    print(f"[fetch_us_universe] {msg}", flush=True)


def _fetch_tables(url):
    """抓單一 Wikipedia 頁面，回傳頁面上所有表格（pandas.read_html 需要 lxml/html5lib）。"""
    import io
    import urllib.request
    import pandas as pd

    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    # 新版 pandas 要求傳入 file-like 物件或明確標示為字面 HTML，直接傳字串容易被誤判成檔案路徑
    return pd.read_html(io.StringIO(html))


def _clean_sym(sym):
    if sym is None:
        return None
    s = str(sym).strip().upper()
    s = re.sub(r"\[.*?\]", "", s)  # 去除 wiki 註腳 [1] 之類
    s = s.replace(".", "-")  # BRK.B -> BRK-B，對齊 yfinance 的代號慣例
    return s if re.match(r"^[A-Z0-9\-]{1,10}$", s) else None


def fetch_sp500():
    tables = _fetch_tables(SOURCES["sp500"])
    for t in tables:
        cols = [str(c).strip() for c in t.columns]
        if "Symbol" in cols:
            syms = [_clean_sym(s) for s in t["Symbol"].tolist()]
            syms = [s for s in syms if s]
            _log(f"S&P 500：解析出 {len(syms)} 檔")
            return syms
    _log("⚠️ S&P 500 頁面找不到預期的 Symbol 欄位，略過")
    return []


def fetch_nasdaq100():
    tables = _fetch_tables(SOURCES["nasdaq100"])
    for t in tables:
        cols = [str(c).strip() for c in t.columns]
        ticker_col = next((c for c in cols if c.lower() in ("ticker", "symbol")), None)
        if ticker_col and len(t) >= 90:  # Nasdaq-100 成分股表至少該有 ~100 列，排除誤抓到其他小表格
            syms = [_clean_sym(s) for s in t[ticker_col].tolist()]
            syms = [s for s in syms if s]
            _log(f"Nasdaq-100：解析出 {len(syms)} 檔")
            return syms
    _log("⚠️ Nasdaq-100 頁面找不到預期的成分股表格，略過")
    return []


def fetch_dji():
    tables = _fetch_tables(SOURCES["dji"])
    for t in tables:
        cols = [str(c).strip() for c in t.columns]
        ticker_col = next((c for c in cols if "symbol" in c.lower()), None)
        if ticker_col and 25 <= len(t) <= 35:  # 道瓊工業指數固定 30 檔
            syms = [_clean_sym(s) for s in t[ticker_col].tolist()]
            syms = [s for s in syms if s]
            _log(f"道瓊工業指數(DJI)：解析出 {len(syms)} 檔")
            return syms
    _log("⚠️ 道瓊工業指數頁面找不到預期的成分股表格，略過")
    return []


def fetch_sox():
    tables = _fetch_tables(SOURCES["sox"])
    for t in tables:
        cols = [str(c).strip() for c in t.columns]
        ticker_col = next((c for c in cols if c.lower() in ("ticker", "symbol")), None)
        if ticker_col and 20 <= len(t) <= 35:  # SOX 固定 30 檔左右
            syms = [_clean_sym(s) for s in t[ticker_col].tolist()]
            syms = [s for s in syms if s]
            _log(f"費城半導體指數(SOX)：解析出 {len(syms)} 檔")
            return syms
    _log("⚠️ SOX 頁面找不到預期的成分股表格，略過")
    return []


def main():
    try:
        import pandas  # noqa: F401
    except ImportError:
        _log("❌ 需要 pandas（還需要 lxml 解析 HTML 表格），請先 pip install pandas lxml")
        return

    membership = {}  # sym -> set(index_key)
    fetchers = {"sp500": fetch_sp500, "nasdaq100": fetch_nasdaq100, "dji": fetch_dji, "sox": fetch_sox}
    counts = {}
    for key, fn in fetchers.items():
        try:
            syms = fn()
        except Exception as e:
            _log(f"⚠️ {key} 抓取失敗（不中斷其他指數）：{e}")
            syms = []
        counts[key] = len(syms)
        for s in syms:
            membership.setdefault(s, set()).add(key)

    if not membership:
        _log("❌ 四個指數都沒抓到資料，未寫入任何檔案")
        return

    all_syms = sorted(membership.keys())
    doc = {
        "meta": {
            "as_of": dt.datetime.now().strftime("%Y-%m-%d"),
            "source": "Wikipedia（List of S&P 500 companies / Nasdaq-100 / Dow Jones Industrial Average / PHLX Semiconductor Sector），CC BY-SA，非官方付費資料源",
            "counts_by_index": counts,
            "combined_unique_count": len(all_syms),
            "note": "道瓊工業指數(DJI)/那斯達克100/SOX成分股絕大多數同時也是S&P500成分股，"
                    "combined_unique_count 是四個指數去重後的實際股票數，不是四個數字直接相加",
        },
        "membership": {s: sorted(membership[s]) for s in all_syms},
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    _log(f"✅ 已寫入 {OUT_PATH}")
    _log(f"   各指數檔數：{counts}")
    _log(f"   四個指數去重後合計：{len(all_syms)} 檔")


if __name__ == "__main__":
    main()
