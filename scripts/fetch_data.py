#!/usr/bin/env python3
"""
mklab-stock GitHub Actions 每日資料抓取腳本（Build-Time, 雲端免 key）。

設計原則（用戶最高原則：GitHub-Native / Fork First / 零外部依賴 / 零 secret）：
  - 主源 TWSE OpenAPI（官方、免 key、雲端可達）抓收盤+PE/PB/殖利率+漲跌
  - 次源 TPEX OpenAPI（官方、免 key）抓上櫃/興櫃
  - ROE/ROA/EPS/股本 由 TWSE 營益分析/資產負債表（免 key）補齊
  - 產業分類用 data/industry-codes.json（33 類官方對照）
  - 產出 schema 與 scripts/export_db.py（本機灌種）完全一致，確保歷史銜接
  - Graceful Degradation：單檔失敗不中斷，欄位給 null
  - 休市判斷：TWSE 回傳空/非最新交易日 → 標註跳過

四種模式：
  python scripts/fetch_data.py daily      # 每日：TWSE+TPEX 收盤+PE/PB/殖利率+營益分析（快，~2min）
  python scripts/fetch_data.py weekly     # 每週六：yfinance 補 ROE/ROA（備用、sleep 3s 防 ban，~70min）
  python scripts/fetch_data.py indices    # 每工作日：yfinance 抓全球指數+代表性 ETF 收盤/漲跌
  python scripts/fetch_data.py twii       # 每工作日：yfinance 抓 ^TWII K 線 (260 日窗口)

資料來源優先順序：TWSE → TPEX → Yahoo Finance (yfinance) → FinMind（Optional，不再依賴）
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


# ===== API 端點 =====
TWSE_DAILY       = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TWSE_BWIBBU      = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
TWSE_PROFITABILITY = "https://openapi.twse.com.tw/v1/opendata/t187ap06_L"  # 營益分析：ROE、ROA、EPS（可能已失效，備用用 yfinance）
TWSE_BALANCE     = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"     # 資產負債表：股本（可能已失效，備用用 yfinance）
TWSE_INCOME      = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"     # 綜合損益表：淨利（可能已失效，備用用 yfinance）

# TPEX：僅抓 ETF（上櫃 ETF、債券 ETF、槓桿/反向 ETF）
TPEX_DAILY       = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes?l=zh-tw"
TPEX_BWIBBU      = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_pe_ratio?l=zh-tw"  # 可能無 BWIBBU，暫用 PE ratio

# ===== 配置參數 =====
SAFE_MAX = 2000  # 上限：上市股票+ETF 總數不超過 2000 筆
SCHEMA_VERSION = "1.0.0"
MODE = sys.argv[1] if len(sys.argv) > 1 else "daily"
LOG = RunLogger(MODE)

# ===== 選股原則 =====
# 1. TWSE 上市股票 + ETF（排除期貨/指數/非數字開頭代碼）
# 2. TPEX 上櫃 ETF（ETF、債券 ETF、槓桿/反向 ETF、高息/配息型）
# 3. 合併後依市值由大到小排序，取前 SAFE_MAX 筆（上限 2000 筆）
# 4. ETF 以名稱關鍵字識別（ETF|基金|指數|正[0-9]|反[0-9]|槓桿|反向|期貨|配息|高息|優息|收益）
# 5. 停牌/無成交資料保留代碼但 OHLC 設為 null


# ===== 工具函式 =====
def keep_record(code):
    """過濾機制：只留數字開頭、長度<=6 的上市/上櫃/ETF 代號。
    排除：期貨(TXF)/指數(TWII)等非數字開頭、異常長度。
    允許 ETF 代號（數字開頭，可能含字母尾碼，如 00679B）。"""
    if not code:
        return False
    if not re.match(r'^\d', code):
        return False
    # 移除字母尾碼後檢查長度
    numeric_part = re.match(r'^(\d+)', code)
    if numeric_part and len(numeric_part.group(1)) > 6:
        return False
    return True


def load_symbol_map():
    path = os.path.join(OUT, "symbol-map.json")
    if not os.path.exists(path):
        LOG.warn("symbol-map.json 不存在，將無法進行代碼轉換")
        return {}
    d = json.load(open(path, encoding="utf-8"))
    return d.get("symbol_map", {})


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


def fetch_json(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "mklab-stock/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_json_with_fallback(urls, timeout=60):
    """依序嘗試多個 URL，成功即回傳；全部失敗回傳空 list。"""
    for url in urls:
        try:
            raw = fetch_json(url, timeout=timeout)
            if isinstance(raw, list) and raw:
                LOG.info(f"成功取得資料來源: {url}")
                return raw
        except Exception as e:
            LOG.warn(f"來源失敗 {url}: {e}")
    LOG.error(f"所有來源均失敗: {urls}")
    return []


def parse_date(roc_str):
    roc = int(roc_str[:3])
    y = roc + 1911
    md = roc_str[3:]
    return f"{y}-{md[:2]}-{md[2:]}"


def load_existing_stocks():
    """讀現有 stocks.json（保留 ROE/ROA/EPS/market_cap 等不直接抓的欄位）"""
    p = os.path.join(OUT, "stocks.json")
    if os.path.exists(p):
        try:
            return {s["sym"]: s for s in json.load(open(p, encoding="utf-8")).get("stocks", [])}
        except Exception:
            return {}
    return {}


# ===== TWSE BWIBBU (PE/PB/殖利率) =====
def fetch_bwibbu():
    """抓 TWSE 本益比/淨值比/殖利率，回傳 {sid: {pe, pb, div}}。失敗回傳空 dict（graceful）。"""
    try:
        raw = fetch_json(TWSE_BWIBBU, timeout=60)
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


# ===== TWSE 營益分析 (ROE/ROA/EPS) =====
def fetch_profitability():
    """抓 TWSE 營益分析 (t187ap06_L)，回傳 {sid: {roe, roa, eps}}。失敗回傳空 dict。"""
    try:
        raw = fetch_json(TWSE_PROFITABILITY, timeout=60)
        if not isinstance(raw, list):
            return {}
        out = {}
        for r in raw:
            sid = str(r.get("公司代號", "")).strip()
            if not sid or not keep_record(sid):
                continue
            def _f(k):
                v = r.get(k)
                if v in (None, "", "-", "--"):
                    return None
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return None
            out[sid] = {
                "roe": _f("股東權益報酬率(%)"),
                "roa": _f("資產報酬率(%)"),
                "eps": _f("每股盈餘(元)")
            }
        LOG.info(f"營益分析取得 {len(out)} 檔 ROE/ROA/EPS")
        return out
    except Exception as e:
        LOG.warn(f"營益分析抓取失敗（ROE/ROA/EPS 留空，不中斷）：{e}")
        return {}


# ===== TWSE 資產負債表 (股本) =====
def fetch_balance_sheet():
    """抓 TWSE 資產負債表 (t187ap05_L)，回傳 {sid: {capital_stock}}。失敗回傳空 dict。"""
    try:
        raw = fetch_json(TWSE_BALANCE, timeout=60)
        if not isinstance(raw, list):
            return {}
        out = {}
        for r in raw:
            sid = str(r.get("公司代號", "")).strip()
            if not sid or not keep_record(sid):
                continue
            def _f(k):
                v = r.get(k)
                if v in (None, "", "-", "--"):
                    return None
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return None
            capital = _f("普通股股本")
            if capital:
                out[sid] = {"capital_stock": capital}
        LOG.info(f"資產負債表取得 {len(out)} 檔股本")
        return out
    except Exception as e:
        LOG.warn(f"資產負債表抓取失敗（股本留空，不中斷）：{e}")
        return {}


# ===== TPEX BWIBBU (上櫃 PE/PB/殖利率) =====
def fetch_tpex_bwibbu():
    """抓 TPEX 本益比/淨值比/殖利率，回傳 {sid: {pe, pb, div}}。失敗回傳空 dict。
    注意：TPEX 新 API 可能只有 PE ratio，PB/Div 可能需另一端點。"""
    try:
        raw = fetch_json(TPEX_BWIBBU, timeout=60)
        if not isinstance(raw, list):
            return {}
        out = {}
        for r in raw:
            sid = str(r.get("SecuritiesCompanyCode", "")).strip()
            if not sid:
                continue
            def _f(k):
                v = r.get(k)
                if v in (None, "", "-", "--"):
                    return None
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return None
            out[sid] = {"pe": _f("PERatio"), "pb": _f("PBratio"),
                        "div": _f("DividendYield")}
        LOG.info(f"TPEX BWIBBU 取得 {len(out)} 檔 PE/PB/殖利率")
        return out
    except Exception as e:
        LOG.warn(f"TPEX BWIBBU 抓取失敗（PE/PB 留空，不中斷）：{e}")
        return {}


# ===== TPEX 每日收盤 =====
def fetch_tpex_daily():
    """抓 TPEX 每日收盤，回傳 list of dict（同 TWSE 格式）。失敗回傳空 list。"""
    try:
        raw = fetch_json(TPEX_DAILY, timeout=60)
        if not isinstance(raw, list):
            return []
        LOG.info(f"TPEX 每日收盤取得 {len(raw)} 筆原始資料")
        return raw
    except Exception as e:
        LOG.warn(f"TPEX 每日收盤抓取失敗：{e}")
        return []


# ===== yfinance ROE/ROA（備用、每週跑）=====
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


# ===== 主流程：每日抓取 =====
def run_daily():
    codes, fallback = load_codes()
    symbol_map = load_symbol_map()
    stamp = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d")
    LOG.info(f"Actions 基準日 {stamp}")

    # 1) TWSE 每日收盤（主源）
    try:
        twse_raw = fetch_json(TWSE_DAILY)
    except Exception as e:
        LOG.error(f"TWSE 抓取失敗：{e}（可能休市/網路異常，不寫入）")
        LOG.finish(False, error=f"TWSE 抓取失敗：{e}")
        return

    if not twse_raw:
        LOG.warn("TWSE 回傳空，可能休市，跳過")
        LOG.stats["skipped"] = True
        LOG.finish(False, error="TWSE 回傳空（休市）")
        return

    # 過濾機制：只留上市/ETF（排除期貨/指數等非數字開頭、異常長度）
    twse_filtered = [r for r in twse_raw if keep_record(r.get("Code", ""))]
    LOG.stats["fetched"] = len(twse_filtered)
    if len(twse_filtered) > SAFE_MAX:
        LOG.error(f"筆數 {len(twse_filtered)} 超過安全閥 {SAFE_MAX}，疑似來源異常，中止寫入")
        LOG.finish(False, error=f"筆數超過安全閥 {SAFE_MAX}")
        return
    if len(twse_filtered) < 500:
        LOG.warn(f"筆數 {len(twse_filtered)} 異常偏低（可能休市/部分資料），仍寫入但標註")
    twse_raw = twse_filtered

    # 3) PE/PB/殖利率：TWSE
    bwibbu_twse = fetch_bwibbu()

    # 4) 營益分析 (ROE/ROA/EPS)：TWSE 官方免 key
    profitability = fetch_profitability()

    # 5) 股本：TWSE 官方免 key
    balance_sheet = fetch_balance_sheet()

    # 6) 處理 TWSE 資料
    trade_date = parse_date(twse_raw[0]["Date"])
    LOG.info(f"trade_date={trade_date}, TWSE={len(twse_raw)}")

    # 載入 ETF 發行張數，用於補算 ETF market_cap
    etf_shares_path = os.path.join(OUT, "etf-shares.json")
    etf_shares = {}
    if os.path.exists(etf_shares_path):
        try:
            etf_shares = json.load(open(etf_shares_path, encoding="utf-8")).get("etf", {})
            LOG.info(f"ETF 發行張數載入 {len(etf_shares)} 檔")
        except Exception as e:
            LOG.warn(f"etf-shares.json 載入失敗：{e}")
    else:
        LOG.warn("etf-shares.json 不存在，ETF market_cap 將留空")

    # 保留既有 ROE/ROA/EPS/market_cap/ind（這些由 weekly/官方 API 更新，daily 不覆寫）
    existing = load_existing_stocks()

    stocks = []
    sources = {"TWSE": 0}

    # --- 處理 TWSE ---
    for r in twse_raw:
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

        # 漲跌%：TWSE Change 是漲跌「元」，需由 收盤-Change 推算昨收，再算漲跌%
        chg_pct = None
        if chg is not None and close is not None and close > 0:
            prev_close = close - chg
            if prev_close and prev_close > 0:
                chg_pct = round(chg / prev_close * 100, 2)
        chg = chg_pct  # 向後相容：保留 chg 欄位存漲跌%（統一為 %），避免前端逐頁改欄位名

        # 繼承既有 ROE/ROA/EPS/market_cap/ind
        ex = existing.get(sid, {})
        bb_twse = bwibbu_twse.get(sid, {})
        prof = profitability.get(sid, {})
        bal = balance_sheet.get(sid, {})

        # 當日無成交/停牌：TWSE 回傳 ClosingPrice=0 或空 → OHLC 全設 None
        no_trade = (close is None or close <= 0)
        if no_trade:
            open_p = high = low = close = None

        # ETF 特殊處理：TWSE API 對 ETF（代號含字母尾碼）只給 ClosingPrice、不給 Open/High/Low
        elif open_p is None or high is None or low is None:
            if close is not None:
                if open_p is None: open_p = close
                if high is None: high = close
                if low is None: low = close

        # ETF market_cap：若無既有值且有發行張數資料，用 price * shares_stock 估算
        mc = ex.get("market_cap")
        if mc is None and sid in etf_shares and close is not None:
            shares = etf_shares[sid].get("shares_stock")
            if shares:
                mc = round(close * shares)

        # 營益分析：優先 TWSE 官方，其次既有資料
        roe = prof.get("roe") if prof.get("roe") is not None else ex.get("roe")
        roa = prof.get("roa") if prof.get("roa") is not None else ex.get("roa")
        eps = prof.get("eps") if prof.get("eps") is not None else ex.get("eps")
        capital_stock = bal.get("capital_stock") if bal.get("capital_stock") is not None else ex.get("capital_stock")

        # ETF 標記
        is_etf = bool(re.search(r"ETF|基金|指數|正[0-9]|反[0-9]|槓桿|反向|期貨|配息|高息|優息|收益", name or ""))

        # 資料來源標記
        source = "TWSE"
        quality = "official"
        last_updated = trade_date

        stocks.append({
            "sym": sid,
            "name": name,
            "price": close,
            "open": open_p, "high": high, "low": low, "volume": volume,
            "pe": bb_twse.get("pe"), "pb": bb_twse.get("pb"), "div": bb_twse.get("div"),
            "roe": roe, "roa": roa, "eps": eps, "capital_stock": capital_stock,
            "market_cap": mc, "ind": ex.get("ind"),
            "is_etf": is_etf,
            "chg": chg,
            "rank": ex.get("rank"),
            "source": source,
            "quality": quality,
            "last_updated": last_updated,
        })
        sources["TWSE"] += 1

    # --- 處理 TPEX ETF ---
    # 抓取 TPEX 每日收盤，過濾出 ETF（名稱含關鍵字或代碼格式）
    tpex_raw = fetch_tpex_daily()
    tpex_etf_candidates = []
    for r in tpex_raw:
        sid = r.get("SecuritiesCompanyCode", "").strip()
        name = r.get("CompanyName", "").strip()
        # 過濾：只保留 ETF 類（名稱關鍵字或代碼格式）
        is_etf = bool(re.search(r"ETF|基金|指數|正[0-9]|反[0-9]|槓桿|反向|期貨|配息|高息|優息|收益", name or ""))
        # 代碼格式：5-6 位數字+字母尾碼（如 00679B）
        is_etf_code = len(sid) >= 5 and any(c.isalpha() for c in sid)
        if keep_record(sid) and (is_etf or is_etf_code):
            tpex_etf_candidates.append(r)
    LOG.info(f"TPEX ETF 候選筆數: {len(tpex_etf_candidates)}")

    # TPEX BWIBBU（PE/PB/殖利率）
    bwibbu_tpex = fetch_tpex_bwibbu()

    # 合併 TWSE + TPEX ETF，依市值排序取前 SAFE_MAX
    # 先用既有 market_cap 或估算（close * volume/1000）排序
    def est_mc(s):
        mc = s.get("market_cap")
        if mc and mc > 0:
            return mc
        # 估算：close * volume/1000（粗略）
        if s.get("price") and s.get("volume"):
            return s["price"] * s["volume"] / 1000
        return 0

    # 為 TWSE 股票補上估算市值
    for s in stocks:
        s["_est_mc"] = est_mc(s)

    # 處理 TPEX ETF，建立相同結構
    tpex_stocks = []
    for r in tpex_etf_candidates:
        sid = r.get("SecuritiesCompanyCode", "").strip()
        name = r.get("CompanyName", "").strip()
        try:
            close = float(r.get("Close")) if r.get("Close") not in (None, "") else None
        except ValueError:
            close = None
        try:
            open_p = float(r.get("Open")) if r.get("Open") not in (None, "") else None
        except ValueError:
            open_p = None
        try:
            high = float(r.get("High")) if r.get("High") not in (None, "") else None
        except ValueError:
            high = None
        try:
            low = float(r.get("Low")) if r.get("Low") not in (None, "") else None
        except ValueError:
            low = None
        try:
            volume = float(r.get("TradingShares")) if r.get("TradingShares") not in (None, "") else None
        except ValueError:
            volume = None
        try:
            chg = float(r.get("Change")) if r.get("Change") not in (None, "") else None
        except ValueError:
            chg = None

        chg_pct = None
        if chg is not None and close is not None and close > 0:
            prev_close = close - chg
            if prev_close and prev_close > 0:
                chg_pct = round(chg / prev_close * 100, 2)
        chg = chg_pct

        no_trade = (close is None or close <= 0)
        if no_trade:
            open_p = high = low = close = None
        elif open_p is None or high is None or low is None:
            if close is not None:
                if open_p is None: open_p = close
                if high is None: high = close
                if low is None: low = close

        ex = existing.get(sid, {})
        bb_tpex = bwibbu_tpex.get(sid, {})
        # TPEX 沒有營益分析/資產負債表 API，沿用既有資料
        roe = ex.get("roe")
        roa = ex.get("roa")
        eps = ex.get("eps")
        capital_stock = ex.get("capital_stock")
        mc = ex.get("market_cap")
        if mc is None and sid in etf_shares and close is not None:
            shares = etf_shares[sid].get("shares_stock")
            if shares:
                mc = round(close * shares)

        is_etf = True  # TPEX 這裡都是 ETF

        source = "TPEX"
        quality = "official"
        last_updated = trade_date

        tpex_stocks.append({
            "sym": sid,
            "name": name,
            "price": close,
            "open": open_p, "high": high, "low": low, "volume": volume,
            "pe": bb_tpex.get("pe"), "pb": bb_tpex.get("pb"), "div": bb_tpex.get("div"),
            "roe": roe, "roa": roa, "eps": eps, "capital_stock": capital_stock,
            "market_cap": mc, "ind": ex.get("ind"),
            "is_etf": is_etf,
            "chg": chg,
            "rank": ex.get("rank"),
            "source": source,
            "quality": quality,
            "last_updated": last_updated,
            "_est_mc": est_mc({"price": close, "volume": volume, "market_cap": mc}),
        })
        sources["TPEX"] = sources.get("TPEX", 0) + 1

    # 合併並依市值排序，取前 SAFE_MAX
    all_stocks = stocks + tpex_stocks
    all_stocks.sort(key=lambda x: x.get("_est_mc", 0), reverse=True)
    all_stocks = all_stocks[:SAFE_MAX]

    # 清理暫存欄位
    for s in all_stocks:
        s.pop("_est_mc", None)

    stocks = all_stocks
    meta = {
        "as_of": trade_date,
        "source": f"TWSE OpenAPI STOCK_DAY_ALL (免 key, 雲端)",
        "schema_version": SCHEMA_VERSION,
        "count": len(stocks),
        "sources": sources,
        "note": "收盤/漲跌每日更新；ROE/ROA/EPS/股本 由 TWSE 營益分析/資產負債表（官方免 key）補齊；ETF 含於上市清單；上限 2000 檔",
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
    LOG.stats["details"]["sources"] = sources
    LOG.info(f"完成 → data/ (stocks={len(stocks)}, history={trade_date}, TWSE={sources['TWSE']})")
    LOG.finish(True)


# ===== 週報模式：yfinance 補 ROE/ROA（備用）=====
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
            s["quality"] = "yfinance_fallback"
            s["source"] = "Yahoo Finance"
    data["meta"]["roe_source"] = "yfinance (免 key, 每週六更新, 備用)"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    LOG.stats["written"] = len(roe_map)
    LOG.stats["details"]["roe_updated"] = len(roe_map)
    LOG.info(f"ROE/ROA 補齊 {len(roe_map)} 檔（備用來源）")
    LOG.finish(True)


# ===== 指數模式 =====
def run_indices():
    """每日：yfinance 抓全球主要指數 + 各國代表 ETF + 巨集經濟指標，寫入 data/indices.json。"""
    try:
        import yfinance as yf
    except ImportError:
        LOG.error("yfinance 未安裝，無法抓指數/ETF/巨集指標（indices 模式跳過）")
        LOG.finish(False, error="yfinance 未安裝")
        return

    cfg_path = os.path.join(OUT, "indices-config.json")
    if not os.path.exists(cfg_path):
        LOG.error(f"缺少 {cfg_path}，無法執行 indices 模式")
        LOG.finish(False, error="缺少 indices-config.json")
        return

    cfg = json.load(open(cfg_path, encoding="utf-8"))
    stamp = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d")
    
    # 支援新結構 (markets) 與舊結構 (indices/etfs/macro 根層級)
    if "markets" in cfg:
        LOG.info(f"indices 模式基準日 {stamp}，市場數={len(cfg['markets'])} (新結構 markets)")
        # 扁平化所有市場的 indices/etfs
        indices_cfg = []
        etfs_cfg = []
        for m in cfg["markets"]:
            indices_cfg.extend(m.get("indices", []))
            etfs_cfg.extend(m.get("etfs", []))
        macro_cfg = cfg.get("macro", [])
    else:
        LOG.info(f"indices 模式基準日 {stamp}，指數數={len(cfg.get('indices', []))}，ETF數={len(cfg.get('etfs', []))} (舊結構)")
        indices_cfg = cfg.get("indices", [])
        etfs_cfg = cfg.get("etfs", [])
        macro_cfg = cfg.get("macro", [])

    def fetch_one(item):
        syms_to_try = [item.get("yf")]
        if item.get("fallback_yf"):
            syms_to_try.append(item["fallback_yf"])
        last_err = None
        for sym in syms_to_try:
            if not sym:
                continue
            try:
                t = yf.Ticker(sym)
                h = t.history(period="1mo", interval="1d")
                if h is None or h.empty:
                    last_err = f"{sym} empty"
                    continue
                valid = h.dropna(subset=["Close"])
                if valid.empty:
                    last_err = f"{sym} all NaN"
                    continue
                last = valid.iloc[-1]
                prev = valid.iloc[-2] if len(valid) > 1 else last
                close = float(last["Close"])
                prev_close = float(prev["Close"])
                chg_pct = round((close - prev_close) / prev_close * 100, 2) if prev_close else None
                return {
                    "close": round(close, 2),
                    "prev_close": round(prev_close, 2),
                    "chg_pct": chg_pct,
                    "as_of": str(last.name.date()),
                }
            except Exception as e:
                last_err = f"{sym}: {e}"
                continue
        if last_err:
            LOG.warn(f"{item.get('yf')} ({item.get('name')}) 未取得：{last_err}")
        return None

    def build(group_key):
        out = []
        for item in cfg.get(group_key, []):
            sym = item.get("yf")
            if not sym:
                continue
            rec = fetch_one(item)
            row = {
                "market": item.get("market"),
                "name": item.get("name"),
                "yf": sym,
            }
            if "desc" in item:
                row["desc"] = item["desc"]
            if "tracks" in item:
                row["tracks"] = item["tracks"]
            if "since" in item:
                row["since"] = item["since"]
            if "rep" in item:
                row["rep"] = item["rep"]
            if rec:
                row.update(rec)
                LOG.info(f"  {sym} {item.get('name')}: {rec['close']} ({rec['chg_pct']}%, as_of={rec['as_of']})")
            else:
                row["close"] = None
                row["prev_close"] = None
                row["chg_pct"] = None
                row["as_of"] = None
                LOG.warn(f"  {sym} {item.get('name')}: 未取得（留 null）")
            out.append(row)
        return out

    indices = build("indices")
    etfs = build("etfs")
    
    # 抓取巨集經濟指標
    macro_items = cfg.get("macro", [])
    macro = {}
    for item in macro_items:
        item_id = item.get("id")
        if not item_id:
            continue
        rec = fetch_one(item)
        if rec:
            macro[item_id] = {
                "label": item.get("label"),
                "unit": item.get("unit"),
                "value": rec.get("close"),
                "prev_value": rec.get("prev_close"),
                "chg_pct": rec.get("chg_pct"),
                "as_of": rec.get("as_of"),
                "yf": item.get("yf"),
                "desc": item.get("desc")
            }
            LOG.info(f"  {item_id} ({item.get('label')}): {rec['close']} ({rec['chg_pct']}%, as_of={rec['as_of']})")
        else:
            macro[item_id] = {
                "label": item.get("label"),
                "unit": item.get("unit"),
                "value": None,
                "prev_value": None,
                "chg_pct": None,
                "as_of": None,
                "yf": item.get("yf"),
                "desc": item.get("desc")
            }
            LOG.warn(f"  {item_id} ({item.get('label')}): 未取得（留 null）")
    LOG.stats["fetched"] = len(indices) + len(etfs) + len(macro)
    LOG.stats["written"] = sum(1 for r in indices + etfs if r.get("close") is not None) + sum(1 for v in macro.values() if v.get("value") is not None)

    meta = {
        "as_of": stamp,
        "source": "yfinance (免 key, 雲端 pip install)",
        "schema_version": SCHEMA_VERSION,
        "index_count": len(indices),
        "etf_count": len(etfs),
        "macro_count": len(macro),
        "note": "收盤/漲跌% 每日更新；as_of 為該標的最後交易日（跨時區可能非同日）。巨集指標含 VIX、匯率、大宗商品、加密貨幣。",
    }
    with open(os.path.join(OUT, "indices.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "indices": indices, "etfs": etfs, "macro": macro}, f, ensure_ascii=False, indent=2)

    LOG.stats["details"]["index_count"] = len(indices)
    LOG.stats["details"]["etf_count"] = len(etfs)
    LOG.info(f"完成 → data/indices.json (indices={len(indices)}, etfs={len(etfs)})")
    LOG.finish(True)


# ===== TWII K 線 =====
def fetch_twii_kline(days=260, out_path=None):
    """抓取台灣加權股價指數 (^TWII, yfinance 免 key) 最近 days 個交易日的 OHLC，
    寫入 data/twii_kdata.js (const TWII_KDATA=[...]，前端 index.html 直接吃，零改動)。"""
    try:
        import yfinance as yf
    except ImportError:
        LOG.warn("yfinance 未安裝，跳過 TWII K 線（twii 模式需先 pip install yfinance）")
        return False
    try:
        t = yf.Ticker("^TWII")
        h = t.history(period=f"{days + 20}d", interval="1d")
        if h is None or h.empty:
            LOG.warn("^TWII 回傳空，跳過 TWII K 線")
            return False
        valid = h.dropna(subset=["Open", "High", "Low", "Close"])
        if valid.empty:
            LOG.warn("^TWII 全為 NaN，跳過 TWII K 線")
            return False
        rows = []
        for ts, r in valid.iterrows():
            rows.append({
                "time": ts.date().isoformat(),
                "open": round(float(r["Open"]), 2),
                "high": round(float(r["High"]), 2),
                "low": round(float(r["Low"]), 2),
                "close": round(float(r["Close"]), 2),
            })
        rows = rows[-days:]
        if out_path is None:
            out_path = os.path.join(OUT, "twii_kdata.js")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("const TWII_KDATA=" + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";\n")
            f.write("if(typeof window!=='undefined')window.TWII_KDATA=TWII_KDATA;\n")
        LOG.stats["written"] = len(rows)
        LOG.stats["details"]["twii_days"] = len(rows)
        LOG.stats["details"]["twii_range"] = f"{rows[0]['time']}~{rows[-1]['time']}"
        LOG.info(f"TWII K 線寫入 {len(rows)} 天 → {os.path.basename(out_path)} ({rows[0]['time']}~{rows[-1]['time']})")
        return True
    except Exception as e:
        LOG.warn(f"TWII K 線抓取失敗：{e}")
        return False


def run_twii():
    """每日：yfinance 抓台灣加權指數 K 線 (260 交易日窗口) → data/twii_kdata.js"""
    LOG.info("開始抓取 TWII 加權指數 K 線 (yfinance ^TWII, 260 日窗口)")
    ok = fetch_twii_kline(days=260)
    if ok:
        LOG.finish(True)
    else:
        LOG.finish(False, error="TWII K 線未取得")


if __name__ == "__main__":
    if MODE == "weekly":
        run_weekly()
    elif MODE == "indices":
        run_indices()
    elif MODE == "twii":
        run_twii()
    else:
        run_daily()