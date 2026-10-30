#!/usr/bin/env python3
"""
TWSE OpenAPI 探測腳本（一次性，用來確認欄位名稱，不進排程）。

用途：ROE/ROA、月營收年增率、股利分派等官方端點的欄位名稱，需要用真實回傳確認後，
才能寫正式解析程式。本腳本只抓少量樣本，存到 data/probe/，請把檔案內容回傳給開發者。

用法（需要能連到 openapi.twse.com.tw 的環境，例如你的電腦或 GitHub Actions）：
  python3 skills/data/probe_twse_openapi.py
"""
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "probe")
ENDPOINTS = {
    "t187ap06_L_profitability": "https://openapi.twse.com.tw/v1/opendata/t187ap06_L",
    "t187ap05_L_monthly_revenue": "https://openapi.twse.com.tw/v1/opendata/t187ap05_L",
    "t187ap45_L_dividend": "https://openapi.twse.com.tw/v1/opendata/t187ap45_L",
    "t187ap47_L_fund_basic": "https://openapi.twse.com.tw/v1/opendata/t187ap47_L",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, url in ENDPOINTS.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mklab-stock-probe/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            sample = data[:3] if isinstance(data, list) else data
            keys = list(data[0].keys()) if isinstance(data, list) and data else []
            path = os.path.join(OUT, name + ".json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"url": url, "row_count": len(data) if isinstance(data, list) else None,
                           "keys": keys, "sample": sample}, f, ensure_ascii=False, indent=2)
            print(f"[probe] ✅ {name}：{len(data) if isinstance(data, list) else '?'} 筆，欄位 {len(keys)} 個 → {path}")
        except Exception as e:
            print(f"[probe] ❌ {name}：{e}")


if __name__ == "__main__":
    main()
