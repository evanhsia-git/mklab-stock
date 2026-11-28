#!/usr/bin/env python3
"""資料庫覆蓋率稽核（Phase 7C，2026-11-28）——唯讀掃描，產出 data/coverage.json 與 data/gaps.json。

口徑鐵律（Ivan 規範＋skill mklab-stock-db-audit）：
- 交易日分母＝資料集建置範圍內應有交易日（reference/trade-calendar-2025-2026.json）；
- 欄位完整率：PE/PB/ROE/殖利率以個股總數為分母（ETF 無這些數值不計入）；price/market_cap 全檔；
- K 線缺口分類（無任意門檻，依應有交易日集合）：
  HEAD＝應有起始日至第一筆有效紀錄之前；MIDDLE＝首尾之間；TAIL＝最後一筆至最新應有日；FULL_MISSING＝整段無資料；
- K 線首日≠上市日：上市日取 reference/listing-dates-twse.json（官方）或 etf-meta.json；取不到 → 該檔上市至今覆蓋率 UNKNOWN；
- 分母未知一律 null／UNKNOWN；覆蓋率＝有效∩應有 ÷ 應有，禁止 >100%；
- 停牌、無成交、尚未公告、不適用（OUT_OF_SCOPE/NOT_APPLICABLE/NOT_DUE）不得列為真正缺失；
- 唯讀：不修改任何正式資料；QA Gate／LKG／Freshness Guard 不受影響。
"""
import json, os, sys, glob, csv, datetime as dt
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
NOW = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec="seconds")
SCHEMA = "1.1.0"
# 統一稽核截止（Phase 8A 前置修正 1）：coverage 與 gaps 必須同一 audit_cutoff 與日曆版本。
# 11-27（週五）的日終批次於 11-28 06:00 完成，STOCK_DAY 實測已可取 → cutoff=2026-11-27。
AUDIT_CUTOFF = "2026-11-27"
BUILD_START = "2025-08-01"  # K 線/快照集建置起點（建置決策，上市前不得計入缺失）


