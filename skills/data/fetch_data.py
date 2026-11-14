#!/usr/bin/env python3
"""
mklab-stock GitHub Actions 每日資料抓取腳本（Build-Time, 雲端免 key）。

設計原則（用戶最高原則：GitHub-Native / Fork First / 零外部依賴 / 零 secret）：
  - 主源 TWSE OpenAPI（官方、免 key、雲端可達）抓收盤+PE/PB/殖利率+漲跌
  - 次源 TPEX OpenAPI（官方、免 key）抓上櫃/興櫃
  - ROE/ROA/EPS 由 import_official_fundamentals.py 以官方財報（MOPS，累計年化）寫入；股本取自資產負債表
  - 產業分類用 data/industry-codes.json（33 類官方對照）
  - 產出 schema 與 data/schema.md 定義一致，確保歷史銜接
  - Graceful Degradation：單檔失敗不中斷，欄位給 null
  - 休市判斷：TWSE 回傳空/非最新交易日 → 標註跳過

四種模式：
  python skills/data/fetch_data.py daily      # 每日：TWSE+TPEX 收盤+PE/PB/殖利率（快，~2min；財報欄位由 import_official_fundamentals.py 另行更新）
  python skills/data/fetch_data.py weekly     # 每週六：yfinance 補 ROE/ROA（備用、sleep 3s 防 ban，~70min）
  python skills/data/fetch_data.py indices    # 每工作日：yfinance 抓全球指數+代表性 ETF 收盤/漲跌
  python skills/data/fetch_data.py twii       # 每工作日：yfinance 抓 ^TWII K 線 (260 日窗口)

資料來源優先順序：TWSE → TPEX → Yahoo Finance (yfinance) → FinMind（Optional，不再依賴）
"""

import json
import os
import sys
import re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data_rules  # 2026-11-13 共用資料品質規則
import math
import time
import datetime as dt
import urllib.request
import urllib.error
# 站內資料範圍的唯一來源（同目錄）。自帶 os/sys 並動態加路徑，這樣不論是
# `python3 skills/data/xxx.py` 直跑、由其他程式 import、或從別的 cwd 執行，都找得到。
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import scope_rules  # noqa: E402

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
os.makedirs(OUT, exist_ok=True)
os.makedirs(os.path.join(OUT, "history"), exist_ok=True)

# ===== 結構化 Log 系統（供 GitHub Actions 留存 + 使用者確認抓取成功）=====
class RunLogger:
    """收集本輪抓取的結構化記錄，最後輸出總結並寫入 data/fetch-log.json。"""
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
        # 單一機器可讀檔案：摘要統計 + 完整過程 log 合併成一份，不再拆成 json/txt 兩份重複內容
        self.stats["log_lines"] = [f"[{l}] {m}" for l, m in self.entries]
        with open(os.path.join(OUT, "fetch-log.json"), "w", encoding="utf-8") as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)


# ===== API 端點 =====
TWSE_DAILY       = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TWSE_BWIBBU      = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
TWSE_BALANCE     = data_rules.TWSE_BALANCE_ENDPOINTS  # 2026-11-13：舊值 t187ap05_L 是「月營收」非資產負債表，股本永遠為 0

# TPEX：只保留上櫃 ETF（上櫃一般股票不納入，為本站原始設計；其餘上櫃證券如權證亦不收）
TPEX_DAILY       = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes?l=zh-tw"
TPEX_BWIBBU      = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_pe_ratio?l=zh-tw"  # 可能無 BWIBBU，暫用 PE ratio

# ===== 配置參數 =====
SAFE_MAX = 3000  # 安全上限：上市（一般股票+ETF+其他）+ 上櫃 ETF 合計，實際約 1,500 筆
# 上櫃只保留這些分類：官方 ETF 清單內的 ETF；00 開頭但清單尚未收錄者（新掛牌 ETF，標記 unverified 供人工確認）
TPEX_KEEP_TYPES = ("etf", "unverified")
TPEX_MIN_RAW = 300  # 上櫃原始筆數低於此值視為來源異常（TPEx 主板約千檔）
SCHEMA_VERSION = "1.0.0"
MODE = sys.argv[1] if len(sys.argv) > 1 else "daily"
LOG = RunLogger(MODE)

# ===== 選股原則 =====
# 1. TWSE 上市股票 + ETF（排除期貨/指數/非數字開頭代碼）
# 2. TPEX 只收上櫃 ETF（依官方 ETF 清單判定；上櫃一般股票、權證等一律不收）
# 3. 合併後依市值由大到小排序，取前 SAFE_MAX 筆（上限 SAFE_MAX=3000 筆）
# 4. ETF 以名稱關鍵字識別（ETF|基金|指數|正[0-9]|反[0-9]|槓桿|反向|期貨|配息|高息|優息|收益）
# 5. 停牌/無成交資料保留代碼但 OHLC 設為 null


