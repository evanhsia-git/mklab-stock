"""第二階段（2026-11-22）：刪除 stocks.json 的孤兒欄位與過期重複欄位。
1) 19 個 official_*：與 official-fundamentals.json financial 逐筆 100% 相同，無寫入端、無讀取端
2) 14 個無引用欄位：前端與後端、欄位選單皆無引用
3) custody_fee：全部為 null，無寫入端寫入 stocks.json（費用表顯示來自 etf-meta.json）
4) ETF 列的 close：與 price 不一致，已過期（分割前的舊值，例：0050 180.0 vs 90.2），price 為最新價（與 K 線、每日快照一致）
不處理：management_fee／total_fee（與 etf-fees.csv 的 moneydj 欄位相同，需先決定費用權威來源）。
"""
import json, sys
path = sys.argv[1]
raw = open(path, encoding="utf-8").read()
doc = json.loads(raw)
DROP_FIXED = ["annualized_return_3y","annualized_return_5y","dividend_frequency","fee_checked_at",
              "holdings_coverage_pct","holdings_total_count","holdings_type","holdings_verified",
              "last_distribution_date","max_drawdown","return_10y","return_3y","sharpe_ratio",
              "volatility_1y","custody_fee"]
OFFICIAL = sorted({k for r in doc["stocks"] for k in r if k.startswith("official_")})
removed = {}
for r in doc["stocks"]:
    for k in DROP_FIXED + OFFICIAL:
        if k in r:
            removed[k] = removed.get(k, 0) + 1
            del r[k]
    if r.get("security_type") == "etf" and "close" in r:
        removed["close(ETF)"] = removed.get("close(ETF)", 0) + 1
        del r["close"]
print("removed:", json.dumps(removed, ensure_ascii=False, sort_keys=True))
out = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
open(path, "w", encoding="utf-8").write(out)
