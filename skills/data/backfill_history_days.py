#!/usr/bin/env python3
"""歷史快照回補（補齊漏抓的真實交易日）。

用途：每日 CI 若某個交易日漏跑或來源失敗，`data/history/` 會缺該日快照，
      造成 kline／技術指標／區間報酬率在該處出現斷點（例如 2026-07-20、
      07-23、08-05、09-03 四天）。本腳本用 **TWSE／TPEx 官方歷史端點**把那幾天補回來。

為什麼不從其他資料庫（如 tw_stock_all.db）抄：
  該庫在 2026-07 之後 open/high/low 缺 93~97%（只剩收盤），且含 18 天休市日的
  殘值列。抄過來會寫出「沒有開高低價」的快照，違反本站「資料不足即為 null、
  絕不以推測值冒充」的原則。官方端點回得到真正的當日四價，才是正確來源。

安全規則（缺一不可）：
  1. **只寫不存在的快照檔**，既有檔一律不覆寫。
  2. 官方當日無資料（休市、颱風假）→ 跳過並記錄，不寫入空檔。
  3. 寫入前檢查完整度：`high` 整日缺失 > 50% 視為非交易日 → 不寫。
  4. 代號範圍以「該日前後最近的既有快照」聯集為準，**不自行發明代號**。
  5. 產業別沿用該代號在 `stocks.json` 的值（產業非每日變動資料）；
     上櫃來源（TPEx）一律 pe/pb/殖利率/產業 = null，與每日管線行為一致。

⚠️ 上櫃成交量預設寫 null（`--tpex-volume raw` 可改成寫原值）：
  每日管線用的是 TPEx OpenAPI `TradingShares`（總成交量），但 OpenAPI **只提供當日**，
  回溯不到歷史。可回溯的 rwd 頁標題為「上櫃股票每日收盤行情**(不含定價)**」，
  同一天實測比 OpenAPI 少 0.09%～0.91%（排除盤後定價交易）。
  兩種口徑混在同一條序列裡無法察覺、也無法更正 → 依本站「資料不足即為 null、
  不以不同口徑的值冒充」原則，歷史回補的上櫃 volume 一律 null。
  （四價不受影響：TWSE／TPEx 的開高低收皆為官方當日值。）

用法：
  python3 skills/data/backfill_history_days.py --dry-run 2026-07-20 2026-07-23
  python3 skills/data/backfill_history_days.py 2026-07-20 2026-07-23 2026-08-05 2026-09-03
  python3 skills/data/backfill_history_days.py --tpex-volume raw 2026-07-20   # 保留上櫃原值
"""
import argparse
import glob
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HIST = os.path.join(ROOT, "data", "history")
STOCKS = os.path.join(ROOT, "data", "stocks.json")
LOG = os.path.join(ROOT, "data", "history-backfill-log.json")
UA = "Mozilla/5.0 (compatible; mklab-stock/3.0)"
TZ_TW = timezone(timedelta(hours=8))
SCHEMA_VERSION = "1.0.0"


def log(msg):
    print(msg, flush=True)