# ===== 工具函式 =====
# 官方財報／股利欄位（由 import_official_fundamentals.py 寫入），每日重建時必須保留
# 2026-11-10 瘦身：拿掉 9 個「前端與測試都沒讀」的欄位（stocks.json 原始大小約 -20%）。
# 本批移除：company_short、ind_src、fund_period、fund_asof、div_latest_year、
#           last_updated（與 price_asof 完全重複）、high52w、low52w、operating_margin。
# 出處資訊沒有消失：official-fundamentals.json 的 meta 仍有 files／financial_period／
# financial_asof_roc_date／method，產業來源在 data/raw/official/ 的原始檔與 industry-codes.json。
# operating_margin 仍完整保留在 official-fundamentals.json（只是不再複製進 stocks.json）。
OFFICIAL_KEYS = ["listing_date", "roe_off", "roa_off", "eps_off", "fund_src",
                 "div_cash_latest", "div_streak_years", "div_years_available"]

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


def load_etf_reference():
    """官方 ETF 清單（etf-meta.json + etf-supplement.json）：ETF 判定的唯一依據，不用名稱關鍵字。"""
    ref = set()
    for fn in ("etf-meta.json", "etf-supplement.json"):
        fp = os.path.join(OUT, fn)
        if os.path.exists(fp):
            try:
                ref |= {e["sym"] for e in json.load(open(fp, encoding="utf-8")).get("etfs", [])}
            except (OSError, json.JSONDecodeError, KeyError):
                LOG.warn(f"{fn} 讀取失敗，ETF 清單可能不完整")
    return ref


def classify_security(sid, etf_ref):
    """證券分類，規則與 compute_indicators.py 一致：
    官方 ETF 清單 → etf；00 開頭但不在清單 → unverified；
    4 碼純數字且非 91xx → stock；其餘（特別股、DR、受益證券、ETN 等）→ other；
    other 在 run_daily 會整批排除，不寫入 stocks.json。

    2026-11-10 修（根因）：DR 代號 9103／9105／9110／9136 是「4 碼純數字」，
    舊版先命中 len(sid)==4 and sid.isdigit() → "stock" 就直接回傳，永遠到不了 other 分支
    → 註解寫的「DR → other」從未生效，4 檔 TDR 長期被當成一般股票收進 stocks.json
    （總檔數虛胖、industry 多一類「存託憑證」、digest 還把它列進 top_gainers）。
    TWSE 產業別代碼 91 = 存託憑證，故 4 碼 91 開頭一律視為 other。
    ⚠️ 改這裡務必同步 compute_indicators.py 的同一段分類（tests 有一致性檢查）。"""
    sid = str(sid or "")
    if sid in etf_ref:
        return "etf"
    if sid.startswith("00"):
        return "unverified"
    if scope_rules.in_scope(sid):
        return "stock"
    return "other"


def recompute_meta(doc):
    """依實際陣列重算 meta.count / meta.sources / meta.price_asof_counts（任何寫入 stocks.json 的地方都要呼叫）。"""
    stocks = doc.get("stocks", [])
    meta = doc.setdefault("meta", {})
    src, pa = {}, {}
    for s in stocks:
        src[s.get("source")] = src.get(s.get("source"), 0) + 1
        pa[s.get("price_asof")] = pa.get(s.get("price_asof"), 0) + 1
    meta["count"] = len(stocks)
    meta["sources"] = src
    meta["price_asof_counts"] = pa
    return doc


def load_codes():
    path = os.path.join(OUT, "industry-codes.json")
    if not os.path.exists(path):
        return {}, "其他等"
    d = json.load(open(path, encoding="utf-8"))
    return d.get("codes", {}), d.get("fallback", "其他等")


def fetch_json(url, timeout=60, attempts=5):
    """抓 JSON，附重試與完整性檢查。

    注意：上櫃全量收盤檔約 5MB，經常在傳輸中被截斷（IncompleteRead）。
    - 不採用截斷後的 partial bytes（即使剛好是合法 JSON 也可能少了後半資料）。
    - 以 Content-Length 與實際位元組數比對，確認回應完整才解析。
    - 要求 identity 編碼，避免伺服器回傳壓縮內容時長度比對失真。
    - 全部重試失敗才拋出例外，由呼叫端決定是否沿用前次有效資料。
    """
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mklab-stock/1.0",
                                                       "Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                expected = r.headers.get("Content-Length")
            if expected is not None and int(expected) != len(raw):
                raise IOError(f"回應長度不符（Content-Length={expected}, 實際={len(raw)}）")
            return json.loads(raw.decode("utf-8"))
        except Exception as e:          # IncompleteRead / URLError / timeout / JSON 截斷 / 長度不符
            last = e
            LOG.warn(f"下載失敗（第 {i+1}/{attempts} 次）{url}: {e}")
            if i + 1 < attempts:
                time.sleep(min(30, 5 * (i + 1)))  # 退避：5s、10s、15s、20s
    raise last


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
    """抓 TWSE 本益比/淨值比/殖利率，回傳 {sid: {pe, pb, div}}。失敗回傳 None（graceful）。"""
    try:
        raw = fetch_json(TWSE_BWIBBU, timeout=60)
        if not isinstance(raw, list):
            return None
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
        LOG.warn(f"BWIBBU 抓取失敗（沿用前次 PE/PB/殖利率，不中斷）：{e}")
        return None


