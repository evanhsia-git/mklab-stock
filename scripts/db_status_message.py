#!/usr/bin/env python3
"""產生「資料庫狀態」通知訊息（telegram-test workflow 的 db-status 模式用）。

資料誠信：全部實讀 checkout 內的真實 JSON，覆蓋率=有值檔數/總數動態計算；
資料庫不含的欄位（毛利率/淨利率/負債比）標 N/A，不硬編碼、不猜測。
輸出：stdout（workflow 導向訊息檔）。
"""
import datetime as dt
import json


def _cov(stocks, field):
    n = len(stocks)
    if not n:
        return "N/A", 0, 0
    have = sum(1 for x in stocks if x.get(field) not in (None, ""))
    return f"{have}/{n} = {have / n * 100:.1f}%", have, n


def build(stocks_path="data/stocks.json", us_path="data/us/us-stocks.json",
          us_etfs_path="data/us/us-etfs.json") -> str:
    s = json.load(open(stocks_path, encoding="utf-8"))
    m = s.get("meta", {})
    stocks = s.get("stocks", [])
    ind = [x for x in stocks if x.get("security_type") == "stock"]
    etf = [x for x in stocks if x.get("security_type") == "etf"]
    asof = m.get("as_of", "N/A")

    def _load(path):
        try:
            return json.load(open(path, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    us = _load(us_path).get("meta", {})
    us_etf_doc = _load(us_etfs_path)
    n_us_etf = len(us_etf_doc.get("etfs") or us_etf_doc.get("stocks") or []) or None
    us_etf_date = us_etf_doc.get("meta", {}).get("as_of", "N/A")

    rows_short = []
    rows_full = []
    for label, field in (("PE", "pe"), ("PB", "pb"), ("ROE", "roe"),
                         ("ROA", "roa"), ("EPS", "eps"), ("殖利率", "div"),
                         ("毛利率", "gross_margin"), ("淨利率", "net_margin"),
                         ("負債比", "debt_ratio"), ("市值", "market_cap"),
                         ("發行股數", "shares")):
        txt, have, n = _cov(ind, field)
        if field in ("gross_margin", "net_margin", "debt_ratio"):
            rows_short.append(f"{label} 覆蓋率: N/A")
            rows_full.append(f"{label}: N/A（資料庫未含此欄）")
        else:
            rows_short.append(f"{label} 覆蓋率: {have}/{n}")
            rows_full.append(f"{label}: {txt}")

    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    return "\n".join([
        "📊 資料庫狀態:",
        f"總筆數: {m.get('count', 'N/A'):,}",
        *rows_short,
        f"📈 覆蓋率 - stocks.json (個股 {len(ind):,} 檔):",
        *rows_full,
        "📋 股票庫存量:",
        f"上市股票: {len(ind):,} 檔",
        f"ETF: {len(etf):,} 檔",
        f"全部: {len(stocks):,} 檔",
        f"美股個股: {us.get('count', 'N/A')} 檔",
        f"美股ETF: {n_us_etf if n_us_etf is not None else 'N/A'} 檔",
        f"資料日期: {asof}",
        f"查詢時間: {now.strftime('%Y-%m-%d %H:%M')} 台北",
    ])


if __name__ == "__main__":
    import sys
    sys.stdout.write(build() + "\n")
