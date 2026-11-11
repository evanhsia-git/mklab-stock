#!/usr/bin/env python3
"""
mklab-stock 技術指標計算（Build-Time，完全基於 data/history/ 既有的每日快照）。

設計原則：
  - 不對外發送任何 API 請求，純粹讀取本地已抓好的 data/history/*.json 逐日快照做數學計算。
  - 計算結果只是每檔股票幾個額外的數字欄位（ma5/ma10/ma20/ma30/rsi14/macd_dif/macd_dea/
    macd_hist/kd_k/kd_d），直接寫回 data/stocks.json 既有紀錄裡，不新增任何前端要下載的
    檔案，不會對網站的檔案大小或載入效能造成負擔。
  - 歷史天數不足以算出某項指標時（例如新上市股票），該欄位一律輸出 null，絕不用其他數值
    冒充或推測（比照全站「資料不足即為 null，不自行推測」的原則）。

用法：
  python3 skills/data/compute_indicators.py
"""
import datetime as dt
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HISTORY_DIR = os.path.join(ROOT, "data", "history")
STOCKS_PATH = os.path.join(ROOT, "data", "stocks.json")

# 280 個交易日：足以算出 MA30 / RSI14 / MACD(12,26,9) / KD(9)，並留一些讓 EMA 收斂的緩衝
LOOKBACK_DAYS = 280  # 52 週位階需要約 1 年的交易日（原 90 日，改為 280 以覆蓋 52 週）
MIN_FOR_MACD = 35  # 26 日 EMA + 9 日訊號線緩衝
MIN_FOR_RSI = 15   # 14 期漲跌幅 + 1
MIN_FOR_KD = 9


