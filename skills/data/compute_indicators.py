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
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HISTORY_DIR = os.path.join(ROOT, "data", "history")
STOCKS_PATH = os.path.join(ROOT, "data", "stocks.json")

# 90 個交易日：足以算出 MA30 / RSI14 / MACD(12,26,9) / KD(9)，並留一些讓 EMA 收斂的緩衝
LOOKBACK_DAYS = 90
MIN_FOR_MACD = 35  # 26 日 EMA + 9 日訊號線緩衝
MIN_FOR_RSI = 15   # 14 期漲跌幅 + 1
MIN_FOR_KD = 9


def load_series():
    """回傳 {股票代號: [(date, open, high, low, close), ...]}，依日期由舊到新排序。"""
    files = sorted(glob.glob(os.path.join(HISTORY_DIR, "*.json")))[-LOOKBACK_DAYS:]
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
    return series


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
        if not rows:
            row["ma5"] = row["ma10"] = row["ma20"] = row["ma30"] = None
            row["rsi14"] = None
            row["macd_dif"] = row["macd_dea"] = row["macd_hist"] = None
            row["kd_k"] = row["kd_d"] = None
            continue

        closes = [r[4] for r in rows]
        highs = [r[2] for r in rows]
        lows = [r[3] for r in rows]

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

    with open(STOCKS_PATH, "w", encoding="utf-8") as f:
        json.dump(stocks_doc, f, ensure_ascii=False, indent=None, separators=(",", ":"))

    print(f"[compute_indicators] 已為 {updated} 檔股票寫入 MA/RSI/MACD/KD 欄位（資料不足者為 null）")


if __name__ == "__main__":
    main()