def fetch_json(url, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                body = r.read().decode("utf-8", "replace")
            return json.loads(body)
        except Exception as e:  # noqa: BLE001 - 來源多種失敗型態，一律重試
            last = e
            if i < tries - 1:
                time.sleep(5 * (i + 1))
    log(f"    ⚠️ 下載失敗（{tries} 次）：{last}")
    return None


def num(v):
    """官方表格的數字欄位：去千分位、處理 '-'/'--'/'X' 等無值記號。"""
    s = str(v).replace(",", "").replace("\u3000", " ").strip()
    if s in ("", "-", "--", "---", "X", "N/A", "nan"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fetch_twse(date):
    """TWSE 上市：MI_INDEX（每日收盤行情，含四價＋量）＋ BWIBBU_d（PE/PB/殖利率）。"""
    ymd = date.replace("-", "")
    mi = fetch_json(f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={ymd}&type=ALLBUT0999&response=json")
    if not mi or mi.get("stat") != "OK":
        log(f"    ⚠️ MI_INDEX 無資料（{ymd}）：{None if not mi else mi.get('stat')}")
        return {}
    table = None
    for t in mi.get("tables", []) or []:
        if "每日收盤行情" in (t.get("title") or ""):
            table = t
            break
    if not table or not table.get("data"):
        log("    ⚠️ MI_INDEX 找不到每日收盤行情表")
        return {}
    f = [x.strip() for x in table["fields"]]
    i_code = f.index("證券代號")
    i_name = f.index("證券名稱")
    i_vol = f.index("成交股數")
    i_open, i_high, i_low = f.index("開盤價"), f.index("最高價"), f.index("最低價")
    i_close = f.index("收盤價")
    i_pe = f.index("本益比") if "本益比" in f else None
    out = {}
    for r in table["data"]:
        code = str(r[i_code]).strip()
        if not code:
            continue
        out[code] = {
            "name": str(r[i_name]).strip(),
            "close": num(r[i_close]), "open": num(r[i_open]),
            "high": num(r[i_high]), "low": num(r[i_low]),
            "volume": num(r[i_vol]),
            "pe": num(r[i_pe]) if i_pe is not None else None,
            "pb": None, "div": None,
        }
    # BWIBBU_d：本益比／股價淨值比／殖利率（MI_INDEX 只有本益比）
    bw = fetch_json(f"https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date={ymd}&selectType=ALL&response=json")
    if bw and bw.get("stat") == "OK" and bw.get("data"):
        bf = [x.strip() for x in bw["fields"]]
        j_code, j_div, j_pe, j_pb = bf.index("證券代號"), bf.index("殖利率(%)"), bf.index("本益比"), bf.index("股價淨值比")
        n = 0
        for r in bw["data"]:
            code = str(r[j_code]).strip()
            if code in out:
                out[code]["div"] = num(r[j_div])
                out[code]["pe"] = num(r[j_pe]) if num(r[j_pe]) is not None else out[code]["pe"]
                out[code]["pb"] = num(r[j_pb])
                n += 1
        log(f"    BWIBBU_d 併入 {n} 檔 PE/PB/殖利率")
    else:
        log("    ⚠️ BWIBBU_d 無資料，PE/PB/殖利率僅取 MI_INDEX 本益比")
    return out


def fetch_tpex(date):
    """TPEx 上櫃：每日收盤行情（含四價＋量）。上櫃歷史 PE/PB/殖利率端點不提供 → null。"""
    y, m, d = date.split("-")
    j = fetch_json(f"https://www.tpex.org.tw/www/zh-tw/afterTrading/otc?date={y}/{m}/{d}&type=EW&id=&response=json")
    if not j or not j.get("tables"):
        log("    ⚠️ TPEx 無資料")
        return {}
    t = j["tables"][0]
    if not t.get("data"):
        log("    ⚠️ TPEx 表格為空")
        return {}
    f = [x.strip() for x in t["fields"]]
    i_code, i_name = f.index("代號"), f.index("名稱")
    i_close, i_open = f.index("收盤"), f.index("開盤")
    i_high, i_low = f.index("最高"), f.index("最低")
    i_vol = f.index("成交股數")
    out = {}
    for r in t["data"]:
        code = str(r[i_code]).strip()
        if not code:
            continue
        out[code] = {
            "name": str(r[i_name]).strip(),
            "close": num(r[i_close]), "open": num(r[i_open]),
            "high": num(r[i_high]), "low": num(r[i_low]),
            "volume": num(r[i_vol]),
            "pe": None, "pb": None, "div": None,
        }
    return out


def neighbour_syms(date):
    """回傳該日前後最近既有快照的代號聯集（不自行發明代號）。"""
    files = sorted(glob.glob(os.path.join(HIST, "*.json")))
    days = [os.path.basename(p)[:-5] for p in files]
    ymd = date.replace("-", "")
    before = [d for d in days if d < ymd]
    after = [d for d in days if d > ymd]
    out = set()
    for pick in (before[-1] if before else None, after[0] if after else None):
        if not pick:
            continue
        try:
            doc = json.load(open(os.path.join(HIST, pick + ".json"), encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out |= {r.get("stock_id") for r in doc.get("stocks", []) if r.get("stock_id")}
    return out


def build(date, dry, tpex_volume="null"):
    ymd = date.replace("-", "")
    path = os.path.join(HIST, ymd + ".json")
    log(f"\n=== {date} ===")
    if os.path.exists(path):
        log("  ⏭ 快照已存在，不覆寫")
        return {"date": date, "status": "skipped_exists"}
    universe = neighbour_syms(date)
    if not universe:
        log("  ❌ 找不到相鄰既有快照可界定代號範圍")
        return {"date": date, "status": "error", "reason": "no_neighbour"}
    ind, is_etf = {}, set()
    try:
        for s in json.load(open(STOCKS, encoding="utf-8")).get("stocks", []):
            ind[s["sym"]] = s.get("ind")
            if s.get("security_type") == "etf":
                is_etf.add(s["sym"])
    except (OSError, json.JSONDecodeError):
        pass

    log(f"  代號範圍（相鄰快照聯集）：{len(universe)} 檔")
    twse = fetch_twse(date)
    log(f"  TWSE 取得 {len(twse)} 檔")
    time.sleep(3)  # 對官方來源客氣一點
    tpex = fetch_tpex(date)
    log(f"  TPEx 取得 {len(tpex)} 檔")

    rows, sources = [], {"TWSE": 0, "TPEX": 0}
    for code in sorted(universe):
        src = twse.get(code)
        is_tpex = False
        if not src:
            src = tpex.get(code)
            is_tpex = src is not None
        if not src or src.get("close") is None:
            continue
        # ETF 一律 pe/pb/殖利率 = null：每日管線用的 OpenAPI BWIBBU 根本不收 ETF，
        # rwd 版的 BWIBBU_d 則把 ETF 回成 0.00——同一件事（沒有這個數字）。
        # 若照抄 0，會與相鄰快照（None）不一致，也會讓前端把 0 當成真實本益比。
        drop_ratio = is_tpex or code in is_etf
        rows.append({
            "stock_id": code, "stock_name": src["name"],
            "close": src["close"], "open": src["open"], "high": src["high"], "low": src["low"],
            # 上櫃 volume 預設 null（口徑不同，見檔頭說明）；--tpex-volume raw 可保留原值
            "volume": (None if (is_tpex and tpex_volume == "null") else src["volume"]),
            "pe_ratio": None if drop_ratio else src["pe"],
            "pb_ratio": None if drop_ratio else src["pb"],
            "dividend_yield": None if drop_ratio else src["div"],
            "industry": None if is_tpex else ind.get(code),
        })
        sources["TPEX" if is_tpex else "TWSE"] += 1

    if not rows:
        log("  ⚠️ 官方當日無任何資料（休市或來源失敗）→ 不寫入")
        return {"date": date, "status": "no_data"}
    miss_hl = sum(1 for r in rows if r["high"] is None)
    if miss_hl / len(rows) > 0.5:
        log(f"  ❌ high 缺失 {miss_hl}/{len(rows)} > 50%，視為非交易日 → 不寫入")
        return {"date": date, "status": "rejected_incomplete", "rows": len(rows), "missing_high": miss_hl}
    prev_n = None
    for d in sorted(os.listdir(HIST))[-3:]:
        try:
            prev_n = json.load(open(os.path.join(HIST, d), encoding="utf-8")).get("count")
        except Exception:  # noqa: BLE001
            pass
    if prev_n and len(rows) < 0.5 * prev_n:
        log(f"  ❌ 筆數 {len(rows)} 遠低於最近快照 {prev_n}（<50%）→ 可疑，不寫入")
        return {"date": date, "status": "rejected_too_few", "rows": len(rows), "neighbour_count": prev_n}

    log(f"  ✅ 可寫入：{len(rows)} 筆（TWSE {sources['TWSE']}／TPEx {sources['TPEX']}）"
        f"　high 缺 {miss_hl}　open 缺 {sum(1 for r in rows if r['open'] is None)}")
    for code in ("2330", "2317", "0050"):
        r = next((x for x in rows if x["stock_id"] == code), None)
        if r:
            log(f"     {code} {r['stock_name']} O={r['open']} H={r['high']} L={r['low']} "
                f"C={r['close']} V={r['volume']} PE={r['pe_ratio']} PB={r['pb_ratio']}")
    if not dry:
        doc = {"trade_date": date, "schema_version": SCHEMA_VERSION, "count": len(rows), "stocks": rows}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)
        log(f"  💾 已寫入 {os.path.relpath(path, ROOT)}")
    else:
        log("  (dry-run：未寫檔)")
    return {"date": date, "status": "dry_run" if dry else "written",
            "rows": len(rows), "sources": sources, "missing_high": miss_hl}


def main():
    ap = argparse.ArgumentParser(description="用官方歷史端點回補漏抓的交易日快照")
    ap.add_argument("dates", nargs="+", help="日期 YYYY-MM-DD")
    ap.add_argument("--dry-run", action="store_true", help="只檢查與預覽，不寫檔")
    ap.add_argument("--tpex-volume", choices=["null", "raw"], default="null",
                    help="上櫃 volume 要寫 null（預設，口徑與每日管線不同）或原始值")
    a = ap.parse_args()
    results = []
    for d in a.dates:
        try:
            datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            log(f"跳過非法日期：{d}")
            continue
        results.append(build(d, a.dry_run, a.tpex_volume))
    log("\n=== 摘要 ===")
    for r in results:
        log(f"  {r['date']}  {r['status']}"
            + (f"  筆數={r.get('rows')}" if r.get("rows") else ""))
    if not a.dry_run:
        try:
            old = json.load(open(LOG, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            old = {"runs": []}
        old.setdefault("runs", []).append({
            "at": datetime.now(TZ_TW).isoformat(timespec="seconds"),
            "source": "TWSE MI_INDEX/BWIBBU_d + TPEx 每日收盤行情（官方歷史端點）",
            "results": results,
        })
        with open(LOG, "w", encoding="utf-8") as fh:
            json.dump(old, fh, ensure_ascii=False, indent=2)
        log(f"紀錄寫入 {os.path.relpath(LOG, ROOT)}")
    return 0 if all(r["status"] in ("written", "dry_run", "skipped_exists") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
