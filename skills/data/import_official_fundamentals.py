#!/usr/bin/env python3
"""
TWSE 官方財報／股利／基金資料匯入（手動匯入：放入 data/raw/official/ 後執行）。

來源檔案（皆為 TWSE OpenAPI 下載）：
  t187ap06_L_ci2.csv   綜合損益表（上市公司，累計期間）→ EPS、本期淨利、營業收入
  t187ap07_L_ci.csv    資產負債表（上市公司）          → 資產總計、歸屬母公司權益
  t187ap45_*.json      上市公司股利分派情形            → 現金股利、連續配息年數
  t187ap47_*.json      基金基本資料彙總表（ETF）       → 上市日期、基金類型、保管機構…

計算方式（重要假設，請確認）：
  - 損益與資產負債表為「累計至該季」的數字（台灣 IFRS 財報慣例）。
    本檔為 115 年第 2 季（累計 6 個月），年化係數 = 12 ÷ 6 = 2。
  - ROE = 歸屬母公司淨利(累計) × 年化 ÷ 歸屬母公司權益合計
  - ROA = 本期淨利(累計) × 年化 ÷ 資產總計
  - EPS(年化) = 基本每股盈餘(累計) × 年化
  - 季節性：上半年獲利未必平均，年化值會偏離全年，屬於估算。
  - 營收年增率：本檔只有一期，無法計算；需要 t187ap05_L（月營收）或前一年同期財報。

寫入：
  data/official-fundamentals.json  每家公司的計算結果與來源資訊
  data/etf-official.json           ETF 基本資料（上市日期、保管機構…）
  data/stocks.json                 補上 roe_off / roa_off / eps_off / 股利欄位與 fund_* 來源欄位
"""
import csv
import datetime as dt
import glob
import json
import os
import sys

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

    c_sym_b = find_col(bh, exact="公司代號")
    c_assets = find_col(bh, exact="資產總計")
    c_eq_parent = find_col(bh, exact="歸屬於母公司業主之權益合計")

    bal = {r[c_sym_b].strip(): r for r in brows if r and r[c_sym_b].strip()}
    year = irows[0][c_year_i].strip() if irows else None
    qtr = irows[0][c_q_i].strip() if irows else None
    months = {"1": 3, "2": 6, "3": 9, "4": 12}.get(qtr)
    if not months:
        raise ValueError(f"無法判斷季別：{qtr}")
    factor = 12 / months
    asof = roc_to_iso(irows[0][c_date_i].strip())
    period = f"{int(year) + 1911}Q{qtr}"

    out = {}
    for r in irows:
        sym = r[c_sym_i].strip()
        if not sym:
            continue
        ni_p, ni_t = num(r[c_ni_parent]), num(r[c_ni_total])
        eps_ytd = num(r[c_eps])
        b = bal.get(sym)
        eq_p = num(b[c_eq_parent]) if b else None
        assets = num(b[c_assets]) if b else None
        rec = {
            "period": period,
            "asof": asof,
            "annualize_factor": factor,
            "revenue_ytd_thousand": num(r[c_rev]),
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
    _log(f"損益/資產負債表：{period}（出表 {asof}），公司 {len(out)} 家")
    return out, {"period": period, "asof": asof, "files": [os.path.basename(inc_path[0]), os.path.basename(bal_path[0])]}


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
    k = list(data[0].keys()) if data else []
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
        "source": "TWSE OpenAPI 官方檔案（使用者下載放入 data/raw/official/）",
        "files": mtimes,
        "imported_at": now,
        "financial_period": fin_info["period"] if fin_info else None,
        "financial_asof_roc_date": fin_info["asof"] if fin_info else None,
        "method": "損益/資產負債表為累計數，依季別年化（Q2×2）；營收年增率需月營收檔，尚未提供",
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
            row["fund_period"] = f_["period"]
            row["fund_asof"] = f_["asof"]
            row["fund_src"] = "TWSE_OFFICIAL"
            n += 1
        if d_:
            row["div_cash_latest"] = d_["latest_cash_per_share"]
            row["div_latest_year"] = d_["latest_year"]
            row["div_streak_years"] = d_["streak_years"]
            row["div_years_available"] = d_["years_available"]
    doc["meta"]["fundamentals"] = src_meta
    json.dump(doc, open(sp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    _log(f"stocks.json 已更新官方財報欄位：{n} 檔（其餘保持原值）")


if __name__ == "__main__":
    main()
