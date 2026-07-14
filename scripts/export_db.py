#!/usr/bin/env python3
"""
mklab-stock 本機 DB 灌種腳本（一次性，僅本機 VPS 執行）。

用途：從本機 SQLite 資料庫 (/root/Documents/database/tw_stock_all.db)
      匯出統一 schema 的 JSON 進 data/，供 GitHub Pages + 未來 GitHub Actions 使用。

產出（與 scripts/fetch_data.py 產出的 schema 完全一致，確保 fork 無縫銜接）：
  data/stocks.json        最新一日全市場個股（含 overview 疊加的 roe/eps/market_cap/industry）
  data/industry.json      33 產業聚合（chg/cnt/top）
  data/history/YYYYMMDD.json  每日切片（259 天），每檔 OHLCV + pe/pb/div + industry
  data/schema-version.json    schema 版號（前端驗證用）

注意：本腳本只在「第一次灌歷史」時由本機執行。之後每日新增由
      GitHub Actions (scripts/fetch_data.py) 在雲端自抓，不依賴本機 DB。
"""
import os, json, sqlite3, sys
from datetime import datetime

DB = "/root/Documents/database/tw_stock_all.db"
OUT = os.path.join(os.path.dirname(__file__), "..", "data")
HIST = os.path.join(OUT, "history")
SCHEMA_VERSION = "1.0.0"

os.makedirs(HIST, exist_ok=True)

def get_db():
    if not os.path.exists(DB):
        sys.exit(f"[ERROR] 本機 DB 不存在: {DB}")
    return sqlite3.connect(DB)

def load_overview(conn):
    """stock_overview: 代號 -> 基本資料（產業/roe/eps/市值等）"""
    cur = conn.execute(
        "SELECT stock_id,stock_name,industry,roe,eps,market_cap,shares_outstanding "
        "FROM stock_overview"
    )
    ov = {}
    for sid, name, ind, roe, eps, mcap, shares in cur.fetchall():
        ov[sid] = {
            "name": name or sid,
            "industry": ind or "未分類",
            "roe": roe,
            "eps": eps,
            "market_cap": mcap,
            "shares": shares,
        }
    return ov

def industry_of(ov, sid):
    return (ov.get(sid) or {}).get("industry", "未分類")

