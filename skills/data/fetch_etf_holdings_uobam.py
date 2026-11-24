#!/usr/bin/env python3
"""大華銀投信官方 PCF 申贖組合 → data/etf-holdings.json（官方來源升級）。

來源鏈位置：富邦／元大／國泰／聯邦官方 → **大華銀官方（本腳本）** → CMoney → yfinance。
6 檔標的：00918、009815、009829、00959B、00983B、00984B。

⚠️ TLS 前置條件（2026-11-23）：
  www.uobam.com.tw 的 server 不送中繼憑證（只送 leaf，verify error num=20/21），
  issuer＝Chunghwa Telecom GCC R46 OV TLS CA 2025（GlobalSign 代管）。
  **必須**先取得該中繼憑證並組 CA bundle，本腳本才能跑（禁止 verify=False 進入正式流程）：
    1. 取得中繼憑證 DER/PEM（來源任一）：
       - crt.sh 搜「Chunghwa Telecom GCC R46 OV TLS CA 2025」下載任一未過期者
       - Chrome 開 https://www.uobam.com.tw（Chrome 會 AIA fetching）→ 憑證檢視器匯出中繼
    2. 組 bundle： cat $(python3 -c 'import certifi;print(certifi.where())') 中繼.pem > skills/data/certs/uobam-bundle.pem
    3. bundle 存在才會執行；否則明確退出（不猜測、不關閉驗證）。

資料語意（資料誠信紅線）：PCF＝申贖組合，不等於全部持股；輸出以 items 權重合計（涵蓋率）如實標示。
實測涵蓋率（2026-11-21 基準）：00918 99.76%、009815 98.19%、009829 98.83%、
00959B 98.38%（債券型 73 筆）、00983B 98.80%（40 筆，債）、00984B 98.00%（66 筆，債）。

流程：
  1. 基金 ID 對照（2026-11-23 瀏覽器實測取得，React 下拉 native setter 觸發）：
     00918=88329556、009815=00648622、009829=00719554、00959B=00515073、
     00983B=00580860、00984B=00580854（若失效可從 PCF 頁重新觸發取得）
  2. GET /api/WebSite/pcfexcel/{基金ID}/{YYYYMMDD}（由今天往回試最多 4 天）→ XLSX
  3. 解析持股表（股票：股票代號/名稱/權重/股數；債券：債券代號/名稱/權重/面額）
     + 表頭區官方基本面（淨資產/受益單位/每單位淨值）
  4. 更新 data/etf-holdings.json（src='UOBAM'）

用法：/root/venvs/quant/bin/python3 skills/data/fetch_etf_holdings_uobam.py [--dry-run]
"""
import io
import json
import re
import sys
import time
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOLDINGS_PATH = ROOT / "data" / "etf-holdings.json"
CERT_DIR = ROOT / "skills" / "data" / "certs"
BUNDLE = CERT_DIR / "uobam-bundle.pem"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
BASE = "https://www.uobam.com.tw/api/WebSite"
DELAY = 0.4
BACK_DAYS = 4
ISSUER = "大華銀投信"
FUND_IDS = {
    "00918": "88329556",
    "009815": "00648622",
    "009829": "00719554",
    "00959B": "00515073",
    "00983B": "00580860",
    "00984B": "00580854",
}
CODE_PAT_STOCK = re.compile(r"^[A-Z0-9]{1,6}\s?[A-Z]{2}$|^\d{4}[A-Z]?$|^\d{6}\.?\d*$")
CODE_PAT_BOND = re.compile(r"^US[A-Z0-9]{6,12}$|^[A-Z0-9]{2,5}\s\d")


def load_verify():
    """載入自訂 CA bundle（必須存在——不關閉憑證驗證）。"""
    if not BUNDLE.exists():
        sys.exit(f"[uobam] ❌ 缺中繼憑證 bundle：{BUNDLE}\n"
                 f"  取得方式見本檔 docstring（TLS 前置條件）；取得後組好 bundle 再執行。")
    import certifi
    # bundle 應為 certifi + 中繼；直接回傳路徑
    return str(BUNDLE)


def fetch_excel(fid, verify):
    """由今天往回試日期；回 (bytes, day) 或 (None, None)。"""
    import requests
    today = dt.date.today()
    for back in range(BACK_DAYS):
        day = today - dt.timedelta(days=back)
        try:
            r = requests.get(f"{BASE}/pcfexcel/{fid}/{day.strftime('%Y%m%d')}",
                             headers=UA, timeout=20, verify=verify)
        except requests.exceptions.SSLError as ex:
            print(f"  [warn] SSL：{str(ex)[:60]}——bundle 是否含 R46 中繼？")
            return None, None
        if r.status_code == 200 and len(r.content) > 1500 and r.content[:2] == b"PK":
            return r.content, day
    return None, None


