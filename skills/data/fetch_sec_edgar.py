#!/usr/bin/env python3
"""SEC EDGAR Company Facts → data/us/us-edgar.json（美股審計財報層＋品質評分）。

方法承襲 maxgfr/crible（MIT，docs/DATA-SOURCES.md＋src/crible/providers/edgar.py）：
- us-gaap 概念保守映射（窄/經典 tag 先佔；同欄多概念時先佔者保留，filed 較新者勝出）
- 年度事實：fp=FY＋10-K/20-F/40-F＋duration 300-400 天（52/53 週財年）；季度/YTD 不取
- 防呆：股數 <10,000＝申報單位錯誤，丟棄；「不確定的審計數字＝不拿」
- 誠信紅線：缺概念留 null（不補值）；missing_inputs 如實命名；抓失敗保留 last-good
- 評分：Piotroski F（0-9，項目缺則該項不計並標 covered）、Altman Z（任一輸入缺→null）、
  Sloan 應計；EBIT＝PretaxIncome+InterestExpense（crible 口徑，與 OperatingIncome 不混用）
- SEC 公平存取：UA「名稱＋聯絡信箱」且不含 URL（含 URL 會被 Akamai 403）；自限 ~4 req/s

資料來源（公有領域）：https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json
ticker→CIK：https://www.sec.gov/files/company_tickers.json（403 時 fallback defeatbeta 鏡像）

輸出：data/us/us-edgar.json {meta, stocks:[{sym,cik,years,scores,missing_inputs,fetched_at}]}
us-stocks.json（us-market 班地盤）不動，避免撞班。
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

# skills/data/fetch_sec_edgar.py → repo 根（parents[2] 慣例；2026-11-24 #311 修正）
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "us", "us-edgar.json")
US_STOCKS = os.path.join(ROOT, "data", "us", "us-stocks.json")
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
TICKERS_MIRROR = ("https://huggingface.co/datasets/defeatbeta/yahoo-finance-data/resolve/main/"
                  "data/US/company_tickers.json")
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
UA = "Ivan Admin evan.hsia@gmail.com"  # SEC 要求名稱＋信箱；不得含 URL
SLEEP = 0.27  # ~4 req/s（SEC 自限 5 req/s 內）
MIN_PLAUSIBLE_SHARES = 10_000
ANNUAL_FORMS = ("10-K", "20-F", "40-F")
DURATION_DAYS = (300, 400)

# us-gaap 概念 → (欄位, 報表)；窄/經典 tag 在前（先佔制）
CONCEPT_MAP = {
    # 損益（期間）
    "Revenues": ("TotalRevenue", "income"),
    "RevenueFromContractWithCustomerExcludingAssessedTax": ("TotalRevenue", "income"),
    "SalesRevenueNet": ("TotalRevenue", "income"),
    "CostOfRevenue": ("CostOfRevenue", "income"),
    "CostOfGoodsAndServicesSold": ("CostOfRevenue", "income"),
    "GrossProfit": ("GrossProfit", "income"),
    "OperatingIncomeLoss": ("OperatingIncome", "income"),
    "NetIncomeLoss": ("NetIncome", "income"),
    "NetIncomeLossAvailableToCommonStockholdersBasic": ("NetIncome", "income"),
    "ProfitLoss": ("NetIncome", "income"),
    "IncomeTaxExpenseBenefit": ("TaxProvision", "income"),
    "InterestExpense": ("InterestExpense", "income"),
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": ("PretaxIncome", "income"),
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments": ("PretaxIncome", "income"),
    "WeightedAverageNumberOfSharesOutstandingBasic": ("BasicAverageShares", "income"),
    # 資產負債（時點）
    "Assets": ("TotalAssets", "balance"),
    "AssetsCurrent": ("CurrentAssets", "balance"),
    "Liabilities": ("TotalLiabilities", "balance"),
    "LiabilitiesCurrent": ("CurrentLiabilities", "balance"),
    "StockholdersEquity": ("StockholdersEquity", "balance"),
    "CommonStockSharesOutstanding": ("OrdinarySharesNumber", "balance"),
    "RetainedEarningsAccumulatedDeficit": ("RetainedEarnings", "balance"),
    "InventoryNet": ("Inventory", "balance"),
    "AccountsReceivableNetCurrent": ("AccountsReceivable", "balance"),
    "AccountsPayableCurrent": ("AccountsPayable", "balance"),
    "CashAndCashEquivalentsAtCarryingValue": ("CashAndCashEquivalents", "balance"),
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents": ("CashAndCashEquivalents", "balance"),
    "PropertyPlantAndEquipmentNet": ("NetPPE", "balance"),
    "LongTermDebtNoncurrent": ("LongTermDebt", "balance"),
    "LongTermDebtAndCapitalLeaseObligations": ("LongTermDebt", "balance"),
    "DebtCurrent": ("CurrentDebt", "balance"),
    "Goodwill": ("Goodwill", "balance"),
    # 現金流（期間）
    "NetCashProvidedByUsedInOperatingActivities": ("OperatingCashFlow", "cashflow"),
    "PaymentsToAcquirePropertyPlantAndEquipment": ("CapitalExpenditure", "cashflow"),
    "PaymentsToAcquireProductiveAssets": ("CapitalExpenditure", "cashflow"),
    "DepreciationDepletionAndAmortization": ("DepreciationAndAmortization", "cashflow"),
    "DepreciationAndAmortization": ("DepreciationAndAmortization", "cashflow"),
    "PaymentsOfDividendsCommonStock": ("CashDividendsPaid", "cashflow"),
    "PaymentsOfDividends": ("CashDividendsPaid", "cashflow"),
    "ProceedsFromIssuanceOfCommonStock": ("CommonStockIssuance", "cashflow"),
}
SHARE_COLS = {"BasicAverageShares", "OrdinarySharesNumber"}


def http_json(url, timeout=30, retries=3):
    """SEC 抓取＋退避重試（429/5xx/暫態網路）。"""
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            code = getattr(e, "code", 0)
            if code not in (0, 403, 429, 500, 502, 503, 504) and not isinstance(e, (TimeoutError, json.JSONDecodeError)):
                raise
            time.sleep(1.5 * (i + 1))
    raise last if last is not None else RuntimeError(f"SEC 抓取失敗: {url}")


MIN_GAAP_CONCEPTS = 150  # 正常 companyfacts ≥434（JPM 918）；縮減快取回應 ~98（2026-11-24 實測 XOM）


def fetch_companyfacts(cik):
    """抓 companyfacts＋健全性檢查：連續抓取時 SEC 邊緣節點偶發回傳縮減快取
    （HTTP 200 但 us-gaap 概念數極少），退避重抓；4 次仍縮減則原樣回（parse 空→missing 如實）。"""
    j = {}
    for i in range(4):
        j = http_json(FACTS_URL.format(cik=cik))
        gaap = (j.get("facts") or {}).get("us-gaap") or {}
        if len(gaap) >= MIN_GAAP_CONCEPTS:
            return j
        print(f"    ⚠️ 縮減回應（us-gaap {len(gaap)} 概念 <{MIN_GAAP_CONCEPTS}），退避重抓…")
        time.sleep(2 * (i + 1))
    # 30 秒冷卻後重抓一次（跨 SEC 限流窗口；班序連抓後的頑固縮減實測 2026-11-24 XOM）
    print("    ↳ 30 秒冷卻後重抓…")
    time.sleep(30)
    j = http_json(FACTS_URL.format(cik=cik))
    if len((j.get("facts") or {}).get("us-gaap") or {}) >= MIN_GAAP_CONCEPTS:
        return j
    return fetch_companyconcepts(cik)


def fetch_companyconcepts(cik):
    """縮減快取降級層：逐概念 companyconcept API（小檔，不觸發大檔快取污染）。
    回應結構與 companyfacts 相容（parse_companyfacts 只讀 us-gaap[concept].units）。"""
    print("    ↳ 降級：逐概念 companyconcept 抓取")
    out = {"facts": {"us-gaap": {}}}
    for concept in CONCEPT_MAP:
        try:
            j = http_json(f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{concept}.json")
            if j.get("units"):
                out["facts"]["us-gaap"][concept] = {"units": j["units"]}
        except Exception:
            pass  # 無此概念的公司常態 404
        time.sleep(0.15)
    return out


def get_tickers():
    """{TICKER: cik}。SEC 目錄 403 → defeatbeta 鏡像。"""
    try:
        payload = http_json(TICKERS_URL)
    except urllib.error.HTTPError as e:
        if e.code != 403:
            raise
        print("  SEC 目錄 403 → defeatbeta 鏡像 fallback")
        payload = http_json(TICKERS_MIRROR)
    return {str(e["ticker"]).strip().upper(): int(e["cik_str"])
            for e in payload.values() if e.get("ticker") and e.get("cik_str")}


def _duration_days(f):
    try:
        from datetime import date
        return (date.fromisoformat(f["end"]) - date.fromisoformat(f["start"])).days
    except Exception:
        return 0


def parse_companyfacts(cf, max_years=8):
    """companyfacts → {end_date: {欄位: 值}}（年度審計事實）。

    規則：fp=FY＋annual forms＋300-400 天 duration；同 (period, 欄) 先到概念先佔、
    filed 較新勝出；股數 <10,000 丟棄；僅取近 max_years 個年度。
    """
    gaap = (cf.get("facts") or {}).get("us-gaap") or {}
    claims, sink = {}, {}
    for concept, (col, _stmt) in CONCEPT_MAP.items():
        node = gaap.get(concept)
        if not node:
            continue
        units = node.get("units") or {}
        vals = next(iter(units.values())) if units else []
        for f in vals:
            if f.get("fp") != "FY" or f.get("form") not in ANNUAL_FORMS:
                continue
            if f.get("start"):
                # duration 事實（損益/現金流）：限全年（52/53 週）
                d = _duration_days(f)
                if not (DURATION_DAYS[0] <= d <= DURATION_DAYS[1]):
                    continue
            # instant 事實（資產負債表，無 start）：無 duration 可檢，10-K FY 即收
            period, val = f["end"], f.get("val")
            if val is None or (col in SHARE_COLS and abs(val) < MIN_PLAUSIBLE_SHARES):
                continue
            if claims.get((period, col)) not in (None, concept):
                continue  # 窄 tag 已供此欄
            cur = sink.setdefault(period, {}).get(col)
            if cur is None or str(f.get("filed", "")) >= cur[0]:
                sink[period][col] = (str(f.get("filed", "")), val)
                claims[(period, col)] = concept
    out = {}
    for period in sorted(sink)[-max_years:]:
        out[period] = {col: v for col, (_f, v) in sink[period].items()}
    return out


def compute_scores(years, price):
    """→ scores, missing_inputs（crible 公式；缺輸入→不計並如實命名，null 不補）。"""
    periods = sorted(years)
    if not periods:
        return {}, ["全部年度事實缺失"]
    t = periods[-1]
    tp = periods[-2] if len(periods) >= 2 else None
    missing = []
    y, yp = years[t], (years.get(tp) or {}) if tp else {}

    def need(col, src=y):
        if src.get(col) is None:
            missing.append(f"{t}.{col}" if src is y else f"{tp}.{col}")
        return src.get(col)

    scores = {}

    # ── Piotroski F（9 項；缺輸入的項不計，covered 如實標記） ──
    ta, tap = need("TotalAssets"), yp.get("TotalAssets")
    ni, nip = need("NetIncome"), yp.get("NetIncome")
    ocf = need("OperatingCashFlow")
    liab, liabp = need("TotalLiabilities"), yp.get("TotalLiabilities")
    cl, clp = need("CurrentLiabilities"), yp.get("CurrentLiabilities")
    ca, cap_ = need("CurrentAssets"), yp.get("CurrentAssets")
    gp, gpp = need("GrossProfit"), yp.get("GrossProfit")
    rev, revp = need("TotalRevenue"), yp.get("TotalRevenue")
    shares, sharesp = need("OrdinarySharesNumber"), yp.get("OrdinarySharesNumber")
    if not shares:
        # 期間加權股數（EPS 分母）作 period-end 股數的降級來源——兩者皆無才記缺
        shares = need("BasicAverageShares")
        if shares:
            missing = [m for m in missing if not m.endswith(".OrdinarySharesNumber")]
    if tp is None:
        missing.append("前一年度事實缺失（首年無法計算變化項）")

    roa_t = ni / ta if (ta and ni is not None) else None
    roa_p = nip / tap if (tap and nip is not None) else None
    p = {}
    p["ROA>0"] = flag = None  # 依序覆寫；flag 佔位避免 flake 誤解
    p["ROA>0"] = (1 if roa_t is not None and roa_t > 0 else 0) if roa_t is not None else None
    p["CFO>0"] = (1 if ocf is not None and ocf > 0 else 0) if ocf is not None else None
    p["ΔROA>0"] = ((1 if roa_t > roa_p else 0)
                   if (roa_t is not None and roa_p is not None) else None)
    p["CFO>NI"] = ((1 if ocf > ni else 0)
                   if (ocf is not None and ni is not None) else None)
    p["Δ槓桿降"] = ((1 if liab / ta < liabp / tap else 0)
                  if all(v is not None for v in (liab, ta, liabp)) and ta and tap else None)
    p["Δ流動比升"] = ((1 if ca / cl > cap_ / clp else 0)
                   if all(v not in (None, 0) for v in (ca, cl, cap_, clp)) else None)
    p["Δ毛利率升"] = ((1 if gp / rev > gpp / revp else 0)
                   if all(v is not None for v in (gp, gpp, rev, revp)) and rev and revp else None)
    p["Δ週轉升"] = ((1 if rev / ta > revp / tap else 0)
                 if all(v is not None for v in (rev, revp, ta, tap)) and ta and tap else None)
    p["股數未增"] = ((1 if shares <= sharesp else 0)
                 if (shares is not None and sharesp is not None) else None)
    got = [v for v in p.values() if v is not None]
    if got and tp:
        scores["piotroski_f"] = sum(got)
        scores["piotroski_detail"] = p
        scores["piotroski_covered"] = f"{len(got)}/9"
    else:
        missing.append("piotroski（無前年對照或任一項都缺輸入）")

    # ── Altman Z（製造業版；任一輸入缺→整體 null，crible 同規） ──
    pretax = need("PretaxIncome")
    iexp = need("InterestExpense")
    re_ = need("RetainedEarnings")
    opinc = y.get("OperatingIncome")
    # EBIT 口徑：主＝PretaxIncome+InterestExpense（crible）；缺任一→降級 OperatingIncome（Altman
    # 原始模型即營業利益口徑），降級如實標記；兩者皆缺→null
    ebit = ebit_src = None
    if pretax is not None and iexp is not None:
        ebit, ebit_src = pretax + iexp, "pretax+interest"
    elif opinc is not None:
        ebit, ebit_src = opinc, "operating_income(降級：缺 InterestExpense 或 PretaxIncome)"
    scores["ebit"] = ebit
    if ebit_src:
        scores["ebit_source"] = ebit_src
    z_ok = all(v is not None and v != 0 for v in (ta, liab)) and \
        all(v is not None for v in (re_, ebit, rev, ca, cl, shares, price))
    if z_ok:
        wc = ca - cl
        mve = price * shares
        scores["altman_z"] = round(1.2 * wc / ta + 1.4 * re_ / ta + 3.3 * ebit / ta
                                   + 0.6 * mve / liab + 1.0 * rev / ta, 4)
    else:
        missing.append("altman_z（輸入不全）")

    # ── Sloan 應計 ──
    if ocf is not None and ni is not None and ta and tap:
        scores["sloan_accruals"] = round((ni - ocf) / ((ta + tap) / 2), 6)
    else:
        missing.append("sloan_accruals（缺 ocf/ni/ta 或前年 ta）")

    return scores, missing


def main():
    dry = "--dry-run" in sys.argv
    if not os.path.exists(US_STOCKS):
        print(f"⚠️ {US_STOCKS} 不存在，SEC EDGAR 跳過（缺清單不擋 job）")
        return 0
    us = json.load(open(US_STOCKS, encoding="utf-8"))
    prices = {r["sym"]: r.get("price") for r in (us.get("stocks") or [])}
    syms = list(prices)
    if not syms:
        print("⚠️ us-stocks.json 無清單，SEC EDGAR 跳過")
        return 0

    old = {}
    if os.path.exists(OUT):
        try:
            old = {s["sym"]: s for s in json.load(open(OUT, encoding="utf-8")).get("stocks", [])}
        except Exception:
            old = {}

    tickers = get_tickers()
    out_rows, fail = [], []
    for sym in syms:
        cik = tickers.get(sym.upper())
        if not cik:
            fail.append(sym)
            print(f"  {sym} ❌ CIK 未對照（保留 last-good）")
            if sym in old:
                out_rows.append(old[sym])
            continue
        try:
            cf = fetch_companyfacts(cik)
            years = parse_companyfacts(cf)
            price = prices.get(sym)
            scores, missing = compute_scores(years, price)
            out_rows.append({
                "sym": sym, "cik": cik, "years": years, "scores": scores,
                "missing_inputs": missing, "src": "SEC_EDGAR",
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            })
            p = scores.get("piotroski_f")
            z = scores.get("altman_z")
            print(f"  {sym} ✅ {len(years)} 個年度，Piotroski={p}（{scores.get('piotroski_covered')}）"
                  f"，Altman Z={z if z is not None else 'null'}，missing={len(missing)}")
        except Exception as ex:
            fail.append(sym)
            print(f"  {sym} ⚠️ {type(ex).__name__}: {str(ex)[:60]}（保留 last-good）")
            if sym in old:
                out_rows.append(old[sym])
        time.sleep(SLEEP)

    print(f"\n[sec-edgar] 成功 {len(syms) - len(fail)}/{len(syms)}，fail={fail or '無'}")
    if dry:
        print("[sec-edgar] --dry-run：未寫入")
        return 0
    if not out_rows:
        print("[sec-edgar] 全部失敗——不覆寫既有檔案")
        return 0
    doc = {
        "meta": {
            "src": "SEC_EDGAR", "asof": time.strftime("%Y-%m-%d"),
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "note": ("美股審計財報層（SEC companyfacts，公有領域）。年度＝10-K/20-F/40-F FY 全年事實；"
                     "EBIT=PretaxIncome+InterestExpense（crible 口徑）；股數<10,000 丟棄；"
                     "缺值留 null 不補值；Altman Z 對金融業（JPM/BAC 等）解讀需保留；"
                     "抓失敗保留 last-good。方法承襲 maxgfr/crible（MIT）。"),
        },
        "stocks": sorted(out_rows, key=lambda s: s["sym"]),
    }
    body = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(body)
    os.replace(tmp, OUT)
    print(f"[sec-edgar] ✅ 已寫入 {OUT}（{len(body)/1024:.0f} KB，{len(out_rows)} 檔）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
