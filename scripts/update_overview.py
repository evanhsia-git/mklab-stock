#!/usr/bin/env python3
"""
update_overview.py — 本機 DB 補齊 ROE / ROA（寫回 tw_stock_all.db）

================================================================================
資料源優先順序（用戶最高原則：TWSE / TPEX 為主，抓不到才用 yfinance）
================================================================================
  1. [主源-首選] FinMind（台灣證交所授權資料，本土最權威）
     - taiwan_stock_balance_sheet → 權益總計 / 資產總額
     - taiwan_stock_financial_statement → 本期淨利
     - 計算：ROE = 淨利 / 權益總計 * 100；ROA = 淨利 / 資產總額 * 100
  2. [備援] yfinance（免 key）
     - 2330.TW 等，讀 balance_sheet / income_stmt 算 ROE/ROA
  3. [預留] TWSE OpenAPI / MOPS 財報端點
     - 本環境直接呼叫回傳空/redirect（需 session/cookie），暫不啟用

計算公式（計算式解決方案）：
  ROE (%) = NetIncome / StockholdersEquity * 100
  ROA (%) = NetIncome / TotalAssets        * 100

⚠️ FinMind 現狀（2026-07-15 實測）：匿名模式被 IP rate-limit（每 3-4 檔鎖）；
   環境變數 FINMIND_TOKEN 過期（Token is illegal）。故當前實際只用 yfinance。
   腳本會自動偵測 FinMind 連續失敗並降級到 yfinance，無需手動指定。

================================================================================
寫入目標
================================================================================
  /root/Documents/database/tw_stock_all.db
  table: stock_overview
    - roe  欄：UPDATE（若無則 ADD COLUMN）
    - roa  欄：ADD COLUMN roa（本表原無此欄，經 PRAGMA 證實）

================================================================================
用法（手動一次補完）
================================================================================
  python3 scripts/update_overview.py                 # 全量補齊（缺失的才抓）
  python3 scripts/update_overview.py --force         # 強制覆寫所有 roe/roa
  python3 scripts/update_overview.py --skip-finmind  # 跳過 FinMind（純 yfinance）

================================================================================
用法（cron 自動化 / 每日排程）
================================================================================
  # 每日增量：只補「還沒值」的檔，跑完即退（適合系統 crontab / Hermes cron）
  python3 scripts/update_overview.py --cron

  # 每日限量分批：每天最多抓 200 檔（避免 yfinance 被 ban，慢慢補到滿）
  python3 scripts/update_overview.py --cron --daily-limit 200

  # 排程範例（每週六 03:00 跑，與雲端 weekly-roe 同頻率）：
  # 0 3 * * 6 cd /root/Documents/mklab-stock && python3 scripts/update_overview.py --cron >> /var/log/mklab_roa.log 2>&1

注意：本腳本只更新「財務衍生欄位(roe/roa)」，不動收盤價/產業/市值等。
      執行後需再跑 export_db.py 匯出 stocks.json 才會反映到前端。
"""

import argparse
import json
import os
import sqlite3
import sys
import time
import datetime as dt

DB = "/root/Documents/database/tw_stock_all.db"
SLEEP = 1.0  # yfinance 備援時每檔間隔（防 ban）


def conn_db():
    if not os.path.exists(DB):
        sys.exit(f"[ERROR] 本機 DB 不存在: {DB}")
    return sqlite3.connect(DB)


def ensure_columns(conn):
    """確保 stock_overview 有 roe / roa 欄位（無則新增）"""
    cur = conn.execute("PRAGMA table_info(stock_overview)")
    cols = [r[1] for r in cur.fetchall()]
    if "roe" not in cols:
        print("[schema] ADD COLUMN roe")
        conn.execute("ALTER TABLE stock_overview ADD COLUMN roe REAL")
    if "roa" not in cols:
        print("[schema] ADD COLUMN roa")
        conn.execute("ALTER TABLE stock_overview ADD COLUMN roa REAL")
    conn.commit()


def get_symbols(conn, incremental=False, daily_limit=0, skip_etf=True):
    """
    從 stock_overview 取出候選代號。
    - incremental: 只取「roe 或 roa 為 null」的（cron 模式預設）
    - skip_etf: 排除 yfinance 無財報的類型（含字母尾碼如 00400A、末碼 T/B/D 等）
    - daily_limit: 限制回傳數量（分批用）
    """
    if incremental:
        cur = conn.execute(
            "SELECT stock_id FROM stock_overview WHERE roe IS NULL OR roa IS NULL"
        )
    else:
        cur = conn.execute("SELECT stock_id FROM stock_overview")
    syms = [r[0] for r in cur.fetchall() if r[0] and r[0][0].isdigit()]

    if skip_etf:
        # ETF 代號特徵：第 5-6 碼含字母（00400A）、末碼 T/B/D（平衡/債券 ETF）
        def is_etf(s):
            return any(c.isalpha() for c in s[4:]) or s[-1] in ("T", "B", "D")
        syms = [s for s in syms if not is_etf(s)]

    if daily_limit:
        syms = syms[:daily_limit]
    return syms


def fetch_twse_financials(sym):
    """[預留] TWSE/MOPS 財報端點（目前本環境無法直接呼叫，保留擴充）。"""
    return None


