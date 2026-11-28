#!/usr/bin/env python3
"""安全歷史回補（Phase 8A，2026-11-28）——指定日期的台股快照與 K 線回補。

設計（Phase 7A.4 規範落地）：
1. 讀取既有快照／K 線（存在→合併模式；不存在→新建）。
2. 來源＝TWSE STOCK_DAY 官方月表（rwd/zh/afterTrading，免 key）——
   回應即官方證據：僅新增缺失紀錄，不覆蓋既有有效紀錄；
   修正既有錯誤需另有官方證據（本程式預設不修正）。
3. 歷史快照的 PE/PB/殖利率／產業欄位取不到當時值 → null（不得以今日資料冒充歷史）。
4. 停牌/無成交（官方 '--'）→ OHLC null＋volume 0，trading_status 標記，不視為缺失。
5. 驗證於暫存區完成 → 原子寫入（tmp + os.replace）→ 失敗不污染正式資料。
6. 重複回補 idempotent：已存在的代號+日期不重複新增。
7. 回補完成後請執行 scripts/database_audit.py 重新稽核，gaps 任務經重新驗證才標 resolved。

用法：
  python skills/data/backfill_history.py --date 2026-11-20 [--dry-run] [--limit N] [--sleep 1.2]
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(ROOT, "data")
UA = {"User-Agent": "mklab-stock/1.0 (backfill)"}


def _get(url, timeout=30, attempts=3):
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise last if last is not None else RuntimeError(f"fetch failed: {url}")


def _roc_row_to_record(row, trade_date_iso):
    """TWSE STOCK_DAY 行 → 統一紀錄。官方 '--'（未成交）→ OHLC null、volume 0（分開處理，不造假）。"""
    # 欄序：0 日期 / 1 成交股數 / 2 成交金額 / 3 開 / 4 高 / 5 低 / 6 收 / 7 漲跌價差 / 8 成交筆數
    def num(v):
        if v in (None, "", "-", "--", "X"):
            return None
        try:
            return float(str(v).replace(",", ""))
        except (ValueError, TypeError):
            return None
    o, h, l, c = num(row[3]), num(row[4]), num(row[5]), num(row[6])
    vol = num(row[1]) or 0.0  # 官方成交量；無成交日為 '--'→0（股數 0 是事實）
    untraded = o is None or c is None
    return {
        "date": trade_date_iso,
        "open": o, "high": h, "low": l, "close": c,
        "volume": 0.0 if untraded else vol,
        "trading_status": "untraded" if untraded else "active",
        "source": "TWSE_STOCK_DAY",
    }


def fetch_month(sym, ym):
    """抓單檔單月官方月表 → {iso_date: record}。stat 非 OK 或查無資料 → 空 dict（保留失敗證據）。"""
    url = (f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
           f"?date={ym}&stockNo={sym}&response=json")
    try:
        j = _get(url)
    except Exception as e:  # noqa: BLE001
        return {}, f"fetch_failed: {str(e)[:80]}"
    if j.get("stat") != "OK":
        return {}, f"stat={j.get('stat')}"
    out = {}
    for row in j.get("data", []):
        try:
            # row[0]='115/11/20'（民國年/月/日，含斜線）——先去斜線再切片
            digits = row[0].replace("/", "")
            roc = int(digits[:3]) + 1911
            iso = f"{roc}-{digits[3:5]}-{digits[5:7]}"
            out[iso] = _roc_row_to_record(row, iso)
        except (ValueError, IndexError, TypeError):
            continue
    return out, None


def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return default


def atomic_write(path, doc):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def merge_snapshot(target_date, records, symbols_meta):
    """合併指定日期快照：保留既有有效紀錄、只新增缺失；PE/PB/殖利率/產業=null（歷史不可得）。"""
    path = os.path.join(DATA, "history", f"{target_date.replace('-', '')}.json")
    doc = load_json(path, None)
    existing = {}
    if doc and isinstance(doc.get("stocks"), list):
        existing = {r.get("stock_id"): r for r in doc["stocks"] if r.get("stock_id")}
    added, kept, skipped_suspended = 0, 0, 0
    for sym, rec in records.items():
        if sym in existing:
            kept += 1
            continue  # 既有有效紀錄不覆蓋（idempotent）
        meta = symbols_meta.get(sym) or {}
        existing[sym] = {
            "stock_id": sym, "stock_name": meta.get("name", ""),
            "close": rec["close"], "open": rec["open"], "high": rec["high"], "low": rec["low"],
            "volume": rec["volume"],
            "pe_ratio": None, "pb_ratio": None, "dividend_yield": None,  # 歷史不可得 → null
            "industry": meta.get("ind"),
        }
        if rec["trading_status"] == "untraded":
            skipped_suspended += 1
        added += 1
    out = {"trade_date": target_date, "schema_version": "1.0.0",
           "count": len(existing), "stocks": [existing[k] for k in sorted(existing)],
           "backfill": {"performed_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec="seconds"),
                        "source": "TWSE_STOCK_DAY", "added": added, "kept_existing": kept}}
    return path, out, added, kept, skipped_suspended


def merge_kline(sym, target_date, rec):
    """K 線合併：日期不存在才 append；已存在不動（idempotent）。
    回傳 (status, rows_len, doc)——呼叫者必須寫回此 doc（Phase 8A 驗收修正：先前
    函式內修改但呼叫者重新讀檔寫回，導致新增全部丟失）。"""
    path = os.path.join(DATA, "kline", f"{sym}.json")
    doc = load_json(path, {"sym": sym, "rows": []})
    rows = doc.setdefault("rows", [])
    if any(r and r[0] == target_date for r in rows):
        return "kept", len(rows), doc
    if rec["close"] is None:
        return "untraded_skip", len(rows), doc  # K 線不存 null 根（停牌日不補 0）
    rows.append([target_date, rec["open"], rec["high"], rec["low"], rec["close"], rec["volume"]])
    rows.sort(key=lambda r: r[0])
    return "added", len(rows), doc


def sync_stocks_current(target_date, records):
    """回補日若晚於 stocks.json 現值 → 同步 price/OHLCV/market_cap/price_asof（Phase 8A 教訓：
    回補 history/kline 而不同步現值，會造成「K 線最新根 vs stocks.json price」不一致，
    觸發 QA 的 MARKET_CAP_MISMATCH 與 P0-3）。market_cap 一律用 QA 公式 close×shares 重算
    （比率外推會保留既有偏差）；無成交標的不動現值；PE/PB 等基本面不動。"""
    path = os.path.join(DATA, "stocks.json")
    doc = load_json(path, {}) or {}
    smap = {s.get("sym"): s for s in doc.get("stocks", [])}
    updated = 0
    for sym, rec in records.items():
        s = smap.get(sym)
        if not s or rec.get("close") is None:
            continue
        old_p = s.get("price")
        if str(s.get("price_asof") or "")[:10] >= target_date:
            continue  # 現值已不舊於回補日，不回寫
        s["price"] = rec["close"]
        s["open"] = rec.get("open"); s["high"] = rec.get("high"); s["low"] = rec.get("low")
        s["volume"] = rec.get("volume")
        s["price_asof"] = target_date
        sh = s.get("shares")
        if sh and sh > 0:
            s["market_cap"] = round(rec["close"] * sh, 1)
        updated += 1
    if updated:
        from collections import Counter
        doc.setdefault("meta", {})["as_of"] = target_date
        doc["meta"]["price_asof_counts"] = dict(Counter(
            str(s.get("price_asof"))[:10] for s in doc.get("stocks", [])))
        atomic_write(path, doc)
    return updated


def main(argv=None):
    ap = argparse.ArgumentParser(description="安全歷史回補（指定日期快照＋K 線）")
    ap.add_argument("--date", required=True, help="目標日期 YYYY-MM-DD（必須為已公告收盤的交易日）")
    ap.add_argument("--dry-run", action="store_true", help="只統計與驗證，不寫入任何檔案")
    ap.add_argument("--limit", type=int, default=0, help="只回補前 N 檔（小批量測試用）")
    ap.add_argument("--sleep", type=float, default=1.2, help="循序請求間隔秒數（預設 1.2，約 29 分/1450 檔）")
    ap.add_argument("--symbols", default="", help="僅回補指定代號（逗號分隔，小批量用）")
    args = ap.parse_args(argv)

    target = args.date
    ym = target.replace("-", "")[:6]
    stocks_doc = load_json(os.path.join(DATA, "stocks.json"), {}) or {}
    symbols_meta = {s.get("sym"): s for s in stocks_doc.get("stocks", [])}
    universe = sorted(symbols_meta.keys())
    if args.symbols:
        want = {x.strip() for x in args.symbols.split(",") if x.strip()}
        universe = [s for s in universe if s in want]
    if args.limit:
        universe = universe[:args.limit]

    print(f"[backfill] 目標 {target}｜母體 {len(universe)} 檔｜dry-run={args.dry_run}｜sleep={args.sleep}s")
    print(f"[backfill] 預估時間 ≈ {len(universe) * (args.sleep + 0.8) / 60:.0f} 分鐘（含 HTTP 回應與退避餘裕）")

    records, evidence = {}, {}
    t0 = time.time()
    for i, sym in enumerate(universe):
        month_recs, err = fetch_month(sym, ym)
        rec = month_recs.get(target)
        if rec is None:
            evidence[sym] = err or "not_in_official_month_table（無行或無成交）"
        else:
            records[sym] = rec
        if (i + 1) % 100 == 0:
            rate = (i + 1) / (time.time() - t0)
            print(f"  進度 {i+1}/{len(universe)}｜已取得 {len(records)}｜速率 {rate:.2f} 檔/秒｜ETA {(len(universe)-i-1)/max(rate,0.01)/60:.0f} 分")
        time.sleep(args.sleep)

    print(f"[backfill] 取得官方紀錄 {len(records)} 檔／無官方行 {len(evidence)} 檔（含未成交與月表無行）")
    if args.limit or args.symbols:
        for sym, rec in list(records.items())[:5]:
            print(f"  樣本 {sym}: O={rec['open']} H={rec['high']} L={rec['low']} C={rec['close']} V={rec['volume']} status={rec['trading_status']}")

    if args.dry_run:
        print("[backfill] dry-run：不寫入任何檔案 ✓")
        json.dump({"target": target, "fetched": len(records), "no_evidence": evidence,
                   "note": "dry-run"}, open(os.path.join(DATA, "digest", f"backfill-dryrun-{target}.json"), "w"), ensure_ascii=False, indent=1)
        return 0

    # 快照合併＋原子寫入
    snap_path, snap_doc, added, kept, untraded = merge_snapshot(target, records, symbols_meta)
    atomic_write(snap_path, snap_doc)
    print(f"[backfill] 快照 {os.path.basename(snap_path)}：新增 {added}／保留既有 {kept}／其中無成交 {untraded}")

    # K 線合併（只處理有成交的紀錄；K 線不存 null 根）——寫回 merge 後的 doc（Phase 8A 修正）
    ka = ke = ks = 0
    for sym, rec in records.items():
        st, _, doc = merge_kline(sym, target, rec)
        ka += st == "added"; ke += st == "kept"; ks += st == "untraded_skip"
        if st == "added":
            atomic_write(os.path.join(DATA, "kline", f"{sym}.json"), doc)
    print(f"[backfill] K 線：新增 {ka}／已存在保留 {ke}／無成交跳過 {ks}")
    # 同步 stocks.json 現值（回補日 > 現值日期時）——避免 K 線與現值不一致觸發 QA 阻擋
    nsync = sync_stocks_current(target, records)
    print(f"[backfill] stocks.json 現值同步: {nsync} 檔（僅 price_asof 早於回補日者）")
    json.dump({"target": target, "snapshot_added": added, "kline_added": ka,
               "no_official_row": {k: v for k, v in list(evidence.items())[:50]},
               "performed_at": NOW_STAMP()}, open(os.path.join(DATA, "digest", f"backfill-{target}.json"), "w"), ensure_ascii=False, indent=1)
    print("[backfill] 完成——請執行 scripts/database_audit.py 重新稽核，gaps 經驗證後才標 resolved")
    return 0


def NOW_STAMP():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec="seconds")


if __name__ == "__main__":
    sys.exit(main())
