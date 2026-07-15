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
     - 免 key（FinMind 匿名登入），台股專用
  2. [備援] yfinance（免 key）
     - 2330.TW 等，讀 balance_sheet / income_stmt 算 ROE/ROA
  3. [預留] TWSE OpenAPI / MOPS 財報端點
     - 本環境直接呼叫回傳空/redirect（需 session/cookie），暫不啟用
     - 端點註解見 fetch_twse_financials()

計算公式（計算式解決方案）：
  ROE (%) = NetIncome / StockholdersEquity * 100
  ROA (%) = NetIncome / TotalAssets        * 100

⚠️ 注意：FinMind 財報為「單季」資料，若需年度 ROE/ROA 應取 TTM（近四季加總淨利）
        或年度財報。本腳本預設取「最新一季」計算，後續可加 --annual 參數擴充。

================================================================================
寫入目標
================================================================================
  /root/Documents/database/tw_stock_all.db
  table: stock_overview
    - roe  欄：UPDATE（若無則 ADD COLUMN）
    - roa  欄：ADD COLUMN roa（本表原無此欄，經 PRAGMA 證實）

================================================================================
用法
================================================================================
  python3 scripts/update_overview.py            # 全量更新（1369 檔，慢）
  python3 scripts/update_overview.py --limit 20 # 只跑前 20 檔（測試）
  python3 scripts/update_overview.py --force    # 強制覆寫既有 roe/roa

注意：本腳本只更新「財務衍生欄位(roe/roa)」，不動收盤價/產業/市值等。
      執行後需再跑 export_db.py 匯出 stocks.json 才會反映到前端。
"""

import argparse
import os
import sqlite3
import sys
import time
import datetime as dt

DB = "/root/Documents/database/tw_stock_all.db"
SLEEP = 0.5  # FinMind 較快，間隔縮短；yfinance 備援時用 1s


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


def get_symbols(conn):
    """從 stock_overview 取出所有代號（數字開頭，台股）"""
    cur = conn.execute("SELECT stock_id FROM stock_overview")
    syms = [r[0] for r in cur.fetchall() if r[0] and r[0][0].isdigit()]
    return syms


def fetch_twse_financials(sym):
    """
    [預留] TWSE/MOPS 財報端點（目前本環境無法直接呼叫，保留擴充）。
    回傳 (net_income, equity, total_assets) 或 None。
    未來啟用方式：
      - TWSE: https://openapi.twse.com.tw/v1/company/BalanceSheet/{sym}?year=&season=
      - MOPS: https://mops.twse.com.tw/mops/web/t146sb05 (POST form)
    """
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

    # 優先順序：FinMind → yfinance → TWSE(預留)
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
    args = ap.parse_args()

    conn = conn_db()
    ensure_columns(conn)
    syms = get_symbols(conn)
    if args.limit:
        syms = syms[: args.limit]
    use_finmind = not args.skip_finmind
    if not use_finmind:
        print("[mode] 跳過 FinMind，純 yfinance 備援")
    print(f"[start] 共 {len(syms)} 檔，force={args.force}，finmind={'on' if use_finmind else 'off'}")

    updated = 0
    finmind_fail_streak = 0
    for i, sym in enumerate(syms):
        try:
            # FinMind 連續失敗 3 次 → 暫時停用（IP 被 limit，避免每檔浪費時間）
            if use_finmind and finmind_fail_streak >= 3:
                use_finmind = False
                print(f"  [warn] FinMind 連續失敗，改用 yfinance 備援")
            did = update_one(conn, sym, force=args.force, use_finmind=use_finmind)
            if did:
                updated += 1
                finmind_fail_streak = 0
            else:
                finmind_fail_streak += 1
        except Exception as e:
            print(f"  [skip] {sym}: {e}")
            finmind_fail_streak += 1
        if (i + 1) % 50 == 0:
            print(f"  [progress] {i + 1}/{len(syms)} 已更新 {updated}")
        time.sleep(SLEEP)

    conn.commit()
    conn.close()
    print(f"[done] 更新 {updated} 檔 ROE/ROA → {DB}")
    print(f"[next] 執行 python3 scripts/export_db.py 匯出 stocks.json 反映前端")


if __name__ == "__main__":
    main()