# ===== TWSE 資產負債表 (股本) =====
def fetch_balance_sheet():
    """抓 TWSE 資產負債表（t187ap07_L_* 各業別），回傳 {sid: {capital_stock(元)}}。
    2026-11-13 修正：舊端點 t187ap05_L 為月營收表，沒有股本欄位，導致股本/市值全部為 0。
    股本欄位單位為仟元，統一換算為新台幣元（data_rules.balance_capital_to_twd）。
    任一端點失敗只略過該端點；全部失敗回傳空 dict（不中斷，但 qa_gate 會以 CAPITAL_ZERO 阻擋發布）。"""
    out = {}
    fails = 0
    for url in TWSE_BALANCE:
        try:
            raw = fetch_json(url, timeout=60)
            if not isinstance(raw, list):
                fails += 1
                continue
            for r in raw:
                sid = str(r.get("公司代號", "")).strip()
                if not sid or not keep_record(sid):
                    continue
                cap = data_rules.balance_capital_to_twd(_to_num(r.get(data_rules.BALANCE_CAPITAL_KEY)))
                if cap:
                    out[sid] = {"capital_stock": cap}
        except Exception as e:
            fails += 1
            LOG.warn(f"資產負債表端點失敗（略過）：{url.rsplit('/', 1)[-1]} {e}")
    LOG.info(f"資產負債表取得 {len(out)} 檔股本（失敗端點 {fails}/{len(TWSE_BALANCE)}）")
    # 單位保險絲：換算後股數不合理 → 整批丟棄（寧缺勿錯），qa_gate 會以 CAPITAL_ZERO 擋下
    if out and not data_rules.capital_unit_plausible([v["capital_stock"] for v in out.values()]):
        LOG.error("資產負債表股本換算後股數不合理（單位疑似錯誤），整批不採用")
        return {}
    return out


# ===== TWSE 上市公司基本資料 (股本，主要來源) =====
def fetch_company_capital():
    """抓上市公司基本資料 t187ap03_L 的「實收資本額」→ {sid: {capital_stock(元)}}。

    2026-11-13 修正：股本的主要來源。t187ap07_L_* 資產負債表只收「該期別已申報」者
    （實測 752/1,099；台積電 2330、富邦金 2881 等都不在內），覆蓋率不足；本端點涵蓋
    全部上市公司，且「實收資本額」單位已是新台幣元，沒有仟元換算的單位風險。
    實測 2330 = 259,323,700,670 元（2,593 億元）。

    同一份資料另有「已發行普通股數」，是市值的正確輸入（見 data_rules.market_cap_from_shares）：
    台股面額有 0.5／1／2.5／5 元與無面額，用 股本÷10 推股數會算錯 32 檔（最大差 20 倍）。"""
    out = {}
    try:
        raw = fetch_json(data_rules.TWSE_COMPANY_INFO_ENDPOINT, timeout=60)
        if isinstance(raw, list):
            for r in raw:
                sid = str(r.get("公司代號", "")).strip()
                if not sid or not keep_record(sid):
                    continue
                cap = data_rules.company_capital_to_twd(_to_num(r.get(data_rules.COMPANY_CAPITAL_KEY)))
                shares = _to_num(r.get(data_rules.COMPANY_SHARES_KEY))
                if shares is not None and shares <= 0:
                    shares = None
                if cap or shares:
                    out[sid] = {"capital_stock": cap, "shares": shares}
        LOG.info(f"公司基本資料取得 {len(out)} 檔（股本＋已發行股數，單位：元／股）")
    except Exception as e:
        LOG.warn(f"公司基本資料端點失敗（略過）：{e}")
    if out and not data_rules.capital_unit_plausible([v["capital_stock"] for v in out.values()]):
        LOG.error("公司基本資料股本換算後股數不合理（單位疑似錯誤），整批不採用")
        return {}
    return out


def _to_num(v):
    if v in (None, "", "-", "--"):
        return None
    try:
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return None


# ===== TPEX BWIBBU (上櫃 PE/PB/殖利率) =====
def fetch_tpex_bwibbu():
    """抓 TPEX 本益比/淨值比/殖利率，回傳 {sid: {pe, pb, div}}。失敗回傳 None（與「來源正常但該股無資料」區分）。
    注意：TPEX 新 API 可能只有 PE ratio，PB/Div 可能需另一端點。"""
    try:
        raw = fetch_json(TPEX_BWIBBU, timeout=60)
        if not isinstance(raw, list):
            return None
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
        LOG.warn(f"TPEX BWIBBU 抓取失敗（沿用前次 PE/PB/殖利率，不中斷）：{e}")
        return None