def parse_xlsx(content):
    """解析 PCF Excel → (items, asof, extra, kind)。items=[[代號,名稱,權重,股數/面額],…]"""
    import warnings
    warnings.filterwarnings("ignore")
    import pandas as pd
    df = pd.read_excel(io.BytesIO(content), header=None)
    flat = [[("" if pd.isna(c) else str(c)) for c in row] for row in df.values.tolist()]

    # 表頭列（含「權重」）→ 判斷股票/債券型
    hi, kind = None, None
    for i, row in enumerate(flat):
        joined = " ".join(row)
        if "權重" in joined:
            if "股票代號" in joined:
                kind = "stock"
            elif "債券代號" in joined:
                kind = "bond"
            hi = i
            break
    if hi is None:
        return None, None, None, None

    pat = CODE_PAT_STOCK if kind == "stock" else CODE_PAT_BOND
    items = []
    for row in flat[hi + 1:]:
        code = row[0].strip()
        if not code or not pat.match(code):
            continue
        weight = None
        for cell in row[1:]:
            try:
                v = float(cell.replace("%", "").replace(",", ""))
            except (ValueError, TypeError):
                continue
            if 0 < v < 100:
                weight = v
                break
        if weight is None:
            continue
        qty = None
        for cell in reversed(row[1:]):
            try:
                v = float(cell.replace(",", ""))
            except (ValueError, TypeError):
                continue
            if v > 100:  # 股數/面額量級
                qty = v
                break
        items.append([code, row[1].strip(), weight, int(qty) if qty is not None else None])

    # 官方基本面（表頭區）
    extra = {}
    for row in flat[:12]:
        joined = " ".join(row)
        for key, kw in (("aum", "基金凈資產"), ("units", "已發行受益"), ("nav", "每受益權單")):
            if kw in joined and key not in extra:
                nums = re.findall(r"([\d,]+(?:\.\d+)?)", " ".join(row[1:]))
                if nums:
                    extra[key] = float(nums[-1].replace(",", ""))

    asof = None
    for row in flat[:12]:
        m = re.search(r"(\d{4}/\d{1,2}/\d{1,2})", " ".join(row))
        if m:
            asof = dt.datetime.strptime(m.group(1), "%Y/%m/%d").date().isoformat()
            break
    return items, asof, (extra or None), kind


def validate(sym, items):
    """資料誠信驗證：權重合計 50~105%、重複代號、負值。"""
    codes = [it[0] for it in items]
    if len(codes) != len(set(codes)):
        return False, "重複代號"
    if any(it[3] is not None and it[3] < 0 for it in items):
        return False, "負股數"
    total = sum(it[2] for it in items)
    if not (50 <= total <= 105):
        return False, f"權重合計 {total:.2f}% 超界"
    return True, f"{len(items)} 筆（PCF 申贖組合），權重合計 {total:.2f}%"


def main():
    dry = "--dry-run" in sys.argv
    verify = load_verify()
    import requests  # noqa: F401（延遲載入確認可用）

    with open(HOLDINGS_PATH, encoding="utf-8") as f:
        doc = json.load(f)
    holdings = doc.get("holdings") or {}
    targets = sorted(s for s in FUND_IDS if s in holdings)
    print(f"[uobam] bundle={BUNDLE.exists()}；標的 {len(targets)}/{len(FUND_IDS)}：{targets}")

    ok, fail = [], []
    for i, sym in enumerate(targets, 1):
        content, day = fetch_excel(FUND_IDS[sym], verify)
        items, asof, extra, kind = parse_xlsx(content) if content else (None, None, None, None)
        if not items:
            fail.append(sym)
            print(f"  [{i}/{len(targets)}] {sym}（{FUND_IDS[sym]}）❌ 無 PCF 資料")
            continue
        vok, vmsg = validate(sym, items)
        if not vok:
            fail.append(sym)
            print(f"  [{i}/{len(targets)}] {sym} ❌ 驗證失敗：{vmsg}")
            continue
        ok.append(sym)
        if not dry:
            e = holdings.get(sym) or {}
            holdings[sym] = {
                "name": e.get("name") or "",
                "market": e.get("market") or "TWSE",
                "issuer": ISSUER,
                "n": len(items),
                "src": "UOBAM",
                "asof": asof or (day.isoformat() if day else None),
                "items": items,
                "n_listed": len(items),
                # PCF 同檔官方基本面（供 verify_pcf_nav 交叉核對 TWSE MIS 淨值）
                "aum": (extra or {}).get("aum"),
                "units": (extra or {}).get("units"),
                "nav": (extra or {}).get("nav"),
            }
        print(f"  [{i}/{len(targets)}] {sym} ✅ {vmsg}（{kind}型），asof={asof}，"
              f"官方淨資產={(extra or {}).get('aum')}")
        time.sleep(DELAY)

    print(f"\n[uobam] 成功 {len(ok)}／失敗 {len(fail)}")
    if fail:
        print(f"[uobam] 失敗清單: {fail}")
    if dry:
        print("[uobam] --dry-run：未寫入")
        return 0
    if ok:
        doc["holdings"] = holdings
        from collections import Counter
        src_count = Counter((v or {}).get("src") for v in holdings.values())
        doc.setdefault("meta", {})["src_counts"] = dict(src_count)
        out = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        HOLDINGS_PATH.write_bytes(out)
        print(f"[uobam] ✅ 已寫入 {HOLDINGS_PATH}（{len(out)/1024:.0f} KB），src_counts={dict(src_count)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