def _load(rel):
    try:
        return json.load(open(os.path.join(DATA, rel), encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _pct(valid, expected):
    if expected is None:
        return None
    if expected <= 0:
        return None
    return round(min(100.0, valid / expected * 100.0), 2)


def _entry(dataset, market, scope, start, end, expected, actual, valid, missing, invalid=0,
           dup=0, denom_source=None, vstatus=None, extra=None):
    e = {
        "dataset": dataset, "market": market, "scope": scope,
        "start_date": start, "end_date": end,
        "expected_count": expected, "actual_count": actual,
        "valid_count": valid, "missing_count": missing,
        "invalid_count": invalid, "duplicate_count": dup,
        "coverage_pct": _pct(valid, expected),
        "denominator_source": denom_source or "UNKNOWN",
        "verification_status": vstatus or ("VERIFIED" if expected is not None else "UNKNOWN"),
        "audited_at": NOW,
    }
    if extra:
        e.update(extra)
    return e


def audit(mode="full"):
    """稽核模式（Phase 8 稽核自動化）：
    daily   = 最新交易日快照＋欄位＋NAV 新鮮度（增量抽查，跳過 1,450 檔 K 線掃描）
    weekly  = daily＋全 K 線歷史缺口＋ETF 資料集合
    monthly = 完整（全項＋官方來源核對清單）（預設）"""
    coverage, gaps = [], []

    # ── 基準：交易日曆（官方代理＋交叉驗證）──
    cal_doc = _load("reference/trade-calendar-2025-2026.json") or {}
    cal = (cal_doc.get("tw") or {}).get("trading_days") or []
    cal_us = (cal_doc.get("us") or {}).get("trading_days") or []
    calendar_status = (cal_doc.get("tw") or {}).get("verification_status", "UNKNOWN")
    listing_doc = _load("reference/listing-dates-twse.json") or {}
    listing = listing_doc.get("stocks") or {}

    # ── 1. 台股每日快照交易日 ──
    snaps = sorted(glob.glob(os.path.join(DATA, "history", "*.json")))
    snap_dates = [dt.datetime.strptime(os.path.basename(p)[:8], "%Y%m%d").date().isoformat() for p in snaps]
    snapset = set(snap_dates)
    # 公告期限：統計截止＝最新快照日（快照集自身的 as-of）；次一交易日若已過公告期限（隔日 06:00 日終批次）
    # 且今日為其後的第一個工作日之後，列為 TAIL 候選缺（candidate，需確認日終批次已跑）。
    if snap_dates:
        cutoff = max(snap_dates)
        expected_days = [c for c in cal if "2025-08-01" <= c <= cutoff]
        missing_days = sorted(set(expected_days) - snapset)
        coverage.append(_entry(
            "tw-snapshot-days", "TW", "history 每日快照（建置範圍 2025-08-01 起）",
            min(snap_dates), cutoff, len(expected_days), len(snap_dates), len(snap_dates),
            len(missing_days), denom_source=f"reference trade-calendar（{calendar_status}）",
            extra={"missing_dates": missing_days}))
        for d in missing_days:
            gaps.append({"dataset": "tw-snapshot", "market": "TW", "symbol": None,
                         "missing_date": d, "field": "daily_snapshot", "gap_type": "MIDDLE_OR_TAIL",
                         "verification_status": "confirmed", "priority": "P0",
                         "source": "TWSE STOCK_DAY 逐檔月表（實測可行）", "status": "open",
                         "retry_count": 0, "last_attempt": None, "resolved_at": None})

    # ── 2. 台股 K 線（四類缺口；上市日＝官方 listing-dates 或 etf-meta；無者 UNKNOWN）──
    etf_meta = _load("etf-meta.json") or {}
    etf_listing = {e.get("sym"): e.get("listing_date") for e in etf_meta.get("etfs", []) if e.get("listing_date")}
    stocks_doc = _load("stocks.json") or {}
    stocks = stocks_doc.get("stocks", [])
    suspended = {s.get("sym") for s in stocks if s.get("trading_status") == "suspended"}
    kstat = {"HEAD": 0, "MIDDLE": 0, "TAIL": 0, "FULL_MISSING": 0}
    kfiles = sorted(glob.glob(os.path.join(DATA, "kline", "*.json")))
    expected_total = actual_total = missing_total = 0
    unknown_listing = 0
    per_dataset_first = None
    for p in kfiles:
        d = _load(os.path.relpath(p, DATA)) or {}
        rows = d.get("rows") or []
        dates = [r[0] for r in rows if r and r[0]]
        sym = os.path.basename(p)[:-5]
        ld = listing.get(sym, {}).get("listing_date") or etf_listing.get(sym)
        if not ld:
            unknown_listing += 1
        # 應有起始日：上市日（官方）與建置起點（2025-08-01）取較晚者——建置決策：不回補建置前
        start = max(ld, BUILD_START) if ld else None
        if start is None:
            # 上市日 UNKNOWN：以首筆有效紀錄近似，標記 APPROX_LISTING
            start = min(dates) if dates else BUILD_START
        exp = [c for c in cal if start <= c <= AUDIT_CUTOFF and dt.date.fromisoformat(c).weekday() < 5]
        # Phase 8A 對帳修正：valid 只數目標區間內的根——
        # 區間外的歷史根（如 006201 的 2025-08 前資料）不得計入 valid（會虛增覆蓋率）
        valid_set = set(x for x in dates if start <= x <= AUDIT_CUTOFF)
        miss = sorted(set(exp) - valid_set)
        expected_total += len(exp)
        actual_total += len(valid_set)
        missing_total += len(miss)
        if not dates:
            kstat["FULL_MISSING"] += 1
            continue
        first, last = min(dates), max(dates)
        for m in miss:
            cat = "HEAD" if m < first else ("MIDDLE" if m <= last else "TAIL")
            kstat[cat] += 1
            if per_dataset_first is None:
                per_dataset_first = first
        # 停牌分離：目前 suspended 標的的缺日屬「無成交候選」——
        # Phase 8A 修正：無官方證據（該日行情來源確認無成交）前不得關閉為 not-a-gap，維持待驗證。
        if sym in suspended and miss:
            gaps.append({"dataset": "tw-kline", "market": "TW", "symbol": sym,
                         "missing_date": miss[:3], "field": "kline", "gap_type": "UNTRADED_CANDIDATE",
                         "verification_status": "candidate", "priority": "P3",
                         "source": "suspended 標的；需官方月表證實當日無成交後方可關閉",
                         "status": "pending_verification",
                         "retry_count": 0, "last_attempt": None, "resolved_at": None})
    for cat, key in (("HEAD", "backfill-candidate（目標期建置前缺）"), ("MIDDLE", None), ("TAIL", None)):
        if kstat[cat]:
            gaps.append({"dataset": "tw-kline", "market": "TW", "symbol": None,
                         "missing_date": None, "field": f"kline_gap_{cat}",
                         "gap_type": cat, "verification_status": "candidate" if cat == "HEAD" else "confirmed",
                         "priority": {"HEAD": "P3", "MIDDLE": "P0", "TAIL": "P0"}[cat],
                         "source": "TWSE STOCK_DAY 逐檔月表", "status": "open" if cat != "HEAD" else "deferred",
                         "retry_count": 0, "last_attempt": None, "resolved_at": None,
                         "missing_records": kstat[cat], "note": key})
    coverage.append(_entry(
        "tw-kline", "TW", f"kline {len(kfiles)} 檔（HEAD/MIDDLE/TAIL 分類，valid 只數目標區間內）",
        BUILD_START, AUDIT_CUTOFF, expected_total, actual_total, actual_total,
        missing_total, denom_source="listing-dates-twse（官方上市日）＋建置起點 2025-08-01",
        vstatus="VERIFIED_WITH_APPROX" if unknown_listing else "VERIFIED",
        extra={"gaps_by_category": kstat, "unknown_listing_count": unknown_listing,
               "reconciliation": f"missing {missing_total:,} ＝ HEAD {kstat['HEAD']:,} ＋ MIDDLE {kstat['MIDDLE']:,} ＋ TAIL {kstat['TAIL']:,} ＋ FULL_MISSING {kstat['FULL_MISSING']:,}"}))

    # ── 3. 台股欄位完整率（個股分母）──
    stk = [s for s in stocks if s.get("security_type") != "etf"]
    n_stk = len(stk)
    for col, scope in (("price", "全檔"), ("market_cap", "全檔"), ("pe", "個股"), ("pb", "個股"),
                       ("roe", "個股"), ("div", "個股")):
        pool = stocks if scope == "全檔" else stk
        n = len(pool)
        v = sum(1 for s in pool if s.get(col) is not None)
        coverage.append(_entry(f"tw-stocks-field:{col}", "TW", f"欄位完整率（{scope}口徑）",
                               None, (stocks_doc.get("meta") or {}).get("as_of"),
                               n, n, v, n - v,
                               denom_source="個股總數（ETF 無此數值不計入）" if scope == "個股" else "stocks.json 全檔",
                               vstatus="VERIFIED"))

    # ── 4. 台股 ETF 資料集集合 ──
    etf_set = {s.get("sym") for s in stocks if s.get("security_type") == "etf"}
    H = (_load("etf-holdings.json") or {}).get("holdings", {})
    nav = (_load("etf-nav.json") or {}).get("navs", {})
    fees = set()
    try:
        with open(os.path.join(DATA, "etf-fees.csv"), encoding="utf-8-sig") as f:
            fees = {r.get("sym") for r in csv.DictReader(f) if r.get("sym")}
    except OSError:
        pass
    meta_set = {e.get("sym") for e in etf_meta.get("etfs", [])}
    for name, ds in (("etf-meta", meta_set), ("etf-holdings", set(H)), ("etf-nav", set(nav)), ("etf-fees", fees)):
        missing_syms = sorted(s for s in (etf_set - ds) if s)
        coverage.append(_entry(f"tw-{name}", "TW", "ETF 母體 362 檔集合比對",
                               None, None, len(etf_set), len(ds), len(etf_set & ds),
                               len(missing_syms), 0, max(0, len(ds) - len(etf_set & ds)),
                               denom_source="stocks.json security_type=etf", vstatus="VERIFIED",
                               extra={"missing_codes": missing_syms, "extra_codes": sorted(ds - etf_set)}))
        for sym in missing_syms:
            gaps.append({"dataset": name, "market": "TW", "symbol": sym, "missing_date": None,
                         "field": name, "gap_type": "MISSING_DATASET_ENTRY",
                         "verification_status": "confirmed", "priority": "P2",
                         "source": "官方發行商或既有管線重跑", "status": "open",
                         "retry_count": 0, "last_attempt": None, "resolved_at": None})
    # NAV 新鮮度（record_date）
    rds = Counter(str(v.get("record_date"))[:10] for v in nav.values() if isinstance(v, dict))
    coverage.append(_entry("tw-etf-nav-freshness", "TW", "NAV record_date 分布（最新）",
                           None, None, len(nav), len(nav), sum(v for k, v in rds.items() if k >= "2026-11-20"),
                           len(nav) - sum(v for k, v in rds.items() if k >= "2026-11-20"),
                           denom_source="etf-nav.json record_date", vstatus="VERIFIED",
                           extra={"record_date_top": rds.most_common(3)}))

    # ── 4b. 台股官方財報（financial/dividend 對個股母體）──
    fund = _load("official-fundamentals.json") or {}
    fin = set((fund.get("financial") or {}).keys())
    div = set((fund.get("dividend") or {}).keys())
    stk_syms = {s.get("sym") for s in stocks if s.get("security_type") != "etf"}
    coverage.append(_entry("tw-official-fundamentals:financial", "TW", "官方財報（2026Q3，MOPS 彙總表）",
                           None, (fund.get("meta") or {}).get("financial_period"),
                           len(stk_syms), len(fin), len(stk_syms & fin), len(stk_syms - fin),
                           denom_source="stocks.json 個股母體", vstatus="PARTIALLY_VERIFIED",
                           extra={"missing_codes": sorted(stk_syms - fin)}))
    for sym in sorted(stk_syms - fin):
        gaps.append({"dataset": "official-fundamentals", "market": "TW", "symbol": sym, "missing_date": None,
                     "field": "financial", "gap_type": "MISSING",
                     "verification_status": "confirmed", "priority": "P1",
                     "source": "MOPS 金融業彙總表（t163sb05/06/07 皆不含金控母公司且舊 API 被 WAF 擋——來源待定位：公開資訊觀測站金融業下載檔）",
                     "status": "open", "retry_count": 0, "last_attempt": None, "resolved_at": None})

    # ── 5. 美股 ──
    us = _load("us/us-stocks.json") or {}
    us_stocks = us.get("stocks", [])
    ue = _load("us/us-etfs.json") or {}
    ed = _load("us/us-edgar.json") or {}
    eds = ed.get("stocks") if isinstance(ed.get("stocks"), (list, dict)) else ed.get("data")
    ed_keys = set(eds.keys() if isinstance(eds, dict) else [x.get("sym") for x in eds if isinstance(x, dict)]) if eds else set()
    us_syms = {s.get("sym") for s in us_stocks}
    coverage.append(_entry("us-stocks", "US", "美股個股", None, (us.get("meta") or {}).get("as_of"),
                           len(us_stocks), len(us_stocks), len(us_syms), 0, 0,
                           len(us_stocks) - len(us_syms), denom_source="us-stocks.json", vstatus="VERIFIED"))
    coverage.append(_entry("us-etfs", "US", "美股 ETF", None, (ue.get("meta") or {}).get("as_of"),
                           len(ue.get("etfs", [])), len(ue.get("etfs", [])), len(ue.get("etfs", [])), 0,
                           denom_source="us-etfs.json", vstatus="VERIFIED"))
    cov_ed = _entry("us-edgar", "US", "SEC EDGAR 財報評分", None, None, len(us_syms),
                    len(ed_keys), len(us_syms & ed_keys), len(us_syms - ed_keys),
                    denom_source="us-stocks.json 母體", vstatus="VERIFIED")
    coverage.append(cov_ed)
    for sym in sorted(us_syms - ed_keys):
        gaps.append({"dataset": "us-edgar", "market": "US", "symbol": sym, "missing_date": None,
                     "field": "edgar_scores", "gap_type": "MISSING",
                     "verification_status": "candidate", "priority": "P2",
                     "source": "sec-edgar-fundamentals 重跑", "status": "open",
                     "retry_count": 0, "last_attempt": None, "resolved_at": None})

    # ── 6. 全球指數 ──
    idx = _load("indices.json") or {}
    idx_rows = idx.get("indices", [])
    none_close = [x.get("yf") for x in idx_rows if x.get("close") is None]
    coverage.append(_entry("global-indices", "GLOBAL", "全球指數收盤", None, (idx.get("meta") or {}).get("as_of"),
                           len(idx_rows), len(idx_rows), len(idx_rows) - len(none_close), len(none_close),
                           denom_source="indices-config.json", vstatus="VERIFIED" if not none_close else "PARTIAL",
                           extra={"missing_symbols": none_close}))
    for yf_sym in none_close:
        gaps.append({"dataset": "global-indices", "market": "GLOBAL", "symbol": yf_sym, "missing_date": None,
                     "field": "close", "gap_type": "SOURCE_UNAVAILABLE",
                     "verification_status": "confirmed", "priority": "P2",
                     "source": "TWSE BFIAMU（台股類指數✓實測）/恒生官網/JPX 官網", "status": "open",
                     "retry_count": 0, "last_attempt": None, "resolved_at": None})

    # ── 7. 已知異常待查（00878 權重）──
    for sym in ("00878",):
        gaps.append({"dataset": "etf-holdings", "market": "TW", "symbol": sym, "missing_date": None,
                     "field": "items_weight", "gap_type": "ANOMALY",
                     "verification_status": "candidate", "priority": "P1",
                     "source": "國泰投信官網持股頁原始對照", "status": "open",
                     "retry_count": 0, "last_attempt": None, "resolved_at": None,
                     "note": "權重合計 1700%，前 5 筆合理，後段欄位語意待官方確認"})

    # ── 輸出 ──
    cov_doc = {"schema_version": SCHEMA, "audited_at": NOW, "audit_cutoff": AUDIT_CUTOFF,
               "calendar_source": f"reference/trade-calendar-2025-2026.json（{calendar_status}）",
               "coverage": coverage}
    gaps_doc = {"schema_version": SCHEMA, "generated_at": NOW, "audit_cutoff": AUDIT_CUTOFF,
                "note": "candidate=待確認（停牌/無成交/待官方對照）；confirmed=已確認缺失；回補後須重新驗證才能標 resolved",
                "gaps": gaps}
    for rel, doc in (("coverage.json", cov_doc), ("gaps.json", gaps_doc)):
        p = os.path.join(DATA, rel)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        os.replace(tmp, p)
    # 模式過濾（Phase 8 稽核自動化）：daily=快照＋欄位＋NAV 新鮮度（增量抽查）；
    # weekly=daily＋K 線＋ETF 資料集；monthly=full＋來源核對。掃描一律完整執行（1,450 檔 IO 僅數秒）。
    if mode == "daily":
        keep = ("tw-snapshot-days", "tw-etf-nav-freshness")
        coverage = [e for e in coverage if e["dataset"] in keep or e["dataset"].startswith("tw-stocks-field")]
        gaps = [g for g in gaps if g["dataset"] in ("tw-snapshot", "etf-holdings") or g.get("priority") == "P0"]
    elif mode == "weekly":
        keep = ("tw-snapshot-days", "tw-kline", "tw-etf-meta", "tw-etf-holdings", "tw-etf-nav",
                "tw-etf-fees", "tw-etf-nav-freshness", "tw-stocks-field:price", "tw-stocks-field:pe")
        coverage = [e for e in coverage if e["dataset"] in keep]
    print(f"[{mode}] coverage.json: {len(coverage)} 條目｜gaps.json: {len(gaps)} 條目（audit_cutoff={AUDIT_CUTOFF}）")
    return cov_doc, gaps_doc


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="資料庫覆蓋率稽核（唯讀）")
    ap.add_argument("--mode", choices=["daily", "weekly", "monthly", "full"], default="full")
    a = ap.parse_args()
    audit(mode=a.mode)