# ===== TPEX 每日收盤 =====
def fetch_tpex_daily():
    """抓 TPEX 每日收盤，回傳 list of dict（同 TWSE 格式）。失敗回傳空 list。"""
    try:
        raw = fetch_json(TPEX_DAILY, timeout=120, attempts=5)   # 全量約 5MB，傳輸中常被截斷，多給幾次重試
        if not isinstance(raw, list):
            return []
        LOG.info(f"TPEX 每日收盤取得 {len(raw)} 筆原始資料")
        return raw
    except Exception as e:
        LOG.warn(f"TPEX 每日收盤抓取失敗：{e}")
        return []


# ===== yfinance ROE/ROA（備用、每週跑）=====
def _sanitize_nan(obj):
    """遞迴把 NaN/Infinity 換成 None，避免 json.dump 寫出不合法的 JSON token（如 NaN、Infinity）。
    Python 的 json 模組預設會把 float('nan') 原樣寫成沒加引號的 NaN，是合法的 Python 但不是合法的 JSON，
    瀏覽器端 JSON.parse() 會直接整份失敗。這是最後一道防線：不管前面哪個計算式漏接了 NaN，
    寫檔前都會在這裡被攔下來，避免單一壞值拖垮整份資料檔。"""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_nan(v) for v in obj]
    return obj


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
            if equity and ni and equity != 0 and not (math.isnan(equity) or math.isnan(ni)):
                v = round(ni / equity * 100, 2)
                if not math.isnan(v) and not math.isinf(v):
                    rec["roe"] = v
            if ta and ni and ta != 0 and not (math.isnan(ta) or math.isnan(ni)):
                v = round(ni / ta * 100, 2)
                if not math.isnan(v) and not math.isinf(v):
                    rec["roa"] = v
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


    # 5) 股本：TWSE 官方免 key（公司基本資料 t187ap03_L 為主、資產負債表 t187ap07_L_* 為備援）
    company_capital = fetch_company_capital()
    balance_sheet = fetch_balance_sheet()
    capital_stock_map = dict(balance_sheet)
    capital_stock_map.update(company_capital)  # 公司基本資料優先（涵蓋全部上市、單位為元）
    LOG.info(f"股本合併：公司基本資料 {len(company_capital)} ＋ 資產負債表 {len(balance_sheet)} → {len(capital_stock_map)} 檔")

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
    etf_ref = load_etf_reference()

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
        bb_twse = bwibbu_twse.get(sid, {}) if bwibbu_twse is not None else {"pe": ex.get("pe"), "pb": ex.get("pb"), "div": ex.get("div")}
        bal = capital_stock_map.get(sid, {})

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
        mc = ex.get("market_cap") or None  # 0 視為缺漏（null 不得轉成 0）
        if mc is None and sid in etf_shares and close is not None:
            shares = etf_shares[sid].get("shares_stock")
            if shares:
                mc = round(close * shares)

        # ROE/ROA/EPS 不在每日行情抓取：沿用既有值（由 import_official_fundamentals.py 以官方年化值同步）
        roe, roa, eps = ex.get("roe"), ex.get("roa"), ex.get("eps")
        capital_stock = bal.get("capital_stock") if bal.get("capital_stock") is not None else ex.get("capital_stock")
        shares = bal.get("shares") if bal.get("shares") is not None else ex.get("shares")

        # 一般股票市值 = 收盤 × 已發行普通股數（2026-11-13 修正：不再用 股本÷10 推股數，
        # 因為台股面額有 0.5／1／2.5／5 元與無面額，會把 32 檔算錯、最嚴重差 20 倍）。
        # 拿不到已發行股數時才退回 股本÷10；兩者都沒有則保留既有值（不補 0）。
        if close is not None and close > 0 and sid not in etf_shares:
            if shares:
                mc = data_rules.market_cap_from_shares(close, shares) or mc
            elif capital_stock:
                mc = data_rules.market_cap_from_capital(close, capital_stock) or mc

        # ETF 標記
        is_etf = bool(re.search(r"ETF|基金|指數|正[0-9]|反[0-9]|槓桿|反向|期貨|配息|高息|優息|收益", name or ""))

        # 本益比統一口徑（2026-11-13）：pe = 收盤 ÷ EPS，與本站顯示的 EPS 同期間基準，
        # 同一列的 pe 與 eps 必然互相吻合（舊版 pe 取自 TWSE、eps 取自 MOPS 累計年化，
        # 251 檔兩者差 >25%，同一列自我矛盾）。
        # 沒有 EPS（例如尚無官方財報的金融保險類）時才退回 TWSE 公告值，並以 pe_src 標示來源，
        # 不讓兩種基準混在同一個欄位裡說不清。
        pe_calc = data_rules.price_eps_consistent_pe(close, eps)
        pe_twse = data_rules.sanitize_pe(bb_twse.get("pe"), eps)
        pe_val = pe_calc if pe_calc is not None else pe_twse
        pe_src = "computed" if pe_calc is not None else ("official" if pe_twse is not None else None)

        # 資料來源標記
        source = "TWSE"
        quality = "official"
        # 治本：每筆記錄自己的價格日期。TWSE 記錄一律等於 trade_date。
        price_asof = trade_date

        stocks.append({
            "sym": sid,
            "name": name,
            "price": close,
            "open": open_p, "high": high, "low": low, "volume": volume,
            "pe": pe_val, "pe_official": data_rules.sanitize_pe(bb_twse.get("pe"), None), "pe_src": pe_src,
            "pb": bb_twse.get("pb"), "div": bb_twse.get("div"),
            "roe": roe, "roa": roa, "eps": eps, "capital_stock": capital_stock,
            "shares": shares,
            "market_cap": mc, "ind": ex.get("ind"),
            "is_etf": is_etf,
            "chg": chg,
            "rank": ex.get("rank"), **{k: ex.get(k) for k in OFFICIAL_KEYS},
            "source": source,
            "quality": quality,
            "price_asof": price_asof,
            "trading_status": "active",
        })
        sources["TWSE"] += 1

    # --- 處理 TPEX（只收上櫃 ETF）---
    # 本站設計：上市一般股票 + 上市 ETF + 上櫃 ETF。上櫃一般股票、權證等不收。
    # 類型一律由 classify_security() 依官方 ETF 清單判定（不以名稱判斷）。
    tpex_raw = fetch_tpex_daily()
    tpex_candidates = [r for r in tpex_raw
                       if keep_record(str(r.get("SecuritiesCompanyCode", "") or "").strip())
                       and classify_security(str(r.get("SecuritiesCompanyCode", "") or "").strip(), etf_ref) in TPEX_KEEP_TYPES]
    LOG.info(f"TPEX 候選筆數（僅 ETF，原始 {len(tpex_raw)} 筆）: {len(tpex_candidates)}")

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
    for r in tpex_candidates:
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

        # 治本：TPEX 常發布 T-0（當天），TWSE 只有 T-1/T-2，兩者本質上不同日。
        # 以該筆自己的 Date 當 price_asof，絕不覆寫成 trade_date ——
        # 否則週一的上櫃價會被標成上週五（曾造成 118 筆錯標 3 天）。
        _tpex_date = str(r.get("Date") or "").strip()
        try:
            price_asof = parse_date(_tpex_date) if _tpex_date else trade_date
        except Exception:
            price_asof = trade_date

        ex = existing.get(sid, {})
        bb_tpex = bwibbu_tpex.get(sid, {}) if bwibbu_tpex is not None else {"pe": ex.get("pe"), "pb": ex.get("pb"), "div": ex.get("div")}
        # TPEX 沒有營益分析/資產負債表 API，沿用既有資料
        roe = ex.get("roe")
        roa = ex.get("roa")
        eps = ex.get("eps")
        capital_stock = ex.get("capital_stock")
        mc = ex.get("market_cap") or None  # 0 視為缺漏（null 不得轉成 0）
        if mc is None and sid in etf_shares and close is not None:
            shares = etf_shares[sid].get("shares_stock")
            if shares:
                mc = round(close * shares)

        # 本益比統一口徑（同 TWSE）：pe = 收盤 ÷ EPS；無 EPS 才退回交易所公告值並以 pe_src 標示
        pe_calc = data_rules.price_eps_consistent_pe(close, eps)
        pe_off = data_rules.sanitize_pe(bb_tpex.get("pe"), eps)
        pe_val = pe_calc if pe_calc is not None else pe_off
        pe_src = "computed" if pe_calc is not None else ("official" if pe_off is not None else None)

        is_etf = classify_security(sid, etf_ref) == "etf"

        source = "TPEX"
        quality = "official"

        tpex_stocks.append({
            "sym": sid,
            "name": name,
            "price": close,
            "open": open_p, "high": high, "low": low, "volume": volume,
            "pe": pe_val, "pe_official": data_rules.sanitize_pe(bb_tpex.get("pe"), None), "pe_src": pe_src,
            "pb": bb_tpex.get("pb"), "div": bb_tpex.get("div"),
            "roe": roe, "roa": roa, "eps": eps, "capital_stock": capital_stock,
            "market_cap": mc, "ind": ex.get("ind"),
            "is_etf": is_etf,
            "chg": chg,
            "rank": ex.get("rank"), **{k: ex.get(k) for k in OFFICIAL_KEYS},
            "source": source,
            "quality": quality,
            "price_asof": price_asof,
            "trading_status": "active",
            "_est_mc": est_mc({"price": close, "volume": volume, "market_cap": mc}),
        })
        sources["TPEX"] = sources.get("TPEX", 0) + 1

    # P0-2：上櫃來源失敗或筆數異常時，不以空/殘缺資料覆蓋既有上櫃資料；沿用前次有效紀錄並標記 stale
    # （price_asof 保留舊日期，因此不會混入今日 history 切片，也不會冒充最新行情）
    # 沿用資料也只能是上櫃 ETF（舊檔若殘留上櫃一般股票，不可因 stale 沿用而復活）
    prev_tpex = [v for v in existing.values() if v.get("source") == "TPEX"
                 and classify_security(v.get("sym", ""), etf_ref) in TPEX_KEEP_TYPES]
    tpex_ok = (len(tpex_raw) >= TPEX_MIN_RAW and len(tpex_stocks) > 0
               and (not prev_tpex or len(tpex_stocks) >= 0.8 * len(prev_tpex)))
    if not tpex_ok:
        LOG.warn(f"TPEX 資料不完整（原始 {len(tpex_raw)} 筆，本次 {len(tpex_stocks)} 筆，前次 {len(prev_tpex)} 筆），沿用前次上櫃資料並標記 stale")
        tpex_stocks = []
        for v in prev_tpex:
            c = dict(v)
            c["quality"] = "stale"
            c["_est_mc"] = est_mc({"price": c.get("price"), "volume": c.get("volume"), "market_cap": c.get("market_cap")})
            tpex_stocks.append(c)
        LOG.stats["details"]["tpex_stale_carry"] = len(tpex_stocks)

    # 合併：每筆類型依官方 ETF 清單統一判定（security_type 為唯一來源）
    all_stocks = stocks + tpex_stocks
    for s in all_stocks:
        sec = classify_security(s.get("sym", ""), etf_ref)
        s["security_type"] = sec
        s["is_etf"] = sec == "etf"

    # 規矩：本站只收 上市一般股票 / 上市 ETF / 上櫃 ETF。
    # 特別股（2881A）、DR（91xxxx）、受益證券（01xxxT）、ETN（02xxxx）、權證等 other 類一律不收。
    _n_other = sum(1 for s in all_stocks if s["security_type"] == "other")
    if _n_other:
        LOG.info(f"排除其他證券（特別股／DR／受益證券／ETN／權證等）: {_n_other} 筆")
        LOG.stats["details"]["excluded_other"] = _n_other
        all_stocks = [s for s in all_stocks if s["security_type"] != "other"]

    # 停牌／無成交標的保留（2026-11-13）：TWSE 每日 feed 不含當日無成交的標的，
    # 舊版直接依 feed 重建 → 1808 潤隆 這類標的會無聲從資料庫消失（1445 → 1444），
    # 使用者的自選股與研究清單會突然少一檔。
    # 這裡把「前次快照有、本次 feed 沒有、但仍在上市公司清單（t187ap03_L）」的標的沿用回來：
    #   - 標記 trading_status='suspended'，保留最後一次成交價與它自己的 price_asof（不冒充最新價）
    #   - 已不在上市公司清單者＝下市 → 不復活（避免墓碑資料永久留存）
    #   - 範圍外證券（特別股／DR／ETN…）不因沿用而復活
    _fresh = {s.get("sym") for s in all_stocks}
    _listed = set(capital_stock_map.keys())
    _susp = []
    for _sym, _prev in existing.items():
        if _sym in _fresh or _sym not in _listed:
            continue
        if classify_security(_sym, etf_ref) == "other":
            continue
        c = dict(_prev)
        # 不冒充現價：suspended 沒有「當日收盤」，把現價欄位留空（缺值就讓它缺），
        # 最後一次成交價另存 last_close／last_close_date，前端顯示「—」而不是把舊價當今日價。
        # 注意：必須從「上一次的 last_close」接手，因為第二次起 _prev 的 price 已經是 None
        # （沿用記錄本身沒有 price），若只看 _prev["price"] 會把最後成交價洗掉。
        c["last_close"] = _prev.get("price") if _prev.get("price") is not None else _prev.get("last_close")
        _last_date = (_prev.get("price_asof") if _prev.get("price_asof") is not None
                      else _prev.get("last_close_date"))
        for _k in ("price", "open", "high", "low", "volume", "chg", "market_cap"):
            c[_k] = None
        # price_asof 保留「最後有價資料的日期」而不用 None：
        #   - meta 的 price_asof_counts 與 qa_gate 的日期規則就不必處理 None 鍵（JSON 會變 "null" 字串）
        #   - 「這個價是哪一天的」仍可追溯（price 為 null，不會被誤讀成當日價）
        #   - price_asof != trade_date，因此不會混進當日的 history 切片
        c["price_asof"] = _last_date
        c.pop("last_close_date", None)
        # 股本／已發行股數與行情無關，且仍在上市公司清單內 → 用官方值補齊（不猜）
        _ci = capital_stock_map.get(_sym) or {}
        if _ci.get("capital_stock"):
            c["capital_stock"] = _ci["capital_stock"]
        if _ci.get("shares"):
            c["shares"] = _ci["shares"]
        c["trading_status"] = "suspended"
        c["_est_mc"] = 0
        _susp.append(c)
    if _susp:
        LOG.warn(f"停牌／當日無成交，沿用前次紀錄 {len(_susp)} 檔並標記 suspended（保留最後成交日，不改價）："
                 f"{[s['sym'] for s in _susp][:10]}")
        LOG.stats["details"]["suspended_carry"] = len(_susp)
        all_stocks.extend(_susp)

    # 依市值排序取前 SAFE_MAX；超過時明確記錄被截除的筆數，不默默丟資料
    all_stocks.sort(key=lambda x: x.get("_est_mc", 0), reverse=True)
    if len(all_stocks) > SAFE_MAX:
        cut = len(all_stocks) - SAFE_MAX
        LOG.warn(f"合併後 {len(all_stocks)} 筆超過上限 {SAFE_MAX}，截除市值最小的 {cut} 筆")
        LOG.stats["details"]["truncated"] = cut
    all_stocks = all_stocks[:SAFE_MAX]
    sources = {"TWSE": 0, "TPEX": 0}
    for s in all_stocks:
        sources[s.get("source")] = sources.get(s.get("source"), 0) + 1

    # 清理暫存欄位
    for s in all_stocks:
        s.pop("_est_mc", None)

    stocks = all_stocks

    # ===== 方案二：yfinance 補齊 capital_stock / eps 缺漏 =====
    meta = {
        "as_of": trade_date,
        "source": f"TWSE OpenAPI STOCK_DAY_ALL (免 key, 雲端)",
        "schema_version": SCHEMA_VERSION,
        "count": len(stocks),
        "sources": sources,
        "note": "收盤/漲跌每日更新；ROE/ROA/EPS 由官方財報累計年化同步（import_official_fundamentals.py），股本取自資產負債表；範圍：上市一般股票 + 上市/上櫃 ETF（上櫃一般股票、特別股、DR、受益證券、ETN、權證皆不收）；ETF 依官方清單判定；上限 3000 檔",
    }

    # 排除 U 尾代號（期貨型 ETF 與認購權證 7xxxxU），依使用者要求，資料庫與 CSV 都不納入
    stocks = [s for s in stocks if not str(s.get("sym", "")).endswith("U")]
    meta["count"] = len(stocks)
    meta["note"] = meta["note"] + "；已排除 U 尾代號（期貨型 ETF / 認購權證）"

    # 揭露各 price_asof 的筆數：一眼看出有沒有把別天的價格混進這個快照
    _pa = {}
    for _s in stocks:
        _k = _s.get("price_asof")
        _pa[_k] = _pa.get(_k, 0) + 1
    meta["price_asof_counts"] = _pa

    _prev_asof = None
    try:
        _prev_asof = str(json.load(open(os.path.join(OUT, "stocks.json"), encoding="utf-8")).get("meta", {}).get("as_of") or "")[:10]
    except Exception:
        pass
    if _prev_asof and _prev_asof > str(trade_date)[:10]:
        LOG.warn(f"既有 stocks.json 日期 {_prev_asof} 比本次資料 {trade_date} 新，不以舊資料覆蓋")
    else:
        with open(os.path.join(OUT, "stocks.json"), "w", encoding="utf-8") as f:
            json.dump(_sanitize_nan({"meta": meta, "stocks": stocks}), f, ensure_ascii=False)

    # 當日 history 切片（收盤價 + PE/PB/殖利率）
    # 只納入價格日期等於快照日期的記錄：一份 dated snapshot 不可以混進別天的價格。
    # TPEX 常領先 TWSE 一天以上，混入會讓回測/指標/前端讀到錯日期的收盤。
    hist = [{
        "stock_id": s["sym"], "stock_name": s["name"], "close": s["price"],
        "open": s["open"], "high": s["high"], "low": s["low"], "volume": s["volume"],
        "pe_ratio": s["pe"], "pb_ratio": s["pb"], "dividend_yield": s["div"],
        "industry": s["ind"],
    } for s in stocks if s.get("price_asof") == trade_date]
    # 防護：休市日或來源資料不完整時，TWSE 會回傳舊資料且缺少高低價；這種日子不是交易日，
    # 不可寫入 history（否則回測與指標會讀到錯誤收盤值）。
    miss_hl = sum(1 for s in stocks if s.get("high") is None)
    hpath = None  # 休市/來源不完整時不會寫入 history，下方記錄需容忍 None
    if stocks and miss_hl / len(stocks) > 0.5:
        LOG.warn(f"{trade_date} 高低價缺失 {miss_hl}/{len(stocks)}，疑似休市或來源不完整，不寫入 history 切片")
    else:
        hpath = os.path.join(OUT, "history", f"{trade_date.replace('-', '')}.json")
        if os.path.exists(hpath):
            LOG.warn(f"{trade_date} 歷史快照已存在，不覆蓋（防止重複寫入或舊資料覆蓋）")
        else:
            with open(hpath, "w", encoding="utf-8") as f:
                json.dump(_sanitize_nan({"trade_date": trade_date, "schema_version": SCHEMA_VERSION,
                           "count": len(hist), "stocks": hist}), f, ensure_ascii=False)

    # industry.json：若已有則保留（不覆寫，避免每天清空）
    ind_path = os.path.join(OUT, "industry.json")
    if not os.path.exists(ind_path):
        ind_out = [{"nm": nm, "chg": 0.0, "cnt": 0, "top": 0.0} for nm in codes.values()]
        with open(ind_path, "w", encoding="utf-8") as f:
            json.dump({"meta": {**meta, "count": len(ind_out)},
                       "industry": ind_out}, f, ensure_ascii=False)

    LOG.stats["details"]["schema_version"] = SCHEMA_VERSION

    LOG.stats["written"] = len(stocks)
    LOG.stats["details"]["trade_date"] = trade_date
    # 2026-11-13：TWSE 日期落後 TPEX 一個交易日 → 上市股價未更新，明確告警（qa_gate 會以 TWSE_STALE 阻擋）
    _tpex_dates = [x.get("price_asof") for x in stocks if x.get("source") == "TPEX" and x.get("price_asof")]
    if _tpex_dates and max(_tpex_dates) > str(trade_date)[:10]:
        LOG.warn(f"TWSE 日期 {trade_date} 落後 TPEX {max(_tpex_dates)}：上市股價疑似未更新，請檢查 TWSE OpenAPI")
        LOG.stats["details"]["twse_stale_vs_tpex"] = max(_tpex_dates)
    LOG.stats["details"]["history_file"] = os.path.basename(hpath) if hpath else None
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
    # 只補「沒有 TWSE 官方財報」的一般股票；官方 ROE/ROA/EPS 已有者與 ETF 不需要 yfinance（大幅縮短執行時間）
    syms = [s["sym"] for s in stocks
            if s.get("fund_src") != "TWSE_OFFICIAL" and s.get("security_type", "stock") == "stock"]
    LOG.stats["fetched"] = len(syms)
    LOG.info(f"待補 {len(syms)} 檔")
    roe_map = fetch_yfinance_roe(syms)
    for s in stocks:
        if s["sym"] in roe_map:
            s["roe"] = roe_map[s["sym"]].get("roe")
            s["roa"] = roe_map[s["sym"]].get("roa")
            # 只標註 ROE/ROA 的補充來源；不得覆寫 source（source 表示行情來源，meta.sources 依此統計）
            s["roe_src"] = "yfinance"
            s["quality"] = "yfinance_fallback"
    # ====== 新增：週更新產業別 ======
    industry_map = fetch_industry_map()
    if industry_map:
        codes, fallback = load_codes()
        apply_industry_to_stocks(stocks, industry_map, codes, fallback)
    else:
        LOG.warn("Industry map empty; skipping industry classification update")
    data["meta"]["roe_source"] = "yfinance (免 key, 每週六更新, 備用)"
    recompute_meta(data)  # 寫入前重算 meta，避免 sources / count 與陣列不一致
    with open(p, "w", encoding="utf-8") as f:
        json.dump(_sanitize_nan(data), f, ensure_ascii=False)
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

    def build(items):
        out = []
        for item in items:
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

    indices = build(indices_cfg)
    etfs = build(etfs_cfg)
    
    # 抓取巨集經濟指標
    macro_items = macro_cfg
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
        json.dump(_sanitize_nan({"meta": meta, "indices": indices, "etfs": etfs, "macro": macro}), f, ensure_ascii=False, indent=2)

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


