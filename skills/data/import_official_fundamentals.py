#!/usr/bin/env python3
"""
TWSE 官方財報／股利／基金資料匯入（手動匯入：放入 data/raw/official/ 後執行）。

來源檔案（皆為 TWSE OpenAPI 下載）：
  t187ap06_L_*.csv     綜合損益表（上市公司，累計期間）→ EPS、本期淨利、營業收入
  t187ap07_L_*.csv     資產負債表（上市公司）          → 資產總計、歸屬母公司權益
                       （檔名由 fetch_official_fundamentals.py 產生，固定為 *_latest.csv；
                         MOPS 只提供「當日出表」的增量批次，該程式會與既有快照 upsert 合併後才寫入）
  t187ap45_*.json      上市公司股利分派情形            → 現金股利、連續配息年數
  t187ap47_*.json      基金基本資料彙總表（ETF）       → 上市日期、基金類型、保管機構…

計算方式（重要假設，請確認）：
  - 損益與資產負債表為「累計至該季」的數字（台灣 IFRS 財報慣例）。
    年化係數「逐列」依該列自己的年度/季別計算：Q1×4、Q2×2、Q3×(12/9)、Q4×1。
    ⚠️ 不可只用第一列的季別算一個係數：官方檔案是「當日出表」的增量批次，
    與既有快照合併後可能同時含不同季別（2026-11-03 實測 999 家 Q2 ＋ 53 家 Q3），
    用單一係數會把 Q3（累計 9 個月）當 Q2 年化而高估 50%。
  - ROE = 歸屬母公司淨利(累計) × 年化 ÷ 歸屬母公司權益合計
  - ROA = 本期淨利(累計) × 年化 ÷ 資產總計
  - EPS(年化) = 基本每股盈餘(累計) × 年化
  - 季節性：上半年獲利未必平均，年化值會偏離全年，屬於估算。
  - 營收年增率：本檔只有一期，無法計算；需要 t187ap05_L（月營收）或前一年同期財報。

寫入：
  data/official-fundamentals.json  每家公司的計算結果與來源資訊
  data/etf-official.json           ETF 基本資料（上市日期、保管機構…）
  data/stocks.json                 補上 roe_off / roa_off / eps_off / gross_margin / net_margin /
                                   debt_ratio / 股利欄位與 fund_src（只留前端與測試真的會讀的欄位；
                                   operating_margin 等仍完整存在本 JSON 的 financial 區塊）
"""
import csv
import datetime as dt
import glob
import json
import os
import sys
# 站內資料範圍的唯一來源（同目錄）。自帶 os/sys 並動態加路徑，這樣不論是
# `python3 skills/data/xxx.py` 直跑、由其他程式 import、或從別的 cwd 執行，都找得到。
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import scope_rules  # noqa: E402
import data_rules  # noqa: E402  （2026-11-14：PE 口徑統一與 eps_src 標記）

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "data", "raw", "official")
DATA = os.path.join(ROOT, "data")
TZ = dt.timezone(dt.timedelta(hours=8))


def _log(m):
    print(f"[import_official] {m}", flush=True)


def roc_to_iso(s):
    """民國日期 1151030 / 1140101 → 2026-10-30 / 2025-01-01；無法解析回傳 None。"""
    s = str(s or "").strip()
    if len(s) == 7 and s.isdigit():
        return f"{int(s[:3]) + 1911}-{s[3:5]}-{s[5:7]}"
    if len(s) == 6 and s.isdigit():
        return f"{int(s[:2]) + 1911}-{s[2:4]}-{s[4:6]}"
    return None


def num(v):
    try:
        s = str(v).strip().replace(",", "")
        return float(s) if s not in ("", "-") else None
    except ValueError:
        return None


def find_col(header, exact=None, contains=None, not_contains=()):
    """以欄位名稱找索引；exact 優先，其次 contains。找不到拋出錯誤（避免靜默錯欄）。"""
    if exact:
        for i, h in enumerate(header):
            if h.strip() == exact:
                return i
        raise KeyError(f"找不到欄位：{exact}")
    for i, h in enumerate(header):
        h = h.strip()
        if contains and contains in h and not any(n in h for n in not_contains):
            return i
    raise KeyError(f"找不到欄位（含 {contains!r}）")


def read_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


