#!/usr/bin/env python3
"""
fetch_us_returns.py — 美股個股／ETF 的月漲跌（chg_1m）、年初至今（chg_ytd）、年漲跌（chg_1y）

資料來源：yfinance Ticker.history（auto_adjust=True，已含除權息調整，ETF 與高配息股報酬才正確）。
輸出：直接更新 data/us/us-stocks.json 與 data/us/us-etfs.json 的每一筆，欄位名稱與台股一致。

定義（以交易日計）：
  chg_1m  : 最後收盤 ÷ 21 個交易日前收盤 − 1
  chg_1y  : 最後收盤 ÷ 252 個交易日前收盤 − 1
  chg_ytd : 最後收盤 ÷ 上一年度最後一個收盤 − 1（年初至今）

失敗處理（寧缺勿錯）：
  - 抓取失敗或資料過舊（最後一根 K 棒距 as_of 超過 7 天）→ 保留該檔「前次」數值，並記入 meta.returns_failed
  - 計算結果超出 ±1000% → 視為異常，設為 null
  - 失敗比例超過 50% → 回傳非零結束碼，讓 CI 失敗、不推送
"""
import datetime as dt
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STOCKS_PATH = os.path.join(ROOT, "data", "us", "us-stocks.json")
ETFS_PATH = os.path.join(ROOT, "data", "us", "us-etfs.json")

MONTH_SESSIONS = 21
YEAR_SESSIONS = 252
MAX_STALE_DAYS = 7
MAX_ABS_PCT = 1000.0
FAIL_RATIO_LIMIT = 0.5


def _pct(last, base):
    if last is None or base is None or base <= 0:
        return None
    v = (last / base - 1.0) * 100.0
    if abs(v) > MAX_ABS_PCT:
        return None
    return round(v, 2)


def compute_returns(series, as_of):
    """series: [(date, close)] 任意順序；as_of: date。
    回傳 {chg_1m, chg_ytd, chg_1y}；資料不足或過舊的欄位為 None。
    若整體過舊（最後一根距 as_of 超過 MAX_STALE_DAYS），三欄全為 None。"""
    out = {"chg_1m": None, "chg_ytd": None, "chg_1y": None}
    rows = sorted((d, float(c)) for d, c in series if c is not None and c == c and c > 0 and d <= as_of)
    if not rows:
        return out
    last_d, last_c = rows[-1]
    if (as_of - last_d).days > MAX_STALE_DAYS:
        return out
    closes = [c for _, c in rows]
    n = len(closes)
    if n > MONTH_SESSIONS:
        out["chg_1m"] = _pct(last_c, closes[n - 1 - MONTH_SESSIONS])
    if n > YEAR_SESSIONS:
        out["chg_1y"] = _pct(last_c, closes[n - 1 - YEAR_SESSIONS])
    prev_year = [c for d, c in rows if d.year < last_d.year]
    if prev_year:
        out["chg_ytd"] = _pct(last_c, prev_year[-1])
    return out


def fetch_closes_yf(sym):
    """以 yfinance 取得近 2 年日線收盤（已調整）。失敗拋出例外，由呼叫端處理。"""
    import yfinance as yf
    df = yf.Ticker(sym).history(period="2y", auto_adjust=True)
    if df is None or df.empty:
        return []
    return [(idx.date(), float(c)) for idx, c in zip(df.index, df["Close"]) if c == c]


def _load(path):
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    return json.loads(raw), raw


def _dump(path, doc, raw_before):
    pretty = raw_before.startswith("{\n")
    nl = "\n" if raw_before.endswith("\n") else ""  # 與原檔一致（fetch_us_data 寫出的檔案無結尾換行）
    text = json.dumps(doc, ensure_ascii=False, indent=2) + nl if pretty \
        else json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def update_file(path, key, fetch, as_of, sleep_sec, failed, stats):
    doc, raw = _load(path)
    for rec in doc.get(key, []):
        sym = rec.get("sym")
        stats["total"] += 1
        try:
            series = fetch(sym)
            res = compute_returns(series, as_of)
            if all(v is None for v in res.values()):
                raise ValueError("無有效收盤資料或資料過舊")
        except Exception as e:  # 單檔失敗不中斷
            failed.append({"sym": sym, "reason": str(e)[:120]})
            stats["fail"] += 1
            res = None
        if res is not None:
            rec.update(res)  # 只覆寫成功的欄位；失敗檔保留前次數值
        if sleep_sec:
            time.sleep(sleep_sec)
    return doc, raw


def run(stocks_path=STOCKS_PATH, etfs_path=ETFS_PATH, fetch=fetch_closes_yf,
        as_of=None, sleep_sec=1.2, dry_run=False):
    as_of = as_of or dt.date.today()
    total = fail = 0
    for path, key in ((stocks_path, "stocks"), (etfs_path, "etfs")):
        failed = []
        stats = {"total": 0, "fail": 0}
        doc, raw = update_file(path, key, fetch, as_of, sleep_sec, failed, stats)
        doc.setdefault("meta", {})
        doc["meta"]["returns_as_of"] = as_of.isoformat()
        doc["meta"]["returns_source"] = "yfinance history(auto_adjust=True)"
        doc["meta"]["returns_failed"] = [f["sym"] for f in failed]
        if not dry_run:
            _dump(path, doc, raw)
        total += stats["total"]
        fail += stats["fail"]
        print(f"[us-returns] {key}: 共 {stats['total']} 檔，失敗 {stats['fail']} 檔")
        for f in failed[:10]:
            print(f"    {f['sym']}: {f['reason']}")
    ratio = (fail / total) if total else 1.0
    print(f"[us-returns] 合計失敗率 {ratio:.0%}（上限 {FAIL_RATIO_LIMIT:.0%}）")
    return 1 if ratio > FAIL_RATIO_LIMIT else 0


if __name__ == "__main__":
    sys.exit(run(dry_run="--dry-run" in sys.argv))
