#!/usr/bin/env python3
"""產生「資料庫狀態」通知訊息（telegram-test workflow 的 db-status 模式用）。

資料誠信：全部實讀 checkout 內的真實 JSON，取不到標 N/A，不硬編碼。
輸出：stdout（workflow 導向訊息檔）。
"""
import datetime as dt
import json
import sys


def build(stocks_path="data/stocks.json", us_path="data/us/us-stocks.json") -> str:
    s = json.load(open(stocks_path, encoding="utf-8"))
    m = s.get("meta", {})
    stocks = s.get("stocks", [])
    n_etf = sum(1 for x in stocks if x.get("security_type") == "etf")
    n_stock = sum(1 for x in stocks if x.get("security_type") == "stock")
    try:
        us = json.load(open(us_path, encoding="utf-8")).get("meta", {})
    except (OSError, json.JSONDecodeError):
        us = {}
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    return "\n".join([
        "📊 MKLAB-STOCK 資料庫狀態",
        "",
        f"台股總數：{m.get('count', 'N/A'):,} 檔",
        f"　個股：{n_stock:,}　ETF：{n_etf:,}",
        f"行情基準日：{m.get('as_of', 'N/A')}",
        f"美股：{us.get('count', 'N/A')} 檔（{us.get('returns_as_of', 'N/A')}）",
        "",
        f"查詢時間：{now.strftime('%Y-%m-%d %H:%M')} 台北",
        "網站：https://evanhsia-git.github.io/mklab-stock/",
    ])


if __name__ == "__main__":
    sys.stdout.write(build() + "\n")
