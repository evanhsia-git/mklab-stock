#!/usr/bin/env python3
"""
四大指數替代 ETF 的持股自動抓取（GitHub Actions 每日執行）。
流程：依 data/index-proxy.json 逐一嘗試來源 → 解析 → 驗證（檔數範圍、權重加總 90~101%、代號格式）
→ 通過才寫入 data/index-holdings/{基金}.json；任何一步失敗都保留上一版，並在日誌中說明原因。
不寫入假資料。手動檔（manual_upload:）存在時才會使用。
exit code：只要有任一基金「所有來源皆失敗且沒有既有版本」→ 回傳 1（job 變紅），
避免像 2026-11-02 之前那樣產出 0 檔卻仍顯示 success。
驗證門檻由 data/index-proxy.json 逐檔設定：expected_min/max（檔數）與 min_weight_total（權重加總下限，預設 90）。
每個來源也可以寫成物件（{"url": ..., "expected_min": ...}）覆寫門檻，讓「官方完整來源」與「免費部分來源」各自用正確的標準驗證。
"""
import csv, datetime as dt, io, json, os, re, sys, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CFG = os.path.join(ROOT, "data", "index-proxy.json")
OUT_DIR = os.path.join(ROOT, "data", "index-holdings")
UA = {"User-Agent": "Mozilla/5.0 (mklab-stock; GitHub Actions) contact: github.com/evanhsia-git/mklab-stock"}
TZ = dt.timezone(dt.timedelta(hours=8))

def log(msg): print(f"[holdings] {msg}", flush=True)

def _num(v):
    try:
        s = str(v).replace("%", "").replace(",", "").strip()
        return float(s) if s not in ("", "-") else None
    except ValueError:
        return None

def parse_table(rows):
    """rows: 二維列表。找到含 Ticker/Symbol 與 Weight 欄位的表頭，回傳 [(代號, 名稱, 權重%)]。"""
    for i, r in enumerate(rows):
        cells = [str(c).strip() for c in r]
        low = [c.lower() for c in cells]
        t = next((j for j, c in enumerate(low) if c in ("ticker", "symbol")), None)
        w = next((j for j, c in enumerate(low) if "weight" in c or "% of" in c or "% assets" in c), None)
        if t is None or w is None:
            continue
        n = next((j for j, c in enumerate(low) if c in ("name", "holding", "holdings", "security name")), None)
        out = []
        for rr in rows[i + 1:]:
            if not rr or len(rr) <= max(t, w):
                continue
            tk = str(rr[t]).strip().upper()
            wt = _num(rr[w])
            if not tk or wt is None or not re.match(r"^[A-Z][A-Z0-9.\-]{0,6}$", tk):
                continue
            out.append({"ticker": tk, "name": str(rr[n]).strip() if n is not None and len(rr) > n else "", "weight_pct": wt})
        if out:
            return out
    return []