def import_income_balance(stamp_info):
    inc_path = glob.glob(os.path.join(SRC, "t187ap06_L*.csv"))
    bal_path = glob.glob(os.path.join(SRC, "t187ap07_L*.csv"))
    if not inc_path or not bal_path:
        _log("缺少 t187ap06 或 t187ap07 CSV，略過損益/資產負債表")
        return {}, None
    ih, irows = read_csv(inc_path[0])
    bh, brows = read_csv(bal_path[0])

    c_sym_i = find_col(ih, exact="公司代號")
    c_year_i = find_col(ih, exact="年度")
    c_q_i = find_col(ih, exact="季別")
    c_date_i = find_col(ih, exact="出表日期")
    c_rev = find_col(ih, exact="營業收入")
    c_ni_total = find_col(ih, exact="本期淨利（淨損）")
    c_ni_parent = find_col(ih, exact="淨利（淨損）歸屬於母公司業主")
    c_eps = find_col(ih, contains="基本每股盈餘")

    def _opt(h, **kw):
        """選用欄位查詢：找不到要回 None。

        不可直接寫 `find_col(...) or find_col(...)` —— find_col 找不到時是 **raise
        KeyError**，`or` 的備援永遠跑不到，整支腳本會爆掉。金融保險業（銀行/保險）的
        損益表本來就沒有「營業毛利」，所以這幾欄必須是可選的。
        """
        try:
            return find_col(h, **kw)
        except KeyError:
            return None

    # 2026-11-09：三率（毛利率／淨利率／營業利益率）與負債比。
    # 金融保險業沒有「營業毛利」（銀行/保險的收入結構不同）→ 該欄自然為 null，不補值。
    c_gp = _opt(ih, exact="營業毛利（毛損）淨額") or _opt(ih, exact="營業毛利（毛損）")
    c_op = _opt(ih, exact="營業利益（損失）")

    c_sym_b = find_col(bh, exact="公司代號")
    c_assets = find_col(bh, exact="資產總計")
    c_eq_parent = find_col(bh, exact="歸屬於母公司業主之權益合計")
    c_liab = _opt(bh, exact="負債總計")

    bal = {r[c_sym_b].strip(): r for r in brows if r and r[c_sym_b].strip()}
    MONTHS = {"1": 3, "2": 6, "3": 9, "4": 12}
    out, periods, skipped = {}, {}, 0
    for r in irows:
        sym = r[c_sym_i].strip()
        if not sym:
            continue
        y, q = r[c_year_i].strip(), r[c_q_i].strip()
        months = MONTHS.get(q)
        if not months:
            skipped += 1
            continue
        factor = 12 / months
        try:
            period = f"{int(y) + 1911}Q{q}"
        except ValueError:
            period = f"{y}Q{q}"
        asof = roc_to_iso(r[c_date_i].strip())
        periods[period] = periods.get(period, 0) + 1
        ni_p, ni_t = num(r[c_ni_parent]), num(r[c_ni_total])
        eps_ytd = num(r[c_eps])
        b = bal.get(sym)
        eq_p = num(b[c_eq_parent]) if b else None
        assets = num(b[c_assets]) if b else None
        liab = num(b[c_liab]) if b and c_liab is not None else None
        rev = num(r[c_rev])
        gp = num(r[c_gp]) if c_gp is not None else None
        op = num(r[c_op]) if c_op is not None else None
        # 比率型指標用「累計期間」本身即可，不需年化（年化只影響 ROE/ROA/EPS 這種規模量）。
        # 分母為 0 或 None 一律回 None —— 不以 0 冒充。
        def ratio(numer):
            return round(numer / rev * 100, 2) if numer is not None and rev else None
        rec = {
            "period": period,
            "asof": asof,
            "annualize_factor": factor,
            "revenue_ytd_thousand": rev,
            "gross_profit_ytd_thousand": gp,
            "operating_income_ytd_thousand": op,
            "liabilities_total_thousand": liab,
            "gross_margin_pct": ratio(gp),
            "operating_margin_pct": ratio(op),
            "net_margin_pct": ratio(ni_t),
            "debt_ratio_pct": round(liab / assets * 100, 2) if liab is not None and assets else None,
            "ni_total_ytd_thousand": ni_t,
            "ni_parent_ytd_thousand": ni_p,
            "eps_ytd": eps_ytd,
            "eps_annualized": round(eps_ytd * factor, 2) if eps_ytd is not None else None,
            "equity_parent_thousand": eq_p,
            "assets_total_thousand": assets,
            "roe_annualized_pct": round(ni_p * factor / eq_p * 100, 2) if ni_p is not None and eq_p else None,
            "roa_annualized_pct": round(ni_t * factor / assets * 100, 2) if ni_t is not None and assets else None,
        }
        out[sym] = rec
    if not out:
        raise ValueError("沒有任何一列能判斷季別，無法年化")
    asofs = {rec["asof"] for rec in out.values() if rec["asof"]}
    mix = "＋".join(f"{p} {n} 家" for p, n in sorted(periods.items(), key=lambda kv: -kv[1]))
    _log(f"損益/資產負債表：{mix}（逐列依各自季別年化），公司 {len(out)} 家"
         + (f"，略過無法判斷季別 {skipped} 列" if skipped else ""))
    return out, {"period": max(periods, key=lambda k: periods[k]), "periods": periods,
                 "asof": max(asofs) if asofs else None,
                 "files": [os.path.basename(inc_path[0]), os.path.basename(bal_path[0])]}