def fetch_finmind(sym):
    """FinMind 主源：抓資產負債表 + 財務報表，算 ROE/ROA。回傳 dict 或 None"""
    try:
        from FinMind.data import DataLoader
    except ImportError:
        return None
    try:
        dl = DataLoader()
        bs = dl.taiwan_stock_balance_sheet(stock_id=sym, start_date="20240101")
        fs = dl.taiwan_stock_financial_statement(stock_id=sym, start_date="20240101")
        if bs is None or len(bs) == 0 or fs is None or len(fs) == 0:
            return None

        def latest_val(df, keys):
            d = df[df["date"] == df["date"].max()]
            for k in keys:
                r = d[d["origin_name"].str.contains(k, na=False)]
                if len(r):
                    return float(r["value"].iloc[0])
            return None

        equity = latest_val(bs, ["權益總計", "股東權益總額", "權益總額"])
        assets = latest_val(bs, ["資產總額", "資產總計"])
        ni = latest_val(fs, ["本期淨利", "稅後淨利", "本期綜合損益總額"])

        rec = {}
        if ni is not None and equity is not None and equity != 0:
            rec["roe"] = round(ni / equity * 100, 2)
        if ni is not None and assets is not None and assets != 0:
            rec["roa"] = round(ni / assets * 100, 2)
        return rec if rec else None
    except Exception as e:
        print(f"  [finmind] {sym} 失敗: {e}")
        return None


def fetch_yfinance(sym):
    """yfinance 備援：讀 balance_sheet / income_stmt，算 ROE/ROA"""
    try:
        import yfinance as yf
    except ImportError:
        return None
    try:
        t = yf.Ticker(f"{sym}.TW")
        bs = t.balance_sheet
        is_ = t.income_stmt
        if bs is None or bs.empty or is_ is None or is_.empty:
            return None
        col = bs.columns[0]
        ni = is_.loc["Net Income", col] if "Net Income" in is_.index else None
        eq = bs.loc["Stockholders Equity", col] if "Stockholders Equity" in bs.index else None
        ta = bs.loc["Total Assets", col] if "Total Assets" in bs.index else None
        rec = {}
        if ni is not None and eq is not None and eq != 0:
            rec["roe"] = round(float(ni) / float(eq) * 100, 2)
        if ni is not None and ta is not None and ta != 0:
            rec["roa"] = round(float(ni) / float(ta) * 100, 2)
        return rec if rec else None
    except Exception as e:
        print(f"  [yf] {sym} 失敗: {e}")
        return None


def update_one(conn, sym, force=False, use_finmind=True):
    """單檔更新：FinMind 主源 → yfinance 備援 → TWSE 預留。回傳 bool 是否更新"""
    cur = conn.execute("SELECT roe, roa FROM stock_overview WHERE stock_id=?", (sym,))
    row = cur.fetchone()
    has_roe, has_roa = (row[0] is not None), (row[1] is not None)
    if not force and has_roe and has_roa:
        return False  # 已有，跳過

    rec = fetch_finmind(sym) if use_finmind else None
    if rec is None:
        rec = fetch_yfinance(sym)
    if rec is None:
        rec = fetch_twse_financials(sym)
    if not rec:
        return False

    conn.execute(
        "UPDATE stock_overview SET roe=?, roa=? WHERE stock_id=?",
        (rec.get("roe"), rec.get("roa"), sym),
    )
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 檔（測試）")
    ap.add_argument("--force", action="store_true", help="強制覆寫既有 roe/roa")
    ap.add_argument("--skip-finmind", action="store_true", help="跳過 FinMind（當 IP 被 limit 時用 yfinance）")
    ap.add_argument("--cron", action="store_true", help="cron 模式：增量補齊 + JSON log + exit code")
    ap.add_argument("--daily-limit", type=int, default=0, help="每日限量（cron 分批用，0=不限制）")
    ap.add_argument("--no-skip-etf", action="store_true", help="不排除 ETF（預設排除，因 yfinance 無 ETF 財報）")
    args = ap.parse_args()

    incremental = args.cron  # cron 模式預設增量
    skip_etf = not args.no_skip_etf

    conn = conn_db()
    ensure_columns(conn)
    syms = get_symbols(conn, incremental=incremental, daily_limit=args.daily_limit, skip_etf=skip_etf)
    if args.limit:
        syms = syms[: args.limit]
    use_finmind = not args.skip_finmind
    if not use_finmind:
        print("[mode] 跳過 FinMind，純 yfinance 備援")
    mode_desc = "cron增量" if incremental else "全量"
    print(f"[start] 模式={mode_desc} 共 {len(syms)} 檔，force={args.force}，finmind={'on' if use_finmind else 'off'}")

    updated = 0
    skipped_existing = 0
    failed = 0
    finmind_fail_streak = 0
    for i, sym in enumerate(syms):
        try:
            if use_finmind and finmind_fail_streak >= 3:
                use_finmind = False
                print(f"  [warn] FinMind 連續失敗，改用 yfinance 備援")
            did = update_one(conn, sym, force=args.force, use_finmind=use_finmind)
            if did:
                updated += 1
                finmind_fail_streak = 0
            else:
                skipped_existing += 1
        except Exception as e:
            print(f"  [skip] {sym}: {e}")
            failed += 1
        if (i + 1) % 50 == 0:
            print(f"  [progress] {i + 1}/{len(syms)} 已更新 {updated}")
        time.sleep(SLEEP)

    conn.commit()
    conn.close()

    result = {
        "mode": mode_desc,
        "total": len(syms),
        "updated": updated,
        "skipped_existing": skipped_existing,
        "failed": failed,
        "finmind_used": use_finmind,
        "timestamp": dt.datetime.now().isoformat(),
    }
    if args.cron:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"[done] 更新 {updated} 檔 ROE/ROA → {DB}")
        print(f"[next] 執行 python3 scripts/export_db.py 匯出 stocks.json 反映前端")

    # exit code: 0=成功（含跳過已有）, 1=有失敗需檢查
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