def fetch_industry_map():
    """
    Retrieve industry code mapping from TWSE t187ap03_L.
    Returns a dict {stock_symbol: industry_code}.
    On failure, returns empty dict.
    """
    url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
    try:
        raw = fetch_json(url, timeout=30)
        if not isinstance(raw, list):
            LOG.warn("t187ap03_L response is not a list")
            return {}
        industry_map = {}
        for r in raw:
            sym = str(r.get("公司代號", "")).strip()
            ind_code = str(r.get("產業別", "")).strip()
            if sym and ind_code:
                industry_map[sym] = ind_code
        LOG.info(f"Fetched industry map for {len(industry_map)} stocks")
        return industry_map
    except Exception as e:
        LOG.warn(f"Failed to fetch industry map: {e}")
        return {}


def apply_industry_to_stocks(stocks, industry_map, codes, fallback):
    """
    Update the 'ind' field of each stock in stocks based on industry_map.
    industry_map: dict {symbol: industry_code}
    codes: dict {industry_code: industry_name}
    fallback: default industry name if code not found
    Modifies stocks list in place.
    """
    updated = 0
    for s in stocks:
        sym = s.get("sym")
        if not sym:
            continue
        ind_code = industry_map.get(sym)
        if ind_code is None:
            # keep existing ind if no data
            continue
        ind_name = codes.get(ind_code, fallback)
        if s.get("ind") != ind_name:
            s["ind"] = ind_name
            updated += 1
    LOG.info(f"Applied industry classification to {updated} stocks")
if __name__ == "__main__":
    try:
        if MODE == "weekly":
            run_weekly()
        elif MODE == "indices":
            run_indices()
        elif MODE == "twii":
            run_twii()
        else:
            run_daily()
    except Exception as e:
        # 任何未被個別函式攔截的非預期例外，先寫入結構化 log 再往外拋，
        # 避免 GitHub Actions 只看到裸露的 traceback、卻沒有 fetch-log.json 可查。
        LOG.error(f"未預期例外，執行中止：{e}")
        LOG.finish(False, error=f"未預期例外：{e}")
        raise