#!/usr/bin/env python3
"""富蘭克林華美投信「基金月報」官方前十大 → data/etf-holdings.json（來源升級）。

來源鏈位置：富邦／元大／國泰／聯邦／大華銀官方 PCF → **FTFT 月報官方 top10（本腳本）** → CMoney top10 → yfinance。
僅對「月報前十大名稱可可靠匹配台股代號」的基金生效（海外型/債券型名稱無可靠市場代號，
匹配率過低時整檔跳過、保留 CMoney——寧缺勿假）。

資料語意（資料誠信紅線）：月報前十大＝官方來源、月底基準（asof＝月報「資料日期」）；
筆數上限 10（非完整持股），涵蓋率無法自月報得知（前十大僅部分覆蓋）——如實以 n≤10 標示。

流程：
  1. GET /official/api/newetf/Fund6/Detail/{1..30} → fileTitle 含「月報」的記錄（fundId → fileUrl）
     （fundId 對照：GET Fund/GetFundId?FtftId={商品頁id}，或本腳本內快照對照）
  2. 下載 PDF → pypdf 抽文字 → 解析「前十大投資標的」表（僅收「… 權重 產業 臺灣」列＝台股型）
  3. 名稱→代號：stocks.json 精確匹配 → 唯一字首匹配（鈊象→鈊象電子）
  4. src='FTFT_MONTHLY'

用法：/root/venvs/quant/bin/python3 skills/data/fetch_etf_holdings_ftft_monthly.py [--dry-run]
注意：需要 requests＋pypdf（quant venv）；pypdf 缺時 sys.exit。
"""
import io
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOLDINGS_PATH = ROOT / "data" / "etf-holdings.json"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
BASE = "https://www.ftft.com.tw"
API = BASE + "/official/api/newetf"
DELAY = 0.5
MIN_MATCH = 5  # 匹配數 <5 → 整檔跳過（保留 CMoney）


def try_import_pypdf():
    try:
        from pypdf import PdfReader
        return PdfReader
    except ImportError:
        sys.exit("需要 pypdf（請用 /root/venvs/quant/bin/python3 執行，或 pip install pypdf）")


def get_monthly_urls():
    """掃檔案記錄 id 1..30 → {fundId: 月報url}。"""
    import requests
    out = {}
    for i in range(1, 31):
        try:
            r = requests.get(f"{API}/Fund6/Detail/{i}", headers=UA, timeout=15)
            if r.status_code != 200 or r.content[:1] != b"{":
                continue
            j = r.json()
            fid, title, url = j.get("fundId"), (j.get("fileTitle") or ""), (j.get("fileUrl") or "")
            if fid and "月報" in title and url:
                out.setdefault(fid, url)
        except Exception:
            pass
        time.sleep(0.15)
    return out


def get_fundid_map():
    """FtftId（商品頁 id）→ fundId → ETF 代號（014 對照由 GetFundId 取得）。"""
    import requests
    # 商品頁 id ↔ 代號（2026-11-23 實測；官網改版時以 etf/product 頁重新對照）
    ftft_ids = {"00899": 130, "00905": 131, "00961": 162, "00982B": 173, "00986B": 176, "009831": 191}
    out = {}
    for sym, ftid in ftft_ids.items():
        try:
            r = requests.get(f"{API}/Fund/GetFundId", params={"FtftId": ftid}, headers=UA, timeout=15)
            j = r.json()
            if j.get("fundId"):
                out[sym] = j["fundId"]
        except Exception:
            pass
        time.sleep(0.15)
    return out


def parse_top10_text(full, name_map):
    """解析月報文字 → (items, asof, stats)。items=[[代號,名稱,權重],…]（僅臺灣列）。"""
    i = full.find("前十大")
    if i < 0:
        return None, None, {"reason": "月報無前十大表"}
    seg = full[i:i + 800]
    dm = re.search(r"資料日期[：:]\s*(\d{4})/(\d{1,2})/(\d{1,2})", full)
    asof = None
    if dm:
        asof = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"

    # 列模式：名稱 權重 產業 臺灣（海外/債券列國家非臺灣，自動排除）
    rows = re.findall(r"([^\s0-9][^\s]{1,14})\s+([\d.]{1,6})\s+[^\s]{2,12}\s+臺灣", seg)
    items, unmatched = [], []
    for name, w in rows:
        try:
            weight = float(w)
        except ValueError:
            continue
        if not (0 < weight < 100) or len(items) >= 10:
            continue
        code = name_map.get(name)
        if code is None:
            # 唯一字首匹配（月報簡稱 vs 證券全名：鈊象→鈊象電子）
            cands = [s for n, s in name_map.items() if n.startswith(name)]
            code = cands[0] if len(cands) == 1 else None
        if code is None:
            unmatched.append(name)
            continue
        items.append([code, name, weight])
    return items, asof, {"unmatched": unmatched, "total_rows": len(rows)}