def fetch_bytes(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def load_source(src):
    if src.startswith("manual_upload:"):
        rel = src.split(":", 1)[1]
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            raise FileNotFoundError(f"手動檔不存在：{rel}")
        # 來源字串寫回 repo 相對路徑，不要把機器的絕對路徑（/home/runner/... 或本機路徑）寫進資料檔
        return open(p, "rb").read(), f"manual_upload:{rel}"
    data = fetch_bytes(src)
    return data, src

def manual_source_stale(src, cfg):
    """manual_upload 來源的新鮮度守門：回傳「跳過原因」字串，或 None 表示可用。

    為什麼需要：有些官方檔案（例如 iShares 的 latest-holdings.csv）對資料中心 IP 一律 403
    （Akamai 依來源 IP 判斷，連瀏覽器都擋），CI 永遠拿不到，只能靠人工下載後放進 repo。
    但人工檔會過期：若它排在自動來源前面又沒有期限，就會一直用舊資料、把後面的自動來源擋掉。
    因此給這類來源 max_age_days：超過就跳過（回報原因），讓自動來源接手。
    檔案不存在時也回傳原因（這是可選來源，不該讓它變成每次執行的錯誤）。
    """
    if not src.startswith("manual_upload:"):
        return None
    rel = src.split(":", 1)[1]
    days = float(cfg.get("max_age_days") or 0)
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return f"可選手動檔不存在（{rel}）→ 跳過"
    if days <= 0:
        return None
    age = (dt.datetime.now() - dt.datetime.fromtimestamp(os.path.getmtime(p))).days
    if age > days:
        return f"手動檔已 {age} 天未更新（上限 {days} 天）→ 跳過，改用自動來源"
    return None

def parse_vanguard(doc):
    """Vanguard 發行人端點（https://investor.vanguard.com/irr/funds/profile/{TICKER}-AdditionalFundData）。

    回應是 JSON（約 420KB），持股在 holdingDetails.equityHoldings，每筆有
    ticker / securityLongDescription / marketValuePercentage（字串如 "8.39%"）。
    只取股票部位：shortTermReservesHoldings 是現金與附買回、derivativeHoldings 是期貨／交換，
    都算「成分股與權重」以外的部位，納入會讓權重與檔數失真。
    """
    hd = (doc or {}).get("holdingDetails") or {}
    out = []
    for h in hd.get("equityHoldings") or []:
        tk = str(h.get("ticker") or "").strip().upper()
        wt = _num(h.get("marketValuePercentage"))
        if not tk or wt is None or not re.match(r"^[A-Z][A-Z0-9.\-]{0,6}$", tk):
            continue
        out.append({"ticker": tk, "name": str(h.get("securityLongDescription") or "").strip(),
                    "weight_pct": wt})
    return out

def parse_invesco(doc):
    """Invesco 官方持股 API（dng-api.invesco.com/cache/v1/accounts/en_US/shareclasses/{CUSIP}/holdings/fund）。

    回傳 JSON：{effectiveDate, totalNumberOfHoldings, holdings:[{ticker, issuerName,
    percentageOfTotalNetAssets, securityTypeName, ...}]}。實測 QQQ（CUSIP 46090E103）106 筆、
    其中股票部位 101 檔、權重約 99.8%，且每日更新（不需瀏覽器、免 key）。
    只取股票部位：Currency／Currency Collateral／Synthetic Cash／Index Future 是現金與衍生性部位。
    """
    hlist = (doc or {}).get("holdings")
    if not isinstance(hlist, list):  # TickerInside 的 holdings 是 dict，交給 parse_tickerinside
        return []
    out = []
    for h in hlist:
        if not isinstance(h, dict):
            continue
        tk = str(h.get("ticker") or "").strip().upper()
        wt = _num(h.get("percentageOfTotalNetAssets"))
        st = str(h.get("securityTypeName") or "")
        if not tk or wt is None or not re.match(r"^[A-Z][A-Z0-9.\-]{0,6}$", tk):
            continue
        if st and not ("Common Stock" in st or "Depository Receipt" in st or st == "Equity"):
            continue  # 排除現金、期貨、交換等非股票部位
        out.append({"ticker": tk, "name": str(h.get("issuerName") or "").strip(), "weight_pct": round(wt, 4)})
    return out

def parse_tickerinside(doc):
    """TickerInside 共用備援（https://tickerinside.com/api/v1/fund/{ticker}.json）。

    holdings 是 {代號: 權重%} 的扁平字典（如 {"AMD": 9.2357}）而非陣列，因此 parse_bytes
    必須先問過 parse_invesco（它只吃 list）再交給這裡；若順序顛倒或沒檢查型別，會直接爆
    AttributeError: 'str' object has no attribute 'get'（2026-11-03 實際踩到，SOXX 因此靜默退回備援）。
    source_layer 說明資料來自發行人持股檔（issuer）或 SEC N-PORT 季報（sec_nport）。
    不同 ETF 的新鮮度不同：實測 SOXX／DIA 為 issuer 當期，VOO／QQQ 是 N-PORT（較舊）。
    使用條款要求標註來源，cite_as 是其建議字串（由 source_attribution 取出寫進產出）。
    """
    h = (doc or {}).get("holdings")
    if not isinstance(h, dict):  # 扁平字典才是這個來源；陣列格式交給其他解析器
        return []
    out = []
    for tk, wt in h.items():
        tku = str(tk).strip().upper()
        w = _num(wt)
        if not tku or w is None or not re.match(r"^[A-Z][A-Z0-9.\-]{0,6}$", tku):
            continue
        out.append({"ticker": tku, "name": "", "weight_pct": round(w, 4)})
    return out

def _json_doc(data):
    if data.lstrip()[:1] != b"{":
        return None
    try:
        doc = json.loads(data.decode("utf-8-sig", errors="replace"))
    except Exception:
        return None
    return doc if isinstance(doc, dict) else None

def source_asof(data):
    """來源自帶的持股基準日 → ISO 日期。

    Vanguard holdingDetails.asOfDate（MM/DD/YYYY）、Invesco effectiveDate（ISO）、
    TickerInside holdings_asof（ISO）。月更新或多來源混用的基金必須記錄這個日期，
    否則看不出手上的權重是哪一版（例如 N-PORT 季報與發行人當期資料差好幾個月）。
    """
    doc = _json_doc(data)
    if not doc:
        return None
    s = str((doc.get("holdingDetails") or {}).get("asOfDate") or "").strip()
    if s:
        try:
            return dt.datetime.strptime(s, "%m/%d/%Y").date().isoformat()
        except Exception:
            return None
    for key in ("effectiveDate", "holdings_asof", "as_of"):
        v = str(doc.get(key) or "").strip()
        if v:
            try:
                return dt.date.fromisoformat(v[:10]).isoformat()
            except Exception:
                continue
    return None

def source_attribution(data):
    """來源要求標註的文字（TickerInside 條款要求標明來源，cite_as 為其建議字串）。"""
    doc = _json_doc(data)
    if not doc:
        return None
    cite = str(doc.get("cite_as") or "").strip()
    if cite:
        return cite
    if isinstance(doc.get("holdings"), dict) and doc.get("source_layer"):
        return "TickerInside (tickerinside.com)"
    return None

def parse_bytes(data, src):
    if data.lstrip()[:1] == b"{":  # JSON（Vanguard、Invesco 官方 API、TickerInside 備援）
        doc = json.loads(data.decode("utf-8-sig", errors="replace"))
        for parser in (parse_vanguard, parse_invesco, parse_tickerinside):
            res = parser(doc)
            if res:
                return res
        return []
    if data.lstrip()[:1] == b"<":  # HTML：逐一檢查每個表格
        import pandas as pd
        for t in pd.read_html(io.StringIO(data.decode("utf-8", errors="replace"))):
            res = parse_table([list(t.columns)] + t.fillna("").values.tolist())
            if res:
                return res
        return []
    if src.lower().endswith((".xlsx", ".xls")) or data[:2] == b"PK":
        import pandas as pd
        df = pd.read_excel(io.BytesIO(data), header=None)
        rows = df.fillna("").values.tolist()
    else:
        text = data.decode("utf-8-sig", errors="replace")
        rows = list(csv.reader(io.StringIO(text)))
    return parse_table(rows)

def validate(fund, holdings):
    n = len(holdings)
    if not (fund["expected_min"] <= n <= fund["expected_max"]):
        raise ValueError(f"檔數 {n} 不在預期範圍 {fund['expected_min']}~{fund['expected_max']}")
    total = sum(h["weight_pct"] for h in holdings)
    floor = fund.get("min_weight_total", 90)
    if not (floor <= total <= 101):
        raise ValueError(
            f"權重加總 {total:.2f}% 異常（該基金門檻 {floor}~101%）；"
            "若來源本身只提供部分持股，請在 index-proxy.json 明確設定 min_weight_total，不要放寬全體門檻"
        )
    if len({h['ticker'] for h in holdings}) != n:
        raise ValueError("代號重複")

def main():
    cfg = json.load(open(CFG, encoding="utf-8"))
    os.makedirs(OUT_DIR, exist_ok=True)
    ok = 0
    missing = []  # 連既有版本都沒有 → 真的沒有任何產出，最後讓 exit code 非 0
    for fund in cfg["funds"]:
        key = fund["key"]
        out_path = os.path.join(OUT_DIR, f"{key}.json")
        if fund.get("freq") == "monthly" and os.path.exists(out_path):
            last = json.load(open(out_path, encoding="utf-8")).get("fetched_at", "")[:10]
            if last and (dt.date.today() - dt.date.fromisoformat(last)).days < 25:
                log(f"⏭ {key}：每月更新，{last} 已抓過，略過")
                ok += 1
                continue
        done = False
        for spec in fund["sources"]:
            # 來源可以是字串，也可以是物件（{"url": ..., "expected_min": ...}）以替單一來源覆寫門檻。
            # 例：QQQ 官方 API 提供約 101 檔，免費備援只提供前 25 大 → 兩者門檻必須不同，
            # 否則不是備援永遠失敗，就是部分資料靜默通過驗證。
            src = spec["url"] if isinstance(spec, dict) else spec
            eff = {**fund, **{k: v for k, v in spec.items() if k != "url"}} if isinstance(spec, dict) else fund
            stale = manual_source_stale(src, eff)
            if stale:
                log(f"⏭ {key}：{stale}")
                continue
            try:
                data, used = load_source(src)
                holdings = parse_bytes(data, used)
                validate(eff, holdings)
                doc = {"fund": key, "index": fund["index"], "issuer": fund["issuer"],
                       "count": len(holdings), "source": used,
                       "fetched_at": dt.datetime.now(TZ).isoformat(),
                       "weight_total_pct": round(sum(h["weight_pct"] for h in holdings), 2),
                       "holdings": sorted(holdings, key=lambda h: -h["weight_pct"])}
                asof = source_asof(data)  # 來源自帶的持股基準日（月更新的來源需要知道是哪一版）
                if asof:
                    doc["holdings_asof"] = asof
                attr = source_attribution(data)  # 來源要求標註時一併寫進產出（如 TickerInside 條款）
                if attr:
                    doc["attribution"] = attr
                json.dump(doc, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                log(f"✅ {key}：{len(holdings)} 檔，來源 {used[:90]}")
                ok += 1; done = True
                break
            except Exception as e:
                log(f"⚠️ {key} 來源失敗（{src[:90]}）：{type(e).__name__}: {e}")
        if not done:
            if os.path.exists(out_path):
                log(f"❌ {key}：所有來源皆失敗，保留上一版（有既有資料）")
            else:
                missing.append(key)
                log(f"❌ {key}：所有來源皆失敗且無既有資料 → 這個基金完全沒有產出")
    log(f"完成：{ok}/{len(cfg['funds'])} 檔成功")
    if missing:
        # 過去這裡無條件 return 0，導致「三個來源全掛、目錄 0 檔」的 job 依然顯示 ✅ success，
        # 只能靠人去翻日誌才發現。真的沒有任何產出時必須讓 job 變紅。
        log(f"❌ 完全沒有資料的基金：{', '.join(missing)}")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
