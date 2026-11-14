#!/usr/bin/env python3
"""
data_rules.py — 資料品質共用規則（2026-11-13 修正計畫）

目的：把「單位換算」「欄位合理性」「跨欄位一致性」集中在一處，
fetch_data.py / fetch_us_data.py / sanitize_snapshot.py / qa_gate.py 共用，
避免各自寫一份而分岔（本專案已多次因此出事故）。

零依賴、純 Python，可直接 import，也可被 tests/ 直接測。

對應事故：
  1. 股本永遠為 0：TWSE_BALANCE 指向的 t187ap05_L 其實是「月營收」，
     沒有「普通股股本」欄位 → 改用 t187ap07_L_* 資產負債表；股本單位為「仟元」。
  2. 美股 ytd_return 放大 100 倍：yfinance 的 ytdReturn 已是百分比，又乘 100。
  3. 美股 div（殖利率）放大：yfinance dividendYield 已是百分比，又乘 100。
  4. 美股 PB 異常（BRK-B 0.0011、ABBV -113）：priceToBook 來源不可靠。
  5. EPS 為負卻仍有 PE（例：1225 福懋油 EPS -1.3、PE 120）。
  6. TWSE 日期落後 TPEX 一個交易日仍被當成正常。
"""
import math
import os
from typing import Any, Dict, List, Optional

# ---------- 單位 ----------
# 資產負債表「股本」單位為新台幣「仟元」（台積電 259,303,804 仟元 = 2,593 億元）
BALANCE_CAPITAL_UNIT_TWD = 1000
# 台股面值 10 元
PAR_VALUE_TWD = 10

# 資產負債表端點（上市）。依 data/raw/twse-openapi-full.md 的欄位說明，
# 「股本」欄位存在於以下各業別。金融業（basi/fh/ins/mim）與一般業/證券業皆需涵蓋。
TWSE_BALANCE_ENDPOINTS = [
    "https://openapi.twse.com.tw/v1/opendata/t187ap07_L_ci",
    "https://openapi.twse.com.tw/v1/opendata/t187ap07_L_basi",
    "https://openapi.twse.com.tw/v1/opendata/t187ap07_L_bd",
    "https://openapi.twse.com.tw/v1/opendata/t187ap07_L_fh",
    "https://openapi.twse.com.tw/v1/opendata/t187ap07_L_ins",
    "https://openapi.twse.com.tw/v1/opendata/t187ap07_L_mim",
]
BALANCE_CAPITAL_KEY = "股本"

# 上市公司基本資料（t187ap03_L）：涵蓋全部上市約 1,099 家，「實收資本額」單位為新台幣元。
# 這是股本最完整的來源；t187ap07_L_* 資產負債表只含「該期別已申報」者（2026-11-13 實測
# 752/1,099，台積電 2330、富邦金 2881 都不在內）→ 以本端點為主、資產負債表為備援。
# 實測值：2330 = 259,323,700,670 元（2,593 億元）。
TWSE_COMPANY_INFO_ENDPOINT = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
COMPANY_CAPITAL_KEY = "實收資本額"
# 已發行普通股數（股）：市值的正確輸入。同一份 t187ap03_L 就有，不必由股本推。
COMPANY_SHARES_KEY = "已發行普通股數或TDR原股發行股數"
COMPANY_CAPITAL_UNIT_TWD = 1  # 已是新台幣元，不做仟元換算

# ---------- 合理範圍 ----------
PE_MAX = 1000.0          # 超過視為異常（與前端「-」顯示一致）
PB_RANGE = (0.05, 200.0)  # 淨值比合理區間
US_DIV_MAX_PCT = 30.0     # 美股殖利率超過 30% 幾乎只可能是資料錯誤
US_YTD_RANGE_PCT = (-100.0, 500.0)
PE_EPS_TOLERANCE = 0.25   # PE 與 價/EPS 相差超過 25% 視為不一致（PE 與 EPS 期間基準可能不同）


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and not (isinstance(v, float) and math.isnan(v)) and not math.isinf(v)


def _num_or_none(v: Any) -> Optional[float]:
    return float(v) if _is_num(v) else None


# ---------- 台股 ----------
def balance_capital_to_twd(raw: Any) -> Optional[float]:
    """資產負債表「股本」(仟元) → 新台幣元。無效值回傳 None。"""
    v = _num_or_none(raw)
    if v is None or v <= 0:
        return None
    return v * BALANCE_CAPITAL_UNIT_TWD


def company_capital_to_twd(raw: Any) -> Optional[float]:
    """上市公司基本資料「實收資本額」→ 新台幣元。單位已是元，不做換算；無效值回傳 None。"""
    v = _num_or_none(raw)
    if v is None or v <= 0:
        return None
    return v * COMPANY_CAPITAL_UNIT_TWD


def capital_unit_plausible(capitals_twd: List[float]) -> bool:
    """單位保險絲：換算後的股數中位數必須落在台股合理範圍（1 千萬～500 億股）。
    若 TWSE 實際單位不是仟元，換算後數值會落在範圍外，寧可整批不寫入也不要寫錯市值。"""
    shares = sorted(c / PAR_VALUE_TWD for c in capitals_twd if _is_num(c) and c > 0)
    if len(shares) < 50:
        return False
    med = shares[len(shares) // 2]
    return 1e7 <= med <= 5e10


def market_cap_from_shares(price: Any, shares: Any) -> Optional[float]:
    """市值 = 收盤 × 已發行普通股數。任一無效回傳 None（不補 0）。

    2026-11-13：改以此為主要算法。舊的 market_cap_from_capital 假設面額固定 10 元，
    但台股面額有 0.5／1／2.5／5 元，甚至有「無面額」公司（實測 32 檔不符、13 檔誤差 >20%，
    最嚴重 6919 康霈* 差 20 倍）→ 直接用官方「已發行普通股數」，不對面額做任何假設。
    """
    p, s = _num_or_none(price), _num_or_none(shares)
    if p is None or s is None or p <= 0 or s <= 0:
        return None
    return round(p * s)


def market_cap_from_capital(price: Any, capital_twd: Any) -> Optional[float]:
    """（備援）市值 = 收盤 × 股數；股數 = 股本(元) ÷ 面值 10。任一無效回傳 None（不補 0）。

    只在拿不到「已發行普通股數」時使用。面額非 10 元或無面額的公司會算錯，
    優先使用 market_cap_from_shares。"""
    p, c = _num_or_none(price), _num_or_none(capital_twd)
    if p is None or c is None or p <= 0 or c <= 0:
        return None
    return round(p * (c / PAR_VALUE_TWD))


def sanitize_pe(pe: Any, eps: Any) -> Optional[float]:
    """EPS ≤ 0 時本益比無意義 → None；PE 超出範圍 → None。"""
    p = _num_or_none(pe)
    e = _num_or_none(eps)
    if p is None:
        return None
    if e is not None and e <= 0:
        return None
    if p <= 0 or p > PE_MAX:
        return None
    return p


def pe_eps_mismatch(pe: Any, price: Any, eps: Any, tol: float = PE_EPS_TOLERANCE) -> bool:
    """PE 與 價/EPS 是否明顯不一致（只在兩邊都有效時判斷）。"""
    p, pr, e = _num_or_none(pe), _num_or_none(price), _num_or_none(eps)
    if p is None or pr is None or e is None or e <= 0 or p <= 0:
        return False
    implied = pr / e
    return abs(implied - p) / p > tol


# ---------- 美股 ----------
def us_dividend_yield_pct(info: Dict[str, Any]) -> Optional[float]:
    """殖利率（百分比）。優先 dividendRate ÷ 價格（單位明確）；
    退回 dividendYield（yfinance 新版為百分比值，不再乘 100）。超範圍 → None。"""
    price = _num_or_none(info.get("currentPrice") or info.get("regularMarketPrice"))
    rate = _num_or_none(info.get("dividendRate"))
    if rate is not None and price and price > 0:
        y = rate / price * 100
    else:
        y = _num_or_none(info.get("dividendYield"))
    if y is None or y < 0 or y > US_DIV_MAX_PCT:
        return None
    return round(y, 2)


def us_ytd_pct(raw: Any) -> Optional[float]:
    """yfinance ytdReturn 已是百分比（11.7 = 11.7%），不再乘 100。"""
    v = _num_or_none(raw)
    if v is None or not (US_YTD_RANGE_PCT[0] <= v <= US_YTD_RANGE_PCT[1]):
        return None
    return round(v, 2)


def us_expense_ratio_pct(info: Dict[str, Any]) -> Optional[float]:
    """ETF 費用率（百分比）。

    2026-11-13：舊版只讀 `annualReportExpenseRatio`，實測 30/30 檔都回 None → 全部顯示空。
    改用 `netExpenseRatio`（實測 VOO 0.03、SPY 0.0945、QQQ 0.18，**單位已是百分比**）。
    退回 `annualReportExpenseRatio` 時，該欄位歷史上為小數（0.0003）→ 明顯小於 0.01 才 ×100。
    超過 5% 幾乎必為單位錯誤 → None（不猜）。
    """
    v = _num_or_none(info.get("netExpenseRatio"))
    if v is not None and 0 < v <= 5:
        return round(v, 3)
    v2 = _num_or_none(info.get("annualReportExpenseRatio"))
    if v2 is not None and v2 > 0:
        pct = v2 * 100 if v2 < 0.01 else v2
        if 0 < pct <= 5:
            return round(pct, 3)
    return None


def price_eps_consistent_pe(price: Any, eps: Any) -> Optional[float]:
    """本益比＝收盤 ÷ EPS（與本站顯示的 EPS 同一口徑，可自我驗證）。

    2026-11-13：舊版 `pe` 來自 TWSE BWIBBU，`eps` 來自 MOPS 累計年化，兩者期間基準不同
    → 251 檔「價/EPS 與 pe 差 >25%」，同一列兩個數字互相矛盾。
    改為統一口徑：`pe = 收盤 ÷ EPS`（EPS ≤ 0 或任一無效 → None，不補值）。
    """
    p, e = _num_or_none(price), _num_or_none(eps)
    if p is None or e is None or p <= 0 or e <= 0:
        return None
    pe = p / e
    # 與 sanitize_pe 同一條上限規則：極端 PE（>1000，通常來自極小 EPS）視為無意義 → None，
    # 在寫入時就判定，不要等到 sanitize 事後補刀（否則沒跑 sanitize 就會留下極端值）。
    if pe > PE_MAX:
        return None
    return round(pe, 2)


# TWSE 的 PEratio 定義為「收盤價 ÷ 最近四季每股盈餘（TTM）」，因此可由兩者精確還原官方用過的 EPS。
EPS_SRC_OFFICIAL = "TWSE_OFFICIAL"
EPS_SRC_YFINANCE = "yfinance"
EPS_SRC_PE_IMPLIED = "TWSE_PE_IMPLIED"  # 由官方 PE 反推（金融保險類無官方損益表時的來源）


def eps_from_official_pe(price: Any, pe_official: Any) -> Optional[float]:
    """由交易所公告 PE 反推 TTM EPS＝收盤 ÷ 官方PE。

    只用於「免費官方管道拿不到損益表」的金融保險類（金控／銀行／保險）。
    這不是估算：TWSE 的 PE 定義就是「收盤 ÷ 最近四季 EPS」，反推即還原該官方數字。
    還原後 `pe = 收盤 ÷ eps` 會回到官方 PE，同一列的兩個數字不再互相矛盾。
    """
    p, pe = _num_or_none(price), _num_or_none(pe_official)
    if p is None or pe is None or p <= 0 or pe <= 0:
        return None
    return round(p / pe, 2)


def apply_pe_from_eps(rec: Dict[str, Any]) -> None:
    """就地依 pe = 收盤 ÷ EPS 重算 pe / pe_src；沒有 EPS 才退回交易所公告值。冪等。"""
    pe_calc = price_eps_consistent_pe(rec.get("price"), rec.get("eps"))
    if pe_calc is not None:
        rec["pe"], rec["pe_src"] = pe_calc, "computed"
        return
    off = rec.get("pe_official")
    if _is_num(off):
        rec["pe"], rec["pe_src"] = off, "official"
    else:
        rec["pe"], rec["pe_src"] = None, None


def us_price_to_book(info: Dict[str, Any]) -> Optional[float]:
    """優先 price / bookValue（每股淨值，單位明確）；退回 priceToBook；超範圍 → None。"""
    price = _num_or_none(info.get("currentPrice") or info.get("regularMarketPrice"))
    bv = _num_or_none(info.get("bookValue"))
    if price and bv and bv > 0:
        pb = price / bv
    else:
        pb = _num_or_none(info.get("priceToBook"))
    if pb is None or not (PB_RANGE[0] <= pb <= PB_RANGE[1]):
        return None
    return round(pb, 4)


# ---------- 快照修復（用於既有 JSON） ----------
# 美股快照的單位修復是「整批」層級：舊版程式把 yfinance 已是百分比的 dividendYield / ytdReturn
# 又乘了 100，所以「每一筆」都放大 100 倍（不是只有離譜的幾筆）。因此以檔案 meta 的
# units 標記做冪等修復：標記為 "pct" 的檔案不會被重複除以 100。
UNIT_MARK_KEY = "units"


def _units_fixed(doc: Dict[str, Any], field: str) -> bool:
    return (doc.get("meta") or {}).get(UNIT_MARK_KEY, {}).get(field) == "pct"


def _mark_units(doc: Dict[str, Any], field: str) -> None:
    doc.setdefault("meta", {}).setdefault(UNIT_MARK_KEY, {})[field] = "pct"


def sanitize_stock_record(s: Dict[str, Any]) -> List[str]:
    """就地修正一筆台股紀錄（確定性規則，不猜值）。"""
    notes = []
    new_pe = sanitize_pe(s.get("pe"), s.get("eps"))
    if s.get("pe") is not None and new_pe is None:
        notes.append(f"pe {s.get('pe')} → null（EPS={s.get('eps')}）")
        s["pe"] = None
    return notes


def sanitize_us_stocks_doc(doc: Dict[str, Any]) -> List[str]:
    """美股個股：殖利率整批 ÷100（**依數值判斷**），再逐筆檢查範圍。

    2026-11-13：不再只用 meta 標記判斷。標記存在 meta，而 `fetch_us_data.py` 每次都重寫
    整個檔案（標記消失），於是下一次 sanitize 會再除一次 100（AAPL 0.3 → 0.003）。
    改成看「整批中位數」：正常美股殖利率中位數約 0.5~3%，中位數 >10% 才是 ×100 事故。
    換算後中位數自動落回正常範圍 → 天然冪等。
    """
    notes: List[str] = []
    rows = doc.get("stocks", [])
    divs = [r["div"] for r in rows if _is_num(r.get("div")) and r["div"] > 0]
    med = sorted(divs)[len(divs) // 2] if divs else None
    if med is not None and med > 10:
        for r in rows:
            if _is_num(r.get("div")):
                r["div"] = round(r["div"] / 100, 2)
        _mark_units(doc, "div")
        notes.append(f"div 整批 ÷100（{len(rows)} 筆，中位數 {med}% 明顯是 ×100）")
    for r in rows:
        d = r.get("div")
        if _is_num(d) and not (0 <= d <= US_DIV_MAX_PCT):
            notes.append(f"{r.get('sym')} div {d} → null（超過 {US_DIV_MAX_PCT}%）")
            r["div"] = None
        pb = r.get("pb")
        if _is_num(pb) and not (PB_RANGE[0] <= pb <= PB_RANGE[1]):
            notes.append(f"{r.get('sym')} pb {pb} → null（超出 {PB_RANGE}）")
            r["pb"] = None
    return notes


def sanitize_us_etfs_doc(doc: Dict[str, Any]) -> List[str]:
    """美股 ETF：年初至今報酬整批 ÷100（若尚未標記）。"""
    notes: List[str] = []
    rows = doc.get("etfs", [])
    yts = [abs(r["ytd_return"]) for r in rows if _is_num(r.get("ytd_return"))]
    ymed = sorted(yts)[len(yts) // 2] if yts else None
    # 同 div：依數值判斷（正常年初至今報酬中位數絕對值遠小於 30%），換算後天然冪等
    if ymed is not None and ymed > 30:
        for r in rows:
            if _is_num(r.get("ytd_return")):
                r["ytd_return"] = round(r["ytd_return"] / 100, 2)
        _mark_units(doc, "ytd")
        notes.append(f"ytd_return 整批 ÷100（{len(rows)} 筆，中位數絕對值 {ymed}% 明顯是 ×100）")
    return notes


# ---------- ETF 持股快照（n 的語意） ----------
# etf-holdings.json 的 n 原本被當成「成份股總數」顯示，但 299/363 檔其實只存了
# 權重前 10 大，n 就等於陣列長度（0050 顯示 10 檔、實際 50 檔；00850 顯示 10、實際約 100）。
# 這裡不改資料來源，只把語意修正為可證實的值：
#   n_listed = 實際列出的檔數（永遠可證實）
#   n        = 可證實的「成份股總數」；無法證實時為 None（前端顯示「—」，不顯示錯的 10）
# 判定：截斷只發生在「權重前 10 大」這個切點，因此
#   - 官方直出完整清單（src 開頭為 FULL_LIST_SRCS）→ n = len(items)
#   - len(items) != 10 → 不可能是被前 10 大截斷的結果 → n = len(items)
#   - len(items) == 10 且非官方完整清單 → 無法證實 → n = None
FULL_LIST_SRCS = ("FUBON",)


def etf_holdings_n(items_len: int, src: Any) -> Optional[int]:
    """回傳可證實的成份股總數；無法證實回傳 None。"""
    if items_len is None or items_len < 0:
        return None
    # 必須「完全等於」官方完整清單來源；`FUBON+CMONEY` 是「富邦頁面取不到、退回 CMoney 前 10 大」，
    # 仍是被截斷的（用 split("+")[0] 判斷會把它誤認為完整清單）。
    head = str(src or "").strip().upper()
    if head in FULL_LIST_SRCS or items_len != 10:
        return items_len
    return None


def sanitize_etf_holdings_doc(doc: Dict[str, Any]) -> List[str]:
    """修正 etf-holdings.json 的 n 語意（見 etf_holdings_n）。冪等。"""
    notes: List[str] = []
    hold = doc.get("holdings") or {}
    unknown = complete = changed = 0
    for _sym, h in hold.items():
        items = h.get("items") or []
        n_new = etf_holdings_n(len(items), h.get("src"))
        if h.get("n_listed") != len(items):
            h["n_listed"] = len(items)
            changed += 1
        if h.get("n") != n_new:
            h["n"] = n_new
            changed += 1
        if n_new is None:
            unknown += 1
        else:
            complete += 1
    note = ("n = 可證實的成份股總數（官方直出完整清單者）；只取得權重前 10 大、無法證實總數時為 null，"
            "前端顯示「—」而非錯誤的 10。n_listed = 本檔實際列出的成份股檔數。")
    meta = doc.setdefault("meta", {})
    if meta.get("note") != note:
        meta["note"] = note
        changed += 1
    if changed:
        notes.append(f"n 語意修正：可證實 {complete} 檔、無法證實改 null {unknown} 檔（{changed} 處變更）")
    return notes


# ---------- 快照驗證（供 qa_gate 與測試共用） ----------
def validate_snapshot(stocks_doc: Dict[str, Any], us_stocks_doc: Optional[Dict[str, Any]] = None,
                      us_etfs_doc: Optional[Dict[str, Any]] = None,
                      etf_holdings_doc: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    """回傳 issues：[{level: ERROR|WARNING, code, msg}]。
    ERROR 會阻擋發布（qa_gate），WARNING 只提醒。"""
    issues: List[Dict[str, str]] = []

    def add(level, code, msg):
        issues.append({"level": level, "code": code, "msg": msg})

    stocks = stocks_doc.get("stocks", []) if isinstance(stocks_doc, dict) else []
    meta = stocks_doc.get("meta", {}) if isinstance(stocks_doc, dict) else {}

    # 1. 股本
    n_stock = [s for s in stocks if s.get("security_type") == "stock"]
    zero_cap = [s["sym"] for s in n_stock if not s.get("capital_stock")]
    if zero_cap:
        add("ERROR", "CAPITAL_ZERO",
            f"一般股票股本為空/0：{len(zero_cap)}/{len(n_stock)} 檔（市值無法計算）")

    # 2. 負 EPS 仍有 PE
    neg_pe = [s["sym"] for s in stocks if _is_num(s.get("eps")) and s["eps"] <= 0 and _is_num(s.get("pe"))]
    if neg_pe:
        add("ERROR", "NEG_EPS_PE", f"EPS≤0 卻有 PE：{len(neg_pe)} 檔，例 {neg_pe[:5]}")

    # 3. PE 與 價/EPS 不一致（僅提醒，因 PE 與 EPS 期間基準可能不同）
    mism = [s["sym"] for s in stocks if pe_eps_mismatch(s.get("pe"), s.get("price"), s.get("eps"))]
    if mism:
        add("WARNING", "PE_EPS_MISMATCH",
            f"PE 與 價/EPS 偏差超過 {int(PE_EPS_TOLERANCE*100)}%：{len(mism)} 檔，需確認期間基準")

    # 3b. 本益比退回交易所公告值：金融保險類（金控／銀行／保險）在免費官方管道拿不到 EPS，
    #     所以 pe 只能用交易所公告的 PE（pe_src='official'），與本站 EPS 不同基準。
    #     這不是錯誤，但必須「可見且不會悄悄變多」——所以列成 WARNING 並附原因。
    #     實測（2026-11-14）：TWSE t187ap06_L_fh 只回 1 筆全空資料、mopsfin t187ap06_L_fh.csv
    #     只有表頭、MOPS 舊 API 被 WAF 擋；yfinance 的台股金融 EPS 為 FY2025 過期值（不可用）。
    fallback = [s["sym"] for s in stocks if s.get("pe_src") == "official"]
    if fallback:
        add("WARNING", "PE_OFFICIAL_FALLBACK",
            f"{len(fallback)} 檔無可用本站 EPS（含極端值），本益比沿用交易所公告值：{fallback[:5]}…")
    #     金融保險類（金控／銀行／保險）沒有官方損益表 → EPS 由官方 PE 反推
    #     （TWSE 的 PE 定義＝收盤 ÷ 最近四季 EPS，反推屬精確還原，不是估算），
    #     仍列 WARNING 讓來源可見、數量異常增加時能立刻發現。
    implied = [s["sym"] for s in stocks if s.get("eps_src") == EPS_SRC_PE_IMPLIED]
    if implied:
        add("WARNING", "PE_EPS_IMPLIED",
            f"{len(implied)} 檔無官方損益表，EPS 由官方 PE 反推（TWSE_PE_IMPLIED；pe 與官方值一致）："
            f"{implied[:5]}…")

    # 3c. 官方加值資料（market-extras，2026-11-14 導入）：月營收／融資融券／官方營益分析。
    #     依架構決策，這些**不放在 stocks.json**（會讓單檔從 1,213 KB 爆到 1,751 KB，違反體積預算），
    #     而是放在 data/market-extras.json 由前端按需載入；主檔只在 meta.market_extras 記來源與筆數。
    #     因此這裡檢查 meta 記錄與資料檔本體，而不是逐列欄位。
    me = (stocks_doc.get("meta") or {}).get("market_extras") or {}
    if not me:
        add("WARNING", "MARKET_EXTRAS_MISSING",
            "stocks.json 的 meta.market_extras 不存在：官方加值資料未整合；"
            "請確認 fetch_market_extras.py 與 integrate_market_extras.py 有在鏈上執行")
    else:
        _counts = me.get("counts") or {}
        for _n, _k, _floor in (("月營收", "revenue", 900), ("融資融券", "margin", 900),
                               ("官方營益分析", "profitability", 800)):
            _c = _counts.get(_k, 0)
            if _c < _floor:
                add("WARNING", "MARKET_EXTRAS_LOW_COVERAGE",
                    f"{_n}僅 {_c} 筆（預期 ≥ {_floor}），請確認官方端點是否縮水")
        # 資料檔本體必須存在且有內容（meta 有記錄但檔案被刪是最容易漏掉的情況）
        _fp = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "data", "market-extras.json")
        if not os.path.exists(_fp) or os.path.getsize(_fp) < 10240:
            add("ERROR", "MARKET_EXTRAS_FILE_MISSING",
                f"meta 有記錄但 {os.path.relpath(_fp)} 不存在或過小")

    # 3d. 停牌標記一致性：由官方暫停交易清單標記者必須有停止日（否則無法稽核）
    _halt_bad = [s["sym"] for s in stocks
                 if s.get("suspended_reason") == "halt" and not s.get("halt_date")]
    if _halt_bad:
        add("ERROR", "HALT_WITHOUT_DATE",
            f"{len(_halt_bad)} 檔標為官方暫停交易卻無停止日：{_halt_bad[:5]}")

    # 4. 日期：TWSE 端點（STOCK_DAY_ALL）結構上只發 T-1，TPEX 發 T-0，
    #    因此「TWSE 較 TPEX 落後 1 個交易日」是來源的既定行為，不是資料沒更新
    #    （實測：2026-11-13 盤後 TWSE 回 11-12、TPEX 回 11-13）。
    #    → 落後 1 個交易日 = WARNING；落後 ≥2 個交易日才是真的沒更新 = ERROR。
    #    不這樣分，這條規則會在每個交易日盤後都誤判為 ERROR，讓閘門永遠 BLOCK。
    dates = {}
    for s in stocks:
        k = (s.get("source"), s.get("price_asof"))
        dates[k] = dates.get(k, 0) + 1
    # 過濾掉 None（停牌沿用記錄可能沒有 price_asof），否則 max() 會拿 str 與 None 相比而爆掉
    twse_d = {d for (src, d) in dates if src == "TWSE" and d}
    tpex_d = {d for (src, d) in dates if src == "TPEX" and d}
    if twse_d and tpex_d and max(tpex_d) > max(twse_d):
        tw, tp = max(twse_d), max(tpex_d)
        # 以快照中出現過的 price_asof 當交易日曆，算 TWSE 實際落後幾個交易日
        cal = sorted({s.get("price_asof") for s in stocks if s.get("price_asof")})
        gap = (cal.index(tp) - cal.index(tw)) if (tw in cal and tp in cal) else 99
        if gap <= 1:
            add("WARNING", "TWSE_T_MINUS_1",
                f"TWSE 最新日期 {tw} 較 TPEX {tp} 落後 1 個交易日（STOCK_DAY_ALL 只發 T-1，屬預期行為）")
        else:
            add("ERROR", "TWSE_STALE",
                f"TWSE 最新日期 {tw} 落後 TPEX {tp} 達 {gap} 個交易日，上市股價資料未更新")

    # 5. 缺價/OHLC（停牌合法，但需數量可見）
    nop = [s["sym"] for s in stocks if s.get("price") is None]
    if nop:
        add("WARNING", "NO_PRICE", f"無收盤價（停牌/無成交）：{len(nop)} 檔，例 {nop[:5]}")

    # 6. 市值為負或 0
    bad_mc = [s["sym"] for s in stocks if _is_num(s.get("market_cap")) and s["market_cap"] <= 0]
    if bad_mc:
        add("ERROR", "MARKET_CAP_NONPOS", f"市值 ≤ 0：{len(bad_mc)} 檔")

    # 7. 美股（單位檢查採「整批中位數」：真實殖利率中位數約 1%、YTD 中位數約 ±10%）
    if us_stocks_doc:
        ust = us_stocks_doc.get("stocks", [])
        if not _units_fixed(us_stocks_doc, "div"):
            divs = [s["div"] for s in ust if _is_num(s.get("div")) and s["div"] > 0]
            if divs and sorted(divs)[len(divs) // 2] > 10:
                add("ERROR", "US_DIV_UNIT",
                    f"美股殖利率中位數 {sorted(divs)[len(divs)//2]}% 異常偏高（疑似單位放大 100 倍）")
        bad_div = [s["sym"] for s in ust if _is_num(s.get("div")) and not (0 <= s["div"] <= US_DIV_MAX_PCT)]
        if bad_div:
            add("ERROR", "US_DIV_RANGE", f"美股殖利率超過 {US_DIV_MAX_PCT}%：{len(bad_div)} 檔")
        bad_pb = [s["sym"] for s in ust if _is_num(s.get("pb")) and not (PB_RANGE[0] <= s["pb"] <= PB_RANGE[1])]
        if bad_pb:
            add("WARNING", "US_PB_RANGE", f"美股淨值比超出 {PB_RANGE}：{bad_pb}")
    if us_etfs_doc:
        ue = us_etfs_doc.get("etfs", [])
        vals = [abs(e["ytd_return"]) for e in ue if _is_num(e.get("ytd_return"))]
        if not _units_fixed(us_etfs_doc, "ytd") and vals and sorted(vals)[len(vals) // 2] > 30:
            add("ERROR", "US_YTD_UNIT",
                f"美股 ETF 年初至今報酬中位數絕對值 {sorted(vals)[len(vals)//2]}% 異常（疑似單位放大 100 倍）")
        no_er = [e["sym"] for e in ue if e.get("expense_ratio") is None]
        if no_er:
            add("WARNING", "US_ETF_NO_EXPENSE", f"美股 ETF 費用率為空：{len(no_er)}/{len(ue)} 檔")
        # 2026-11-13：price 必須是市價。舊版取 navPrice（淨值），導致 16/30 檔與市場收盤
        # 差 >0.5%（最大 3.64%），而 chg 卻用市價算 → 口徑不一致。
        # `nav` 欄位存在時，price 與 nav 完全相同（位元級相等）就是取錯欄位的鐵證。
        nav_eq = [e["sym"] for e in ue
                  if _is_num(e.get("price")) and _is_num(e.get("nav")) and abs(e["price"] - e["nav"]) < 1e-9]
        if nav_eq:
            add("ERROR", "US_ETF_PRICE_IS_NAV",
                f"美股 ETF 的 price 等於淨值（取到 navPrice 而非市價）：{len(nav_eq)} 檔，例 {nav_eq[:5]}")

    # 8. 市值與「收盤 × 已發行股數」不一致（2026-11-13 事故：用 股本÷10 推股數，
    #    對面額非 10 元／無面額的 32 檔算錯，最嚴重差 20 倍）。只在兩邊都有值時判斷。
    mc_bad = []
    for s in stocks:
        if s.get("security_type") != "stock":
            continue
        p, sh, mc = _num_or_none(s.get("price")), _num_or_none(s.get("shares")), _num_or_none(s.get("market_cap"))
        if p and sh and mc:
            exp = p * sh
            if exp > 0 and abs(mc - exp) / exp > 0.01:
                mc_bad.append(s["sym"])
    if mc_bad:
        add("ERROR", "MARKET_CAP_MISMATCH",
            f"市值與 收盤×已發行股數 不符（>1%）：{len(mc_bad)} 檔，例 {mc_bad[:5]}")

    # 9b. 停牌／當日無成交：保留是為了不讓標的無聲消失，但必須可見且不得冒充最新價
    susp = [s["sym"] for s in stocks if s.get("trading_status") == "suspended"]
    if susp:
        add("WARNING", "SUSPENDED_HELD",
            f"停牌／當日無成交，沿用前次紀錄：{len(susp)} 檔，例 {susp[:5]}（保留最後成交日，非最新價）")

    # 9. ETF 成份股總數仍是「只列出前 10 大」（n == 10 且 items 長度 == 10）
    if etf_holdings_doc:
        hold = etf_holdings_doc.get("holdings") or {}
        trunc = [k for k, v in hold.items()
                 if v.get("n") is not None and v.get("n") == 10 and len(v.get("items") or []) == 10]
        if trunc:
            add("WARNING", "ETF_HOLDINGS_TRUNCATED",
                f"ETF 成份股總數仍標成 10（可能被截斷為前 10 大）：{len(trunc)} 檔，例 {trunc[:5]}")
    return issues