def parse_top10(pdf_bytes, name_map):
    """PDF → 文字 → parse_top10_text。"""
    PdfReader = try_import_pypdf()
    rd = PdfReader(io.BytesIO(pdf_bytes))
    full = "\n".join((p.extract_text() or "") for p in rd.pages)
    return parse_top10_text(full, name_map)


def main():
    dry = "--dry-run" in sys.argv
    with open(HOLDINGS_PATH, encoding="utf-8") as f:
        doc = json.load(f)
    holdings = doc.get("holdings") or {}
    stocks = json.load(open(ROOT / "data" / "stocks.json", encoding="utf-8"))["stocks"]

    # 名稱→代號 map（全證券；同名取先者，台股為主）
    name_map = {}
    for r in stocks:
        nm = (r.get("name") or "").strip()
        if nm:
            name_map.setdefault(nm, r["sym"])

    fids = get_fundid_map()
    urls = get_monthly_urls()
    print(f"[ftft-monthly] fundId 對照 {len(fids)} 檔；月報 {len(urls)} 份")

    ok, fail = [], []
    for sym, fid in sorted(fids.items()):
        url = urls.get(fid)
        cur = (holdings.get(sym) or {})
        if cur.get("src") not in ("CMONEY", "YFINANCE", "", None):
            print(f"  {sym}: 既有 src={cur.get('src')}（非備援），不覆蓋")
            continue
        if not url:
            fail.append(sym)
            print(f"  {sym}（fundId={fid}）❌ 無月報記錄")
            continue
        import requests
        r = requests.get(url, headers=UA, timeout=30)
        if r.status_code != 200 or r.content[:4] != b"%PDF":
            fail.append(sym)
            print(f"  {sym} ❌ 月報下載失敗 HTTP {r.status_code}")
            continue
        items, asof, stats = parse_top10(r.content, name_map)
        if not items or len(items) < MIN_MATCH:
            fail.append(sym)
            print(f"  {sym} ⏭ 匹配不足（{len(items or [])} 筆<{MIN_MATCH}，unmatched={stats.get('unmatched')}）→ 保留 {cur.get('src')}")
            continue
        ok.append(sym)
        if not dry:
            holdings[sym] = {
                "name": cur.get("name") or "",
                "market": cur.get("market") or "TWSE",
                "issuer": cur.get("issuer") or "富蘭克林華美投信",
                "n": len(items),
                "src": "FTFT_MONTHLY",
                "asof": asof,
                "items": items,
                "n_listed": len(items),
            }
        print(f"  {sym} ✅ 官方前十大 {len(items)} 筆（匹配自月報），asof={asof}，"
              f"unmatched={stats.get('unmatched') or '無'}")
        time.sleep(DELAY)

    print(f"\n[ftft-monthly] 升級 {len(ok)}／跳過 {len(fail)}")
    if dry:
        print("[ftft-monthly] --dry-run：未寫入")
        return 0
    if ok:
        doc["holdings"] = holdings
        from collections import Counter
        src_count = Counter((v or {}).get("src") for v in holdings.values())
        doc.setdefault("meta", {})["src_counts"] = dict(src_count)
        doc["meta"]["note"] = doc["meta"].get("note", "") + " FTFT_MONTHLY＝富蘭克林華美基金月報官方前十大（月底基準，台股名稱匹配代號，海外/債券型月報名稱無可靠代號故保留 CMoney）。"
        out = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        HOLDINGS_PATH.write_bytes(out)
        print(f"[ftft-monthly] ✅ 已寫入 {HOLDINGS_PATH}（{len(out)/1024:.0f} KB），src_counts={dict(src_count)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