def import_dividends():
    paths = glob.glob(os.path.join(SRC, "t187ap45*.json"))
    if not paths:
        _log("缺少 t187ap45 JSON，略過股利")
        return {}
    data = json.load(open(paths[0], encoding="utf-8"))
    if not data:
        return {}
    k = list(data[0].keys())
    c_sym = find_col(k, exact="公司代號")
    c_year = find_col(k, exact="股利年度")
    c_scope = find_col(k, exact="股利所屬年(季)度")
    c_cash_earn = find_col(k, contains="盈餘分配之現金股利")
    c_cash_legal = find_col(k, contains="法定盈餘公積發放之現金")
    c_cash_cap = find_col(k, contains="資本公積發放之現金")

    # 每家公司、每個股利年度：若有「年度」列用它，否則加總所有期別
    per = {}
    for r in data:
        sym = str(r.get(k[c_sym], "")).strip()
        year = str(r.get(k[c_year], "")).strip()
        if not sym or not year:
            continue
        # 範圍過濾（治本）：官方股利檔 t187ap45 同時包含特別股（2881A/B/C、2887E…）與 ETN，
        # 本站不收。沒有這道過濾，每次 CI 都會把這些死鍵種回 official-fundamentals.json。
        if not scope_rules.in_scope(sym):
            continue
        cash = sum(x or 0 for x in [num(r.get(k[c_cash_earn])), num(r.get(k[c_cash_legal])), num(r.get(k[c_cash_cap]))])
        scope = str(r.get(k[c_scope], "")).strip()
        d = per.setdefault(sym, {}).setdefault(year, {"annual": None, "sum": 0.0})
        if scope == "年度":
            d["annual"] = cash
        d["sum"] += cash

    out = {}
    for sym, years in per.items():
        totals = {y: (v["annual"] if v["annual"] is not None else v["sum"]) for y, v in years.items()}
        latest = max(totals.keys(), key=lambda y: int(y))
        # 連續配息年數：從最新年度往前，連續 > 0 的年數（僅計算檔案內有的年度）
        streak, y = 0, int(latest)
        while str(y) in totals and totals[str(y)] > 0:
            streak += 1
            y -= 1
        out[sym] = {
            "by_year_cash_per_share": {y: round(t, 4) for y, t in sorted(totals.items())},
            "latest_year": latest,
            "latest_cash_per_share": round(totals[latest], 4),
            "streak_years": streak,
            "years_available": sorted(totals.keys(), key=lambda y: int(y)),
        }
    _log(f"股利：{len(out)} 家公司，股利年度 {sorted({y for v in per.values() for y in v}, key=int)}")
    return out


def import_etf_basic(stamp_info):
    paths = glob.glob(os.path.join(SRC, "t187ap47*.json"))
    if not paths:
        return {}
    data = json.load(open(paths[0], encoding="utf-8"))
    def g(r, name):
        return str(r.get(name, "") or "").strip()
    out = {}
    for r in data:
        sym = g(r, "基金代號")
        if not sym:
            continue
        out[sym] = {
            "name": g(r, "基金簡稱"),
            "fund_type": g(r, "基金類型"),
            "full_name": g(r, "基金中文名稱"),
            "tracking_index": g(r, "標的指數/追蹤指數名稱"),
            "listing_date": roc_to_iso(g(r, "上市日期")),
            "establish_date": roc_to_iso(g(r, "成立日期")),
            "manager": g(r, "基金經理人"),
            "custodian": g(r, "保管機構"),
            "units_issued": g(r, "發行單位數/轉換數"),
        }
    _log(f"ETF 基本資料：{len(out)} 檔")
    return out


