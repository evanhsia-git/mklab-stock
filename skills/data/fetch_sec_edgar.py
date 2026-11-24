#!/usr/bin/env python3
"""Fetch US stock financial data from SEC EDGAR Company Facts API.

目前僅列印說明，實際抓取與寫入請自行實作（需要合法 User-Agent
包含聯絡信箱，參考 SEC 政策）。

未來可依 CIK 到 submissions 取得最新 10-Q/10-K，解析
revenue、gross profit、operating income、net income、operating
cash flow、capital expenditure 等欄位，並更新
data/us/us-stocks.json 中對應記錄（若目前為 null 時填入，
否則保留原值）。

依原則：不得把 null 轉 0，若抓取失敗保持 null。
"""

import json, sys, os, time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# skills/data/fetch_sec_edgar.py → repo 根（parents[2] 慣例；2026-11-24 #311 修正：原 dirname
# 兩層只到 skills/，指向不存在的 skills/data/us/us-stocks.json）
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
US_STOCKS = os.path.join(ROOT, "data", "us", "us-stocks.json")

# SEC 要求 User-Agent 包含聯絡資訊
UA = "Ivan Admin evan.hsia@gmail.com"

def fetch_company_facts(cik: str) -> dict:
    """取得 Company Facts JSON（CIK 無前導 0，長度為 10）。"""
    url = f"https://data.sec.gov/api/xbrl/companyfacts/{cik}.json"
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except (HTTPError, URLError) as e:
        print(f"⚠️ SEC facts fetch error for CIK {cik}: {e}")
        return {}

def main():
    if not os.path.exists(US_STOCKS):
        print(f"⚠️ {US_STOCKS} 不存在，SEC EDGAR 跳過（缺清單不擋 job）")
        return
    with open(US_STOCKS, "r", encoding="utf-8") as f:
        data = json.load(f)
    stocks = data.get("stocks", [])
    updated = 0
    for rec in stocks:
        sym = rec.get("sym")
        if not sym:
            continue
        # 簡單的 CIK 對應：此處僅作為說明，實際上需要 CIK 對照表
        # 此處先跳過實際抓取，只列印符號
        print(f"Processing {sym}")
        time.sleep(0.5)  # polite rate‑limit
    # 目前不修改任何數值，只為了示範結構
    with open(US_STOCKS, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Finished SEC EDGAR fetch placeholder. Updated {updated} records (none changed).")

if __name__ == "__main__":
    main()