#!/usr/bin/env python3
"""
mklab-stock GitHub Actions 每日資料抓取腳本（Build-Time, 雲端免 key）。

設計原則（用戶最高原則：GitHub-Native / Fork First / 零外部依賴 / 零 secret）：
  - 主源 TWSE OpenAPI（官方、免 key、雲端可達）抓收盤+PE/PB/殖利率+漲跌
  - ROE/ROA 由 yfinance（免 key）補，但降頻（weekly 模式，避免 IP ban）
  - 產業分類用本 repo 既有 data/industry-codes.json（33 類官方對照）
  - 產出 schema 與 scripts/export_db.py（本機灌種）完全一致，確保歷史銜接
  - Graceful Degradation：單檔失敗不中斷，欄位給 null
  - 休市判斷：TWSE 回傳空/非最新交易日 → 標註跳過

兩種模式：
  python scripts/fetch_data.py daily    # 每日：TWSE 收盤+PE/PB/殖利率（快，~1min）
  python scripts/fetch_data.py weekly    # 每週六：yfinance ROE/ROA（sleep 3s 防 ban，~70min）
"""
import json
import os
import sys
import re
import time
import datetime as dt
import urllib.request
import urllib.error

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
os.makedirs(OUT, exist_ok=True)
os.makedirs(os.path.join(OUT, "history"), exist_ok=True)

# ===== 結構化 Log 系統（供 GitHub Actions 留存 + 使用者確認抓取成功）=====
class RunLogger:
    """收集本輪抓取的結構化記錄，最後輸出總結並寫入 data/fetch-log.{json,txt}。"""
    def __init__(self, mode):
        self.mode = mode
        self.start = dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
        self.entries = []  # (level, msg)
        self.stats = {"mode": mode, "success": False, "error": None,
                      "fetched": 0, "written": 0, "skipped": False,
                      "details": {}}

    def log(self, level, msg):
        ts = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime("%H:%M:%S")
        line = f"[{ts}] {level} {msg}"
        self.entries.append((level, msg))
        print(line, flush=True)

    def info(self, msg):  self.log("INFO", msg)
    def warn(self, msg):  self.log("WARN", msg)
    def error(self, msg): self.log("ERROR", msg)

    def finish(self, success, error=None):
        self.stats["success"] = success
        self.stats["error"] = error
        self.stats["end"] = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
        self.stats["duration_sec"] = round((dt.datetime.now(dt.timezone(dt.timedelta(hours=8))) - self.start).total_seconds(), 1)
        self.stats["start"] = self.start.strftime("%Y-%m-%d %H:%M:%S")
        # 總結報告
        print("", flush=True)
        print("=" * 56, flush=True)
        if success:
            print(f"  ✅ 抓取成功 | 模式={self.mode}", flush=True)
        else:
            print(f"  ❌ 抓取失敗 | 模式={self.mode}", flush=True)
        print(f"  開始: {self.stats['start']}", flush=True)
        print(f"  結束: {self.stats['end']} (耗時 {self.stats['duration_sec']}s)", flush=True)
        print(f"  抓取筆數: {self.stats['fetched']}", flush=True)
        print(f"  寫入筆數: {self.stats['written']}", flush=True)
        if self.stats.get("skipped"):
            print(f"  狀態: 跳過（休市/無資料）", flush=True)
        if error:
            print(f"  錯誤: {error}", flush=True)
        for k, v in self.stats.get("details", {}).items():
            print(f"  - {k}: {v}", flush=True)
        print("=" * 56, flush=True)
        self._write_files()

    def _write_files(self):
        # 機器可讀
        with open(os.path.join(OUT, "fetch-log.json"), "w", encoding="utf-8") as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)
        # 人讀（含過程條目）
        lines = [f"mklab-stock 資料抓取 Log | 模式={self.mode}",
                 f"開始: {self.stats['start']}  結束: {self.stats['end']}  耗時: {self.stats['duration_sec']}s",
                 f"成功: {self.stats['success']}  跳過: {self.stats.get('skipped', False)}",
                 f"抓取筆數: {self.stats['fetched']}  寫入筆數: {self.stats['written']}",
                 "-" * 50]
        lines += [f"[{l}] {m}" for l, m in self.entries]
        if self.stats.get("error"):
            lines.append(f"ERROR: {self.stats['error']}")
        with open(os.path.join(OUT, "fetch-log.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


# 主源：TWSE STOCK_DAY_ALL（每日收盤，官方上市清單，回傳 ~1369 筆含股票+ETF）
TWSE_DAILY = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
SCHEMA_VERSION = "1.0.0"
SAFE_MAX = 2000  # 安全閥：超過即視為異常，中止避免資料爆炸
MODE = sys.argv[1] if len(sys.argv) > 1 else "daily"
LOG = RunLogger(MODE)


def keep_record(code):
    """過濾機制：只留數字開頭、長度<=6 的上市/上櫃/ETF 代號。
    排除：期貨(TXF)/指數(TWII)等非數字開頭、異常長度。"""
    if not code:
        return False
    if not re.match(r'^\d', code):
        return False
    if len(code) > 6:
        return False
    return True


def load_codes():
    path = os.path.join(OUT, "industry-codes.json")
    if not os.path.exists(path):
        return {}, "其他等"
    d = json.load(open(path, encoding="utf-8"))
    return d.get("codes", {}), d.get("fallback", "其他等")


def ind_name(codes, fallback, raw):
    if not raw:
        return fallback
    nm = codes.get(str(raw).zfill(2)) or codes.get(str(raw))
    return nm if nm else fallback


def fetch_twse_json(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "mklab-stock/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# 本益比/淨值比/殖利率（TWSE OpenAPI 官方，免 key，回傳 list of dict）
TWSE_BWIBBU = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"


def fetch_bwibbu():
    """抓 TWSE 本益比/淨值比/殖利率，回傳 {sid: {pe, pb, div}}。失敗回傳空 dict（graceful）。"""
    try:
        raw = fetch_twse_json(TWSE_BWIBBU, timeout=60)
        if not isinstance(raw, list):
            return {}
        out = {}
        for r in raw:
            sid = str(r.get("Code", "")).strip()
            if not sid:
                continue
            def _f(k):
                v = r.get(k)
                if v in (None, "", "-"):
                    return None
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return None
            out[sid] = {"pe": _f("PEratio"), "pb": _f("PBratio"),
                        "div": _f("DividendYield")}
        return out
    except Exception as e:
        LOG.warn(f"BWIBBU 抓取失敗（PE/PB 留空，不中斷）：{e}")
        return {}



def parse_date(roc_str):
    roc = int(roc_str[:3])
    y = roc + 1911
    md = roc_str[3:]
    return f"{y}-{md[:2]}-{md[2:]}"


def load_existing_stocks():
    """讀現有 stocks.json（保留 ROE/ROA 等不直接抓的欄位）"""
    p = os.path.join(OUT, "stocks.json")
    if os.path.exists(p):
        try:
            return {s["sym"]: s for s in json.load(open(p, encoding="utf-8")).get("stocks", [])}
        except Exception:
            return {}
    return {}


def fetch_yfinance_roe(sym_list):
    """yfinance 抓 ROE/ROA（免 key）。每檔 sleep 3s 防 ban。回傳 {sym: {roe, roa}}"""
    try:
        import yfinance as yf
    except ImportError:
        print("[weekly] yfinance 未安裝，跳過 ROE/ROA")
        return {}
    out = {}
    for i, sym in enumerate(sym_list):
        try:
            t = yf.Ticker(f"{sym}.TW")
            bs = t.balance_sheet
            is_ = t.income_stmt
            if bs is None or bs.empty or is_ is None or is_.empty:
                continue
            col = bs.columns[0]
            equity = bs.loc["Stockholders Equity", col] if "Stockholders Equity" in bs.index else None
            ni = is_.loc["Net Income", col] if "Net Income" in is_.index else None
            ta = bs.loc["Total Assets", col] if "Total Assets" in bs.index else None
            rec = {}
            if equity and ni and equity != 0:
                rec["roe"] = round(ni / equity * 100, 2)
            if ta and ni and ta != 0:
                rec["roa"] = round(ni / ta * 100, 2)
            if rec:
                out[sym] = rec
        except Exception as e:
            print(f"  [weekly] {sym} 失敗: {e}")
        if (i + 1) % 50 == 0:
            print(f"  [weekly] 進度 {i+1}/{len(sym_list)}")
        time.sleep(3)  # 防 ban：每檔間隔 3 秒
    return out


def run_daily():
    codes, fallback = load_codes()
    stamp = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d")
    LOG.info(f"Actions 基準日 {stamp}")

    try:
        raw = fetch_twse_json(TWSE_DAILY)
    except Exception as e:
        LOG.error(f"TWSE 抓取失敗：{e}（可能休市/網路異常，不寫入）")
        LOG.finish(False, error=f"TWSE 抓取失敗：{e}")
        return

    if not raw:
        LOG.warn("TWSE 回傳空，可能休市，跳過")
        LOG.stats["skipped"] = True
        LOG.finish(False, error="TWSE 回傳空（休市）")
        return

    # 過濾機制：只留上市/ETF（排除期貨/指數等非數字開頭、異常長度）
    filtered = [r for r in raw if keep_record(r.get("Code", ""))]
    LOG.stats["fetched"] = len(filtered)
    if len(filtered) > SAFE_MAX:
        LOG.error(f"筆數 {len(filtered)} 超過安全閥 {SAFE_MAX}，疑似來源異常，中止寫入")
        LOG.finish(False, error=f"筆數超過安全閥 {SAFE_MAX}")
        return
    if len(filtered) < 500:
        LOG.warn(f"筆數 {len(filtered)} 異常偏低（可能休市/部分資料），仍寫入但標註")
    raw = filtered

    trade_date = parse_date(raw[0]["Date"])
    LOG.info(f"trade_date={trade_date}, 過濾後筆數={len(raw)}")

    # 抓本益比/淨值比/殖利率（TWSE BWIBBU，免 key）
    bwibbu = fetch_bwibbu()
    LOG.info(f"BWIBBU 取得 {len(bwibbu)} 檔 PE/PB/殖利率")

    # 保留既有 ROE/ROA/eps/market_cap（這些由 weekly 模式更新，daily 不覆寫）
    existing = load_existing_stocks()

    stocks = []
    for r in raw:
        sid = r.get("Code", "").strip()
        name = r.get("Name", "").strip()
        try:
            close = float(r.get("ClosingPrice")) if r.get("ClosingPrice") not in (None, "") else None
        except ValueError:
            close = None
        try:
            open_p = float(r.get("OpeningPrice")) if r.get("OpeningPrice") not in (None, "") else None
        except ValueError:
            open_p = None
        try:
            high = float(r.get("HighestPrice")) if r.get("HighestPrice") not in (None, "") else None
        except ValueError:
            high = None
        try:
            low = float(r.get("LowestPrice")) if r.get("LowestPrice") not in (None, "") else None
        except ValueError:
            low = None
        try:
            volume = float(r.get("TradeVolume")) if r.get("TradeVolume") not in (None, "") else None
        except ValueError:
            volume = None
        try:
            chg = float(r.get("Change")) if r.get("Change") not in (None, "") else None
        except ValueError:
            chg = None
        # 漲跌%：TWSE Change 是絕對值差，需昨收推算；這裡直接存 chg（元），前端可換算
        # 繼承既有 ROE/ROA/eps/market_cap/ind；PE/PB/div 來自 BWIBBU
        ex = existing.get(sid, {})
        bb = bwibbu.get(sid, {})
        # 當日無成交/停牌：TWSE 回傳 ClosingPrice=0 或空 → OHLC 全設 None（前端顯示 '-'），
        # 避免髒值 price<=0 進入資料；volume 保留供參考
        no_trade = (close is None or close <= 0)
        if no_trade:
            open_p = high = low = close = None
        stocks.append({
            "sym": sid,
            "name": name,
            "price": close,
            "open": open_p, "high": high, "low": low, "volume": volume,
            "pe": bb.get("pe"), "pb": bb.get("pb"), "div": bb.get("div"),
            "roe": ex.get("roe"), "eps": ex.get("eps"), "market_cap": ex.get("market_cap"),
            "ind": ex.get("ind"),
            "chg": chg,
            "rank": ex.get("rank"),
        })

    meta = {
        "as_of": trade_date,
        "source": "TWSE OpenAPI STOCK_DAY_ALL (免 key, 雲端)",
        "schema_version": SCHEMA_VERSION,
        "count": len(stocks),
        "note": "收盤/漲跌每日更新；ROE/ROA 由 weekly 模式補齊；ETF 含於上市清單",
    }
    with open(os.path.join(OUT, "stocks.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "stocks": stocks}, f, ensure_ascii=False)

    # 當日 history 切片（收盤價 + PE/PB/殖利率）
    hist = [{
        "stock_id": s["sym"], "stock_name": s["name"], "close": s["price"],
        "open": s["open"], "high": s["high"], "low": s["low"], "volume": s["volume"],
        "pe_ratio": s["pe"], "pb_ratio": s["pb"], "dividend_yield": s["div"],
        "industry": s["ind"],
    } for s in stocks]
    hpath = os.path.join(OUT, "history", f"{trade_date.replace('-', '')}.json")
    with open(hpath, "w", encoding="utf-8") as f:
        json.dump({"trade_date": trade_date, "schema_version": SCHEMA_VERSION,
                   "count": len(hist), "stocks": hist}, f, ensure_ascii=False)

    # industry.json：若已有則保留（不覆寫，避免每天清空）
    ind_path = os.path.join(OUT, "industry.json")
    if not os.path.exists(ind_path):
        ind_out = [{"nm": nm, "chg": 0.0, "cnt": 0, "top": 0.0} for nm in codes.values()]
        with open(ind_path, "w", encoding="utf-8") as f:
            json.dump({"meta": {**meta, "count": len(ind_out)},
                       "industry": ind_out}, f, ensure_ascii=False)

    with open(os.path.join(OUT, "schema-version.json"), "w", encoding="utf-8") as f:
        json.dump({"schema_version": SCHEMA_VERSION, "generated_at": stamp,
                   "generator": "scripts/fetch_data.py (GitHub Actions, daily)"}, f, ensure_ascii=False, indent=2)

    LOG.stats["written"] = len(stocks)
    LOG.stats["details"]["trade_date"] = trade_date
    LOG.stats["details"]["history_file"] = os.path.basename(hpath)
    LOG.info(f"完成 → data/ (stocks={len(stocks)}, history={trade_date})")
    LOG.finish(True)


def run_weekly():
    """每週六：yfinance 補 ROE/ROA，合併進 stocks.json（不動收盤價）"""
    LOG.info("開始補 ROE/ROA（yfinance 免 key，sleep 3s 防 ban）")
    p = os.path.join(OUT, "stocks.json")
    if not os.path.exists(p):
        LOG.warn("stocks.json 不存在，先跑 daily 再補")
        run_daily()
    data = json.load(open(p, encoding="utf-8"))
    stocks = data.get("stocks", [])
    syms = [s["sym"] for s in stocks]
    LOG.stats["fetched"] = len(syms)
    LOG.info(f"待補 {len(syms)} 檔")
    roe_map = fetch_yfinance_roe(syms)
    for s in stocks:
        if s["sym"] in roe_map:
            s["roe"] = roe_map[s["sym"]].get("roe")
            s["roa"] = roe_map[s["sym"]].get("roa")
    data["meta"]["roe_source"] = "yfinance (免 key, 每週六更新)"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    LOG.stats["written"] = len(roe_map)
    LOG.stats["details"]["roe_updated"] = len(roe_map)
    LOG.info(f"ROE/ROA 補齊 {len(roe_map)} 檔")
    LOG.finish(True)


if __name__ == "__main__":
    if MODE == "weekly":
        run_weekly()
    else:
        run_daily()