def main():
    if not os.path.isdir(SRC):
        _log(f"找不到 {SRC}，請先放入官方檔案")
        sys.exit(1)
    now = dt.datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
    mtimes = {os.path.basename(p): dt.datetime.fromtimestamp(os.path.getmtime(p), TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
              for p in glob.glob(os.path.join(SRC, "*"))}

    fin, fin_info = import_income_balance(None)
    div = import_dividends()
    etf = import_etf_basic(None)

    src_meta = {
        "source": "TWSE OpenAPI／MOPS opendata 官方檔案（由 fetch_official_fundamentals.py 下載）",
        "files": mtimes,
        "imported_at": now,
        "financial_period": fin_info["period"] if fin_info else None,
        "financial_periods": fin_info.get("periods") if fin_info else None,
        "financial_asof_roc_date": fin_info["asof"] if fin_info else None,
        "method": ("損益/資產負債表為累計數，年化係數逐列依各自季別計算（Q1×4、Q2×2、Q3×4/3、Q4×1）；"
                   "同一份快照可能同時含不同季別（MOPS 增量批次與既有快照合併所致）；營收年增率需月營收檔，尚未提供；"
                   "gross_margin_pct=營業毛利淨額/營業收入、operating_margin_pct=營業利益/營業收入、"
                   "net_margin_pct=本期淨利/營業收入、debt_ratio_pct=負債總計/資產總計，皆為累計期間比率（不年化）；"
                   "缺欄位一律 null，不以 0 冒充"),
    }

    with open(os.path.join(DATA, "official-fundamentals.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": src_meta, "financial": fin, "dividend": div}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(DATA, "etf-official.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": src_meta, "etfs": etf}, f, ensure_ascii=False, indent=2)

    # 合併進 stocks.json（只更新有官方資料的股票；其餘保持原樣）
    sp = os.path.join(DATA, "stocks.json")
    doc = json.load(open(sp, encoding="utf-8"))
    n = 0
    for row in doc["stocks"]:
        sym = row.get("sym")
        f_ = fin.get(sym)
        d_ = div.get(sym)
        if f_:
            row["roe_off"] = f_["roe_annualized_pct"]
            row["roa_off"] = f_["roa_annualized_pct"]
            row["eps_off"] = f_["eps_annualized"]
            row["fund_src"] = "TWSE_OFFICIAL"
            # 三率與負債比（2026-11-09）：與 roe_off/eps_off 同一份官方財報、同一累計期間。
            # 缺值一律 null（金融保險業沒有「營業毛利」、ETF 沒有財報）→ 前端顯示「-」，
            # 不以 0 或任何推測值冒充。
            row["gross_margin"] = f_.get("gross_margin_pct")
            row["net_margin"] = f_.get("net_margin_pct")
            row["debt_ratio"] = f_.get("debt_ratio_pct")
            n += 1
        # roe / roa / eps 與官方年化值同步（單一口徑）。
        # 歷史包袱：舊版從 TWSE t187ap06_L 取 ROE/ROA/EPS，該端點已失效且欄位已改名，這三欄之後從未更新，
        # 殘留的是過期、口徑不明的舊值（例：2330 的 roe 31.7 vs 官方年化 39.77）。
        # 規則：有官方值 → 一律用官方；沒有官方值 → 只保留 yfinance 週更補的 ROE/ROA（roe_src 有標註），
        # 其餘（過期殘值、EPS）清成 null，顯示「-」，不拿舊值冒充。
        if row.get("security_type") == "stock":
            if row.get("roe_off") is not None:
                row["roe"], row["roa"] = row["roe_off"], row.get("roa_off")
                row.pop("roe_src", None)
            elif row.get("roe_src") != "yfinance":
                row["roe"] = row["roa"] = None
            if row.get("eps_off") is not None:
                row["eps"] = row["eps_off"]
                row["eps_src"] = "TWSE_OFFICIAL"
            elif row.get("eps_src") != "TWSE_PE_IMPLIED":
                # 沒有官方損益表（金融保險類）：只保留「由官方 PE 反推」的值，
                # 該值由 fetch_data.py daily 每天依最新 PE 重算；其餘（過期殘值）清成 null。
                row["eps"] = None
                row.pop("eps_src", None)
            # eps 定案後重算 pe（單一口徑：pe = 收盤 ÷ EPS；無 EPS 才退回官方公告值）
            data_rules.apply_pe_from_eps(row)
        if d_:
            row["div_cash_latest"] = d_["latest_cash_per_share"]
            row["div_streak_years"] = d_["streak_years"]
            row["div_years_available"] = d_["years_available"]
    doc["meta"]["fundamentals"] = src_meta
    json.dump(doc, open(sp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    _log(f"stocks.json 已更新官方財報欄位：{n} 檔（其餘保持原值）")


if __name__ == "__main__":
    main()