def export_latest(conn, ov):
    """最新一日 = daily_prices 表（總表，最新交易日）"""
    row = conn.execute("SELECT trade_date FROM daily_prices LIMIT 1").fetchone()
    trade_date = row[0] if row else None
    print(f"[latest] trade_date={trade_date}")
    cur = conn.execute(
        "SELECT stock_id,stock_name,close,volume,pe_ratio,pb_ratio,dividend_yield,open,high,low "
        "FROM daily_prices"
    )
    stocks = []
    for sid, name, close, vol, pe, pb, div, o, h, l in cur.fetchall():
        base = ov.get(sid, {})
        stocks.append({
            "sym": sid,
            "name": (name or base.get("name") or sid),
            "price": close,
            "open": o, "high": h, "low": l, "volume": vol,
            "pe": pe, "pb": pb, "div": div,
            "roe": base.get("roe"),
            "eps": base.get("eps"),
            "market_cap": base.get("market_cap"),
            "ind": base.get("industry", "未分類"),
        })
    # 計算漲跌%（與前一日切片比對）
    prev = latest_prev_day(conn, trade_date)
    if prev:
        pmap = {r[0]: r[1] for r in conn.execute(
            f"SELECT stock_id,close FROM daily_prices_{prev}").fetchall()}
        for s in stocks:
            pc = pmap.get(s["sym"])
            if pc and pc != 0:
                s["chg"] = round((s["price"] - pc) / pc * 100, 2)
            else:
                s["chg"] = None
    else:
        for s in stocks:
            s["chg"] = None
    # 綜合評分（簡易：ROE 為主 + 殖利率）
    for s in stocks:
        roe = s.get("roe") or 0
        dv = s.get("div") or 0
        s["rank"] = round(min(100, max(0, roe * 1.5 + dv * 3)), 1)
    meta = {
        "as_of": trade_date,
        "source": "local-db",
        "schema_version": SCHEMA_VERSION,
        "count": len(stocks),
    }
    with open(os.path.join(OUT, "stocks.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "stocks": stocks}, f, ensure_ascii=False)
    print(f"[latest] 匯出 {len(stocks)} 檔 → data/stocks.json")
    return trade_date, stocks

def latest_prev_day(conn, today):
    tbls = [t[0] for t in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'daily_prices_2%'").fetchall()]
    dates = sorted(t.replace("daily_prices_", "") for t in tbls)
    dates = [d for d in dates if d < (today or "99999999")]
    return dates[-1] if dates else None

def export_industry(conn, ov, trade_date):
    """聚合 33 產業（來自 stock_overview.industry）"""
    cur = conn.execute("SELECT stock_id,close FROM daily_prices").fetchall()
    price_map = {r[0]: r[1] for r in cur}
    # 產業 chg：用最新一日切片 vs 前一日
    prev = latest_prev_day(conn, trade_date)
    prev_map = {}
    if prev:
        prev_map = {r[0]: r[1] for r in conn.execute(
            f"SELECT stock_id,close FROM daily_prices_{prev}").fetchall()}
    ind = {}
    for sid, base in ov.items():
        nm = base.get("industry") or "未分類"
        if nm not in ind:
            ind[nm] = {"cnt": 0, "chg_sum": 0.0, "top": None, "top_sym": None}
        rec = ind[nm]
        rec["cnt"] += 1
        cur_p = price_map.get(sid)
        pre_p = prev_map.get(sid)
        if cur_p and pre_p and pre_p != 0:
            c = (cur_p - pre_p) / pre_p * 100
            rec["chg_sum"] += c
            if rec["top"] is None or c > rec["top"]:
                rec["top"] = round(c, 2); rec["top_sym"] = sid
    out = []
    for nm, rec in ind.items():
        avg = round(rec["chg_sum"] / rec["cnt"], 2) if rec["cnt"] else 0.0
        out.append({"nm": nm, "chg": avg, "cnt": rec["cnt"],
                    "top": rec["top"] if rec["top"] is not None else 0.0})
    out.sort(key=lambda x: x["chg"], reverse=True)
    meta = {"as_of": trade_date, "schema_version": SCHEMA_VERSION, "count": len(out)}
    with open(os.path.join(OUT, "industry.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "industry": out}, f, ensure_ascii=False)
    print(f"[industry] 匯出 {len(out)} 產業 → data/industry.json")

def export_history(conn, ov):
    """259 天每日切片 → data/history/YYYYMMDD.json
    注意：部分早期日表缺 open/high/low 欄，需動態偵測避免報錯。"""
    tbls = [t[0] for t in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'daily_prices_2%'").fetchall()]
    dates = sorted(t.replace("daily_prices_", "") for t in tbls)
    print(f"[history] 共 {len(dates)} 個交易日")
    written = 0
    for d in dates:
        tname = f"daily_prices_{d}"
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({tname})").fetchall()}
        has_ohlc = all(c in cols for c in ("open", "high", "low"))
        if has_ohlc:
            cur = conn.execute(
                f"SELECT stock_id,stock_name,close,volume,pe_ratio,pb_ratio,dividend_yield,open,high,low "
                f"FROM {tname}")
        else:
            cur = conn.execute(
                f"SELECT stock_id,stock_name,close,volume,pe_ratio,pb_ratio,dividend_yield "
                f"FROM {tname}")
        rows = []
        for r in cur.fetchall():
            sid, name, close, vol, pe, pb, div = r[0], r[1], r[2], r[3], r[4], r[5], r[6]
            base = ov.get(sid, {})
            rec = {
                "stock_id": sid,
                "stock_name": name or base.get("name") or sid,
                "close": close, "volume": vol,
                "pe_ratio": pe, "pb_ratio": pb, "dividend_yield": div,
                "industry": base.get("industry", "未分類"),
            }
            if has_ohlc:
                rec["open"], rec["high"], rec["low"] = r[7], r[8], r[9]
            else:
                rec["open"], rec["high"], rec["low"] = None, None, None
            rows.append(rec)
        path = os.path.join(HIST, f"{d}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"trade_date": d, "schema_version": SCHEMA_VERSION,
                       "count": len(rows), "stocks": rows}, f, ensure_ascii=False)
        written += 1
    print(f"[history] 寫入 {written} 個切片 → data/history/")

def export_schema():
    with open(os.path.join(OUT, "schema-version.json"), "w", encoding="utf-8") as f:
        json.dump({
            "schema_version": SCHEMA_VERSION,
            "generated": datetime.now().isoformat(timespec="seconds"),
            "description": "mklab-stock data contract (stocks/industry/history)",
            "history_format": "data/history/YYYYMMDD.json → {trade_date, schema_version, count, stocks:[stock_id,stock_name,close,open,high,low,volume,pe_ratio,pb_ratio,dividend_yield,industry]}",
            "stocks_format": "data/stocks.json → {meta:{as_of,source,schema_version,count}, stocks:[sym,name,price,open,high,low,volume,pe,pb,div,roe,eps,market_cap,ind,chg,rank]}",
        }, f, ensure_ascii=False, indent=2)
    print(f"[schema] → data/schema-version.json v{SCHEMA_VERSION}")

def main():
    conn = get_db()
    print(f"[connect] {DB}")
    ov = load_overview(conn)
    print(f"[overview] {len(ov)} 檔基本資料")
    trade_date, _ = export_latest(conn, ov)
    export_industry(conn, ov, trade_date)
    export_history(conn, ov)
    export_schema()
    conn.close()
    print("[done] 灌種完成。可 git add data/ && commit && push")

if __name__ == "__main__":
    main()
