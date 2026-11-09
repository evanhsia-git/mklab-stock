#!/usr/bin/env python3
"""
fetch_twii_long.py — 台股加權指數（^TWII）長期日 K 線，產出 data/twii-long.json

用途：digest 頁「大盤重大事件時間軸」需要長期大盤資料（如 2000、2008、2020 股災）。
      repo 內原本只有近 260 個交易日的 data/twii_kdata.js，這支腳本補上完整歷史。

執行（本機一次性，或需要更新時手動執行）：
    pip install yfinance --break-system-packages
    python skills/data/fetch_twii_long.py                # 預設自 1997-07-01 起
    python skills/data/fetch_twii_long.py --start 2000-01-01
然後 commit data/twii-long.json 即可。前端會自動優先使用此檔，再以近期 twii_kdata.js 補齊。

輸出格式（與 data/kline/*.json 相同欄位順序）：
    {"meta": {...}, "rows": [[日期, 開, 高, 低, 收], ...]}
注意：yfinance 為非官方來源，請以交易所資料為最終依據。
"""
import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "twii-long.json"
TZ_TW = timezone(timedelta(hours=8))


def main():
    ap = argparse.ArgumentParser(description="下載台股加權指數長期日 K 線")
    ap.add_argument("--start", default="1997-07-01", help="起始日 YYYY-MM-DD")
    ap.add_argument("--symbol", default="^TWII")
    args = ap.parse_args()

    try:
        import yfinance as yf
    except ImportError:
        print("缺少 yfinance，請先執行：pip install yfinance --break-system-packages", file=sys.stderr)
        return 1

    df = yf.download(args.symbol, start=args.start, auto_adjust=False, progress=False)
    if df is None or df.empty:
        print("下載失敗或沒有資料，未覆寫既有檔案。", file=sys.stderr)
        return 2

    # yfinance 新版為多層欄位（Price, Ticker），統一取單層欄位名
    if hasattr(df.columns, "levels"):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    rows = []
    for idx, r in df.iterrows():
        vals = [r.get("Open"), r.get("High"), r.get("Low"), r.get("Close")]
        if any(v is None or v != v for v in vals):  # None 或 NaN
            continue
        rows.append([
            idx.strftime("%Y-%m-%d"),
            round(float(vals[0]), 2), round(float(vals[1]), 2),
            round(float(vals[2]), 2), round(float(vals[3]), 2),
        ])

    doc = {
        "meta": {
            "symbol": args.symbol,
            "source": "yfinance（非官方來源；僅供研究參考）",
            "start": rows[0][0] if rows else None,
            "end": rows[-1][0] if rows else None,
            "count": len(rows),
            "fields": ["date", "open", "high", "low", "close"],
            "generated_at": datetime.now(TZ_TW).isoformat(timespec="seconds"),
        },
        "rows": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"已寫入 {OUT}（{len(rows)} 筆，{doc['meta']['start']} ～ {doc['meta']['end']}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
