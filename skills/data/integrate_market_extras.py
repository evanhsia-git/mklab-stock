#!/usr/bin/env python3
"""把 data/market-extras.json 的「暫停交易」狀態套用到 data/stocks.json（冪等、不增不減檔數）。

**為什麼不把月營收／融資融券／三率塞進 stocks.json**：
`stocks.json` 每一頁都要下載，2026-11-10 已立下「單檔 1,300 KB」預算（tests/test_known_errors.py）。
實測把 17 個加值欄位寫進去會從 1,213 KB 暴增到 1,751 KB（+538 KB）——遠超預算。
因此加值資料留在獨立的 `data/market-extras.json`（779 KB，按需載入），
只有「會改變交易狀態語意」的停牌欄位寫進主檔（僅影響 0–3 檔，體積可忽略）。

寫入 stocks.json 的欄位：

| 來源 | 欄位 |
|---|---|
| 暫停交易 TWTAWU | `halt_date`、`halt_resume`；仍在停止期間者 `trading_status='suspended'`＋`suspended_reason='halt'` |

刻意不併入的：
- **`eps_official`（t187ap14_L）**：官方為「累計 EPS」、本站 `eps` 為「累計年化」，基準不同，
  直接併會讓同一列的 eps 與 pe 互相矛盾。只用於交叉驗證。
- 月營收／融資融券／官方三率：體積考量，留在 market-extras.json 由前端按需載入。
"""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "data")
EXTRAS = os.path.join(DATA, "market-extras.json")
STOCKS = os.path.join(DATA, "stocks.json")
TZ = dt.timezone(dt.timedelta(hours=8))

REV_KEYS = ["rev_ym", "rev_month", "rev_mom", "rev_yoy", "rev_ytd", "rev_ytd_yoy"]
MAR_KEYS = ["margin_fin", "margin_sec", "margin_fin_prev", "margin_sec_prev"]
PROF_KEYS = ["gross_margin_off", "operating_margin_off", "net_margin_off", "profit_period", "profit_asof"]
HALT_KEYS = ["halt_date", "halt_resume"]

# 低於此覆蓋率視為來源異常，中止不覆蓋（避免把好資料洗掉）
MIN_COVERAGE = {"revenue": 500, "margin": 500, "profitability": 400}


def is_halted_on(halt, today):
    """該檔在 today 這天是否「仍在暫停交易」期間。

    TWTAWU 是「暫停交易證券」清單，內容可能是**已經恢復**的紀錄
    （實測 2026-11-14：2314 台揚 停止 11/10、恢復 11/11 —— 早已恢復）。
    因此必須比對日期，否則會把已恢復的股票誤標成停牌（＝製造錯誤資料）。
    """
    if not halt:
        return False
    start = halt.get("halt_date")
    if not start or start > today:
        return False
    resume = halt.get("resume_date")
    return resume is None or resume > today  # 無恢復日＝仍在停；恢復日已過＝已恢復


def merge_record(rec, extras, today):
    """只把「暫停交易」狀態套用到主檔；加值資料留在 market-extras.json（見檔頭說明）。"""
    sym = rec.get("sym")
    filled = 0

    halt = extras["halts"].get(sym)
    rec["halt_date"] = halt.get("halt_date") if halt else None
    rec["halt_resume"] = halt.get("resume_date") if halt else None

    # 只有「本檔造成的停牌」才由本檔解除（suspended_reason='halt'），
    # 其他原因造成的 suspended（例如無當日成交價）一律不動。
    if is_halted_on(halt, today):
        rec["trading_status"] = "suspended"
        rec["suspended_reason"] = "halt"
    elif rec.get("suspended_reason") == "halt":
        rec["trading_status"] = "active"
        rec.pop("suspended_reason", None)
    return filled


def main():
    if not os.path.exists(EXTRAS):
        print(f"找不到 {EXTRAS}，先跑 fetch_market_extras.py", file=sys.stderr)
        return 2
    extras = json.load(open(EXTRAS, encoding="utf-8"))
    snap = json.load(open(STOCKS, encoding="utf-8"))
    stocks = snap["stocks"]

    counts = extras["meta"]["counts"]
    short = {k: v for k, v in MIN_COVERAGE.items() if counts.get(k, 0) < v}
    if short:
        print(f"來源覆蓋率不足 {short}（實得 {counts}），中止不覆蓋", file=sys.stderr)
        return 2

    # 以快照資料日判斷「是否仍在停止交易期間」；無 as_of 才退回執行當日
    today = extras["meta"].get("as_of") or dt.datetime.now(TZ).strftime("%Y-%m-%d")
    before = len(stocks)
    filled = sum(merge_record(s, extras, today) for s in stocks)
    after = len(stocks)
    if before != after:
        print(f"檔數改變 {before} → {after}，中止", file=sys.stderr)
        return 2

    # 主檔只記「加值資料在哪、有多少」；資料本體在 market-extras.json，不佔主檔體積
    halted = sorted(s["sym"] for s in stocks if s.get("suspended_reason") == "halt")
    snap["meta"]["market_extras"] = {
        "integrated_at": dt.datetime.now(TZ).isoformat(timespec="seconds"),
        "source_as_of": extras["meta"]["as_of"],
        "source_file": "data/market-extras.json",
        "endpoints": extras["meta"]["endpoints"],
        "counts": extras["meta"]["counts"],
        "halted": halted,
        "note": "加值資料（月營收／融資融券／官方營益分析／官方累計EPS／開休市日）本體在 "
                "data/market-extras.json，前端按需載入；stocks.json 只保留停牌欄位（體積預算）。"
                "官方累計 EPS 與本站年化 eps 基準不同，僅供交叉驗證。",
    }
    cov = {"halted": len(halted)}

    with open(STOCKS, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, separators=(",", ":"))

    print(f"已併入 {after} 檔（寫入 {filled} 個非空值）")
    for k, v in cov.items():
        print(f"  {k:<20} {v}/{after}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