def load_series(limit: "int | None" = LOOKBACK_DAYS):
    """回傳 {股票代號: [(date, open, high, low, close), ...]}，依日期由舊到新排序。

    limit=None 代表不截斷（讀 history/ 全部），給 build_kline.py 用——K 線是使用者的
    歷史資料，不該被「算指標剛好夠用」的天數限制住。算指標的呼叫端維持預設
    LOOKBACK_DAYS（MA30/RSI14/MACD/KD 只需要約 280 日，讀更多只是變慢）。
    """
    files = sorted(glob.glob(os.path.join(HISTORY_DIR, "*.json")))
    if limit:
        files = files[-limit:]
    series = {}
    for fp in files:
        date = os.path.basename(fp)[:-5]
        try:
            with open(fp, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        for row in d.get("stocks", []):
            sym = row.get("stock_id")
            if sym is None or str(sym).endswith("U"):  # 排除 U 尾（期貨 ETF / 認購權證）
                continue
            close = row.get("close")
            if sym is None or close is None:
                continue
            o = row.get("open")
            h = row.get("high")
            l = row.get("low")
            o = o if o is not None else close
            h = h if h is not None else close
            l = l if l is not None else close
            series.setdefault(sym, []).append((date, o, h, l, close))
    return {sym: clean_spikes(rows) for sym, rows in series.items()}


def load_kline_rows(sym):
    """讀 data/kline/{代號}.json → [(YYYYMMDD, open, high, low, close), ...]。

    為什麼指標要參考 K 線檔：history/ 只有近約一年的快照，但 K 線檔可能含有更長的歷史
    （skills/data/backfill_etf_history.py 回補的「上市以來」日線只存在 K 線檔，history/
    裡該代號可能只有 1~2 天）。指標一律用兩者中較長的那一份，才是資訊最完整的算法。
    """
    path = os.path.join(ROOT, "data", "kline", f"{sym}.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            rows = json.load(f).get("rows", [])
    except (OSError, json.JSONDecodeError):
        return []
    return [(str(r[0]).replace("-", ""), r[1], r[2], r[3], r[4]) for r in rows]


def clean_spikes(rows):
    """過濾歷史收盤的單點離群值（典型錯誤資料：某日與前後兩日都差超過 25%，且前後兩日彼此接近）。
    以前後兩日的平均取代該點。只用於指標計算，不改寫 data/history/ 原始快照。
    rows 為 (date, open, high, low, close) 清單，回傳新的清單。"""
    out = list(rows)
    for i in range(1, len(out) - 1):
        p, x, q = out[i-1][4], out[i][4], out[i+1][4]
        if p and x and q and abs(x/p-1) > 0.25 and abs(x/q-1) > 0.25 and abs(p/q-1) < 0.1:
            d, o, h, l, _ = out[i]
            out[i] = (d, o, h, l, round((p + q) / 2, 2))
    return out


def sma(closes, n):
    if len(closes) < n:
        return None
    return round(sum(closes[-n:]) / n, 2)


def ema_series(values, n):
    if not values:
        return []
    k = 2.0 / (n + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def calc_rsi(closes, n=14):
    if len(closes) < n + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-n:]) / n
    avg_loss = sum(losses[-n:]) / n
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def calc_macd(closes):
    if len(closes) < MIN_FOR_MACD:
        return None, None, None
    ema12 = ema_series(closes, 12)
    ema26 = ema_series(closes, 26)
    n = min(len(ema12), len(ema26))
    dif_series = [ema12[-n:][i] - ema26[-n:][i] for i in range(n)]
    dea_series = ema_series(dif_series, 9)
    dif = dif_series[-1]
    dea = dea_series[-1]
    return round(dif, 2), round(dea, 2), round(dif - dea, 2)


def calc_kd(highs, lows, closes, n=9):
    if len(closes) < n:
        return None, None
    k, d = 50.0, 50.0
    for i in range(n - 1, len(closes)):
        hh = max(highs[i - n + 1:i + 1])
        ll = min(lows[i - n + 1:i + 1])
        rsv = 50.0 if hh == ll else (closes[i] - ll) / (hh - ll) * 100
        k = k * 2 / 3 + rsv * 1 / 3
        d = d * 2 / 3 + k * 1 / 3
    return round(k, 1), round(d, 1)


def calc_chg(rows, days):
    """區間漲跌幅（%）：最新收盤 vs 不晚於「最新日 - days 個日曆天」的最近一個交易日收盤。
    rows 為 (date, open, high, low, close)，已依日期由舊到新排序。
    找不到基準日（歷史不足）回傳 None，不推測、不補 0。"""
    if len(rows) < 2:
        return None
    latest = dt.datetime.strptime(rows[-1][0], "%Y%m%d").date()
    target = latest - dt.timedelta(days=days)
    base = None
    for r in rows:
        if dt.datetime.strptime(r[0], "%Y%m%d").date() <= target:
            base = r[4]
    if base is None or base == 0:
        return None
    return round((rows[-1][4] - base) / base * 100, 2)


# 報酬期間（日曆天）：1 月 30、3 月 91、6 月 182、1 年 365、2 年 730
def calc_chg_1m(rows):
    return calc_chg(rows, 30)


def calc_chg_1y(rows):
    return calc_chg(rows, 365)


# chg_2y 已預先計算但前端暫不開放：history 目前只有約 14 個月，大部分標的為 null；累積滿 2 年後自然有值
CHG_PERIODS = {"chg_1m": 30, "chg_3m": 91, "chg_6m": 182, "chg_1y": 365, "chg_2y": 730}


def calc_pos52(rows):
    """52 週位階：以最近約一年的收盤價算最高/最低，將目前收盤落在 5 個等寬區間之一（1~5）。
    歷史覆蓋不足 300 天（例如新上市）回傳 None，不推測。"""
    empty = {"pos52w_level": None}
    if len(rows) < 2:
        return empty
    last = dt.datetime.strptime(rows[-1][0], "%Y%m%d").date()
    cutoff = last - dt.timedelta(days=365)
    win = [r for r in rows if dt.datetime.strptime(r[0], "%Y%m%d").date() > cutoff]
    if not win:
        return empty
    first = dt.datetime.strptime(win[0][0], "%Y%m%d").date()
    if (last - first).days < 300:
        return empty
    closes = [r[4] for r in win]
    hi, lo, cur = max(closes), min(closes), closes[-1]
    if hi == lo:
        level = 3
    else:
        pos = (cur - lo) / (hi - lo)
        level = min(int(pos * 5), 4) + 1  # 0-20%→1, 20-40%→2, 40-60%→3, 60-80%→4, 80-100%→5
    return {"pos52w_level": level}


def main():
    print("[compute_indicators] 讀取 data/history/ ...")
    series = load_series()
    print(f"[compute_indicators] 取得 {len(series)} 檔股票的歷史序列（最多回溯 {LOOKBACK_DAYS} 個交易日）")

    with open(STOCKS_PATH, encoding="utf-8") as f:
        stocks_doc = json.load(f)

    updated = 0
    for row in stocks_doc.get("stocks", []):
        sym = row.get("sym")
        rows = series.get(sym)
        # K 線檔可能比 history/（僅近一年）更長（回補的上市以來資料），取較長的一份算指標。
        # 不這樣做的話，history/ 只有 1~2 天的代號會被算成全部 null，把回補的指標蓋掉。
        krows = load_kline_rows(sym)
        if len(krows) > len(rows or []):
            rows = krows
        if not rows:
            row["ma5"] = row["ma10"] = row["ma20"] = row["ma30"] = None
            row["rsi14"] = None
            row["macd_dif"] = row["macd_dea"] = row["macd_hist"] = None
            row["kd_k"] = row["kd_d"] = None
            for _k in CHG_PERIODS:
                row[_k] = None
            row.update({"pos52w_level": None})
            continue

        closes = [r[4] for r in rows]
        highs = [r[2] for r in rows]
        lows = [r[3] for r in rows]

        for _k, _d in CHG_PERIODS.items():
            row[_k] = calc_chg(rows, _d)
        row.update(calc_pos52(rows))
        row["ma5"] = sma(closes, 5)
        row["ma10"] = sma(closes, 10)
        row["ma20"] = sma(closes, 20)
        row["ma30"] = sma(closes, 30)
        row["rsi14"] = calc_rsi(closes, 14) if len(closes) >= MIN_FOR_RSI else None
        dif, dea, hist = calc_macd(closes)
        row["macd_dif"], row["macd_dea"], row["macd_hist"] = dif, dea, hist
        k, d = calc_kd(highs, lows, closes, 9) if len(closes) >= MIN_FOR_KD else (None, None)
        row["kd_k"], row["kd_d"] = k, d
        updated += 1

    # P0-1：ETF / 一般股票分類以官方 ETF 清單為唯一依據（data/etf-meta.json）。
    # 清單內 → etf；代號像 ETF（00 開頭）但不在清單 → unverified（待確認，不計入 ETF 也不計入一般股）；其餘 → stock
    etf_official = set()
    try:
        etf_official = {e["sym"] for e in json.load(open(os.path.join(ROOT, "data", "etf-meta.json"), encoding="utf-8")).get("etfs", [])}
        _sp = os.path.join(ROOT, "data", "etf-supplement.json")
        if os.path.exists(_sp):
            etf_official |= {e["sym"] for e in json.load(open(_sp, encoding="utf-8")).get("etfs", [])}
    except (OSError, json.JSONDecodeError):
        pass
    for row in stocks_doc.get("stocks", []):
        sym = str(row.get("sym", ""))
        if sym in etf_official:
            row["security_type"], row["is_etf"] = "etf", True
        elif sym.startswith("00"):
            row["security_type"], row["is_etf"] = "unverified", False
        elif not (len(sym) == 4 and sym.isdigit() and not sym.startswith("91")):
            # 非普通股代碼（特別股、DR、受益證券、ETN、權證等）：本站不收，標 other 後下方整批移除
            # 2026-11-10 修：DR 是 4 碼純數字（91xx），舊條件會把它判成 stock 而逃過 other 移除。
            # TWSE 產業別 91 = 存託憑證 → 4 碼 91 開頭一律 other。
            # ⚠️ 必須與 fetch_data.py 的 classify_security() 同步（tests 有一致性檢查）。
            row["security_type"], row["is_etf"] = "other", False
        else:
            row["security_type"], row["is_etf"] = "stock", False

    # 規矩：只留 上市一般股票 / 上市 ETF / 上櫃 ETF；特別股、DR、受益證券、ETN、權證等（other）一律不收
    _before = len(stocks_doc.get("stocks", []))
    stocks_doc["stocks"] = [r for r in stocks_doc.get("stocks", []) if r.get("security_type") != "other"]
    if len(stocks_doc["stocks"]) != _before:
        print(f"[compute_indicators] 移除其他證券 {_before - len(stocks_doc['stocks'])} 筆（本站不收特別股等）")

    # 上面會改變檔數（移除 other 類），所以 meta 必須一起重算——否則 meta.count／sources／
    # price_asof_counts 會與實際陣列脫節（2026-11-10 實測：清掉 4 檔 DR 後 meta.count 仍停在 1448）。
    # 邏輯與 fetch_data.recompute_meta() 相同（tests 有 count／sources 一致性檢查）。
    _s = stocks_doc.get("stocks", [])
    _meta = stocks_doc.setdefault("meta", {})
    _src, _pa = {}, {}
    for _r in _s:
        _src[_r.get("source")] = _src.get(_r.get("source"), 0) + 1
        _pa[_r.get("price_asof")] = _pa.get(_r.get("price_asof"), 0) + 1
    _meta["count"], _meta["sources"], _meta["price_asof_counts"] = len(_s), _src, _pa

    with open(STOCKS_PATH, "w", encoding="utf-8") as f:
        json.dump(stocks_doc, f, ensure_ascii=False, indent=None, separators=(",", ":"))

    print(f"[compute_indicators] 已為 {updated} 檔股票寫入 MA/RSI/MACD/KD 欄位（資料不足者為 null）")


if __name__ == "__main__":
    main()
