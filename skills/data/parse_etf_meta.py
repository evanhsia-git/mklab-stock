#!/usr/bin/env python3
"""
mklab-stock ETF 補充資料解析腳本（半自動，非 GitHub Actions 排程）。

⚠️ 跟 fetch_data.py／fetch_us_data.py 不同，這支腳本**不會自動抓資料**，原因：
  TWSE「ETF 投資篩選器」(https://wwwc.twse.com.tw/zh/ETFortune/products) 和
  TPEx「ETF 投資篩選器」(https://info.tpex.org.tw/ETF/zh/filter.html) 這兩個頁面的
  表格是瀏覽器端 JavaScript 動態載入，沒有找到穩定、允許程式化存取的公開 JSON API；
  兩個網站的使用條款也都有「禁止自動化擷取」的規定，所以本專案不寫爬蟲去抓這兩頁。

  這兩個頁面本身都有「CSV 下載」功能，這是網站主動提供、允許使用者手動匯出的正規
  管道。因此流程改成「半自動」：

    1. 你自己到上面兩個網址，各按一次「CSV 下載」
    2. 把下載下來的兩個檔案分別存成：
         data/raw/twse_etf.csv
         data/raw/tpex_etf.csv
       （檔名固定，直接覆蓋舊檔即可；data/raw/ 只放這種人工匯出的原始檔，
       不會被前端讀取，也不影響任何自動排程）
    3. 執行本腳本，會解析並輸出成 data/etf-meta.json 供前端讀取

  上市/上櫃日期、發行人這類幾乎不會變動的欄位，一次匯出後可以放很久；資產規模、
  受益人數這類會變動的欄位，建議你想更新時再重新下載一次 CSV、重跑本腳本，
  不需要天天做。

用法：
  python3 skills/data/parse_etf_meta.py
"""
import csv
import datetime as dt
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(ROOT, "data", "raw")
OUT_PATH = os.path.join(ROOT, "data", "etf-meta.json")

TWSE_CSV = os.path.join(RAW_DIR, "twse_etf.csv")
TPEX_CSV = os.path.join(RAW_DIR, "tpex_etf.csv")

TWSE_SOURCE_URL = "https://wwwc.twse.com.tw/zh/ETFortune/products"
TPEX_SOURCE_URL = "https://info.tpex.org.tw/ETF/zh/filter.html"


def _clean_sym(raw):
    # CSV 裡代號是 Excel 防止前導零被吃掉的寫法：="00400A"
    return raw.strip().lstrip("=").strip('"')


def _num(raw):
    """把 "61,166,878" / "1,558.45" 這種帶千分位逗號的字串轉成 float；空字串回傳 None。"""
    if raw is None:
        return None
    s = raw.strip().strip('"').replace(",", "")
    if s == "" or s == "-":
        return None
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return None


def parse_twse():
    if not os.path.exists(TWSE_CSV):
        print(f"[parse_etf_meta] 找不到 {TWSE_CSV}，略過 TWSE（見腳本開頭說明如何取得）")
        return []
    with open(TWSE_CSV, encoding="cp950", errors="replace") as f:
        content = f.read()
    lines = [l for l in content.splitlines() if l.strip()]
    # 第 0 行是頁面標題「ETF 投資篩選器」，第 1 行才是真正表頭，資料從第 2 行開始
    reader = csv.reader(lines[1:])
    header = next(reader)
    out = []
    for row in reader:
        if not row or not row[0].strip():
            continue
        sym = _clean_sym(row[0])
        listing_date = row[2].strip().replace(".", "-") if len(row) > 2 and row[2].strip() else None
        out.append({
            "sym": sym,
            "name": row[1].strip() if len(row) > 1 else None,
            "market": "TWSE",
            "listing_date": listing_date,
            "tracking_index": row[3].strip() or None if len(row) > 3 else None,
            "net_assets_100m": _num(row[4]) if len(row) > 4 else None,
            "close": _num(row[5]) if len(row) > 5 else None,
            "avg_value_1m": _num(row[6]) if len(row) > 6 else None,
            "avg_volume": _num(row[7]) if len(row) > 7 else None,
            "beneficiaries": _num(row[8]) if len(row) > 8 else None,
            "issuer": row[9].strip() if len(row) > 9 and row[9].strip() else None,
            "ytd_return_pct": None,
        })
    print(f"[parse_etf_meta] TWSE 解析出 {len(out)} 檔")
    return out


def parse_tpex():
    if not os.path.exists(TPEX_CSV):
        print(f"[parse_etf_meta] 找不到 {TPEX_CSV}，略過 TPEx（見腳本開頭說明如何取得）")
        return []
    with open(TPEX_CSV, encoding="utf-8-sig", errors="replace") as f:
        content = f.read()
    lines = [l for l in content.splitlines() if l.strip()]
    reader = csv.reader(lines)
    header = next(reader)
    out = []
    for row in reader:
        if not row or not row[0].strip():
            continue
        sym = _clean_sym(row[0])
        raw_date = row[2].strip() if len(row) > 2 else ""
        listing_date = None
        if len(raw_date) == 8 and raw_date.isdigit():
            listing_date = f"{raw_date[0:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        out.append({
            "sym": sym,
            "name": row[1].strip() if len(row) > 1 else None,
            "market": "TPEx",
            "listing_date": listing_date,
            "tracking_index": row[3].strip() or None if len(row) > 3 else None,
            "net_assets_100m": _num(row[4]) if len(row) > 4 else None,
            "close": None,
            "avg_value_1m": _num(row[5]) if len(row) > 5 else None,
            "avg_volume": _num(row[6]) if len(row) > 6 else None,
            "beneficiaries": _num(row[7]) if len(row) > 7 else None,
            "ytd_return_pct": _num(row[8]) if len(row) > 8 else None,
            "issuer": row[9].strip() if len(row) > 9 and row[9].strip() else None,
        })
    print(f"[parse_etf_meta] TPEx 解析出 {len(out)} 檔")
    return out


def main():
    twse = parse_twse()
    tpex = parse_tpex()
    etfs = twse + tpex

    if not etfs:
        print("[parse_etf_meta] ❌ 兩邊都沒有可解析的 CSV，未寫入任何檔案")
        return

    doc = {
        "meta": {
            "as_of": dt.datetime.now().strftime("%Y-%m-%d"),
            "source": "TWSE ETF投資篩選器 + TPEx ETF投資篩選器（使用者手動 CSV 匯出，非自動排程）",
            "twse_source_url": TWSE_SOURCE_URL,
            "tpex_source_url": TPEX_SOURCE_URL,
            "count": len(etfs),
            "note": "上市/上櫃日期、發行人為低頻變動欄位；資產規模、受益人數為 CSV 匯出當下的快照值，"
                    "並非即時資料，更新方式見本腳本檔頭說明。",
        },
        "etfs": etfs,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"[parse_etf_meta] ✅ 已寫入 {OUT_PATH}（共 {len(etfs)} 檔，TWSE {len(twse)} + TPEx {len(tpex)}）")


if __name__ == "__main__":
    main()
