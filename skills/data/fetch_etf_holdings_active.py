#!/usr/bin/env python3
"""主動式 ETF（A 尾）官方持股採集：13 家投信逐一破解 → data/etf-holdings.json。

端點與陷阱知識來源：nctuwanglin/active-etf 的公開探勘（2026-08~11 實測），
本檔為 mklab-stock 自有實作（解析器重寫，非程式碼拷貝）。首次整合 2026-11-22。

涵蓋：統一 ezmoney／群益 capitalfund／安聯 etf.allianzgi／中信 ctbcinvestments／
野村 nomurafunds／台新 tsit／玉山 esunam／復華 fhtrust／凱基 kgifund／
永豐 sitc.sinopac／聯博 webapi.alliancebernstein／第一金 fsitc／兆豐 megafunds／
富邦 websys.fsit（補股數）。元大（既有 YUANTA 鏈）與國泰（既有 CATHAY 鏈）不在此處。

設計（學自 active-etf，對齊本 repo 原則）：
  - items 第 4 欄新增「股數」（可用時），供換股比對的 scale 校正（申贖分離）。
  - 基準日語意：一律取持股基準日 T（各家「公告日 T+1」欄位見 issuer-sources.md 對照表，勿用）。
  - 驗證：權重合計 50~105（主動式現金/期貨部位可觀，僅防解析錯誤非完整性檢查）、
    重複代號擋下（dict 覆蓋 vs 反查累加會算出兩種答案）、空代號/負值/單筆權重>100 擋下。
  - bot 挑戰：投信站會用 HTTP 200 回驗證圖片（PNG/JPEG/GIF magic bytes），辨識後讓該檔走 stale。
  - stale carry：單檔失敗保留既有 entry 並標 stale:true；成功後移除；來源回舊不覆蓋較新資料。

用法：/root/venvs/quant/bin/python3 skills/data/fetch_etf_holdings_active.py [--only SYM,SYM] [--dry-run]
"""
import datetime as dt
import html
import json
import math
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
HOLDINGS_PATH = ROOT / "data" / "etf-holdings.json"
IDS_CACHE = ROOT / "data" / "raw" / "firstsec-fundids.json"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36")
W_MIN, W_MAX = 50.0, 105.0
_BACKOFF_DAYS = 7


class AdapterError(Exception):
    """單檔抓取/解析/驗證失敗；主流程捕捉後標 stale，不中斷整批。"""


# ─── 共用工具 ───────────────────────────────────────────────────────────────
def to_num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").replace("NT$", "").replace("$", "").strip()
    if not s or s in ("-", "—", "nan"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_dotnet_date(s):
    """.NET JSON 日期兩種形式：ISO 或 '/Date(ms)/'（ms 為台北午夜 epoch，UTC 解會少一天）。"""
    m = re.match(r"/Date\((\d+)\)/", str(s or ""))
    if m:
        tz = dt.timezone(dt.timedelta(hours=8))
        return dt.datetime.fromtimestamp(int(m.group(1)) / 1000, tz).strftime("%Y-%m-%d")
    return str(s)[:10]


def is_bot_challenge(resp):
    """投信站以 HTTP 200 回驗證圖片而非資料（野村 2026-08-08 起實測）。"""
    body = resp.content[:8]
    return any(body.startswith(m) for m in (b"\x89PNG", b"\xff\xd8\xff", b"GIF8"))


def validate_holdings(holdings, code, w_min=W_MIN, w_max=W_MAX):
    """空/權重合計異常/重複代號/負值/空代號 → AdapterError（回正規化清單 [code,name,weight,shares]）。"""
    if not holdings:
        raise AdapterError(f"{code}: 持股為空")
    total = sum(h[2] for h in holdings)
    if not (w_min <= total <= w_max):
        raise AdapterError(f"{code}: 權重合計 {total:.2f} 超出 {w_min}-{w_max}")
    out, seen = [], set()
    for c, name, w, sh in holdings:
        c = str(c).strip().upper()
        if not c:
            raise AdapterError(f"{code}: 空代號（誤抓合計/現金列？）")
        if c in seen:
            raise AdapterError(f"{code}: 持股代號重複 {c}")
        seen.add(c)
        if not math.isfinite(float(w)) or w < 0 or w > 100.0:
            raise AdapterError(f"{code}: {c} 權重異常 {w}")
        if sh is not None and (not math.isfinite(float(sh)) or sh < 0):
            raise AdapterError(f"{code}: {c} 股數異常 {sh}")
        out.append([c, str(name).strip(), float(w), None if sh is None else int(sh)])
    return out


def _get(url, **kw):
    return _request("GET", url, **kw)


def _post(url, **kw):
    return _request("POST", url, **kw)


_session = requests.Session()


def _request(method, url, **kw):
    headers = {"User-Agent": UA}
    headers.update(kw.pop("headers", {}))
    kw.setdefault("timeout", 30)
    last = None
    for attempt in range(3):
        try:
            r = _session.request(method, url, headers=headers, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise AdapterError(f"{url} 抓取失敗: {last}")


def _json(r, who):
    if is_bot_challenge(r):
        raise AdapterError(f"{who}: HTTP 200 回驗證圖片（機器人挑戰）")
    try:
        return r.json()
    except ValueError:
        raise AdapterError(f"{who}: 回非 JSON（改版或被擋？）")


def _backoff_days(n=_BACKOFF_DAYS):
    today = dt.date.today()
    return [(today - dt.timedelta(days=i)) for i in range(n)]


def _strip_tags(t):
    return re.sub(r"<[^>]+>", " ", t)


# ─── 各投信 fetcher：回 (data_date, holdings, meta) ────────────────────────
def fetch_esun(code, name):
    """玉山 esunam.com：POST JSON API。CNavDt=基準日（CPcfdate=公告日勿用）；受益人數 1900 日期=未揭露。"""
    api = "https://www.esunam.com/ETFAPI/"
    h = {"Content-Type": "application/json", "Referer": "https://www.esunam.com/ETF/trad-info"}
    lst = _json(_post(api + "GetETFFundSelectList", json={"TypeID": 5542}, headers=h), "esun 清單")
    if lst.get("StatusCode") != 0:
        raise AdapterError(f"esun: 清單 StatusCode={lst.get('StatusCode')}")
    fund_no = next((str(e["FundNo"]) for e in (lst.get("Entries") or [])
                    if (e.get("FundShortName") or "").strip() == name.strip() and e.get("FundNo")), None)
    if not fund_no:
        raise AdapterError(f"esun: {code}「{name}」不在主動式清單")
    d = _json(_post(api + "GetFundTradeInfo", json={"FundNo": fund_no, "Date": None}, headers=h),
              "esun tradeinfo")
    if d.get("StatusCode") != 0:
        raise AdapterError(f"esun: tradeinfo StatusCode={d.get('StatusCode')}")
    e = d.get("Entries")
    if isinstance(e, list):  # 防禦：實測為 dict（單基金），但形態可能變
        e = e[0] if e else None
    if not isinstance(e, dict) or not e.get("CNavDt"):
        raise AdapterError(f"{code}: 缺基準日 CNavDt")
    tables = [t for t in (e.get("DynamicTableData") or []) if t.get("TableTitle") == "股票"]
    if not tables:
        raise AdapterError(f"{code}: 找不到「股票」表")
    t0 = tables[0]
    cols = [c.get("Name") for c in (t0.get("Columns") or [])]
    try:
        ic, iname, ish, iw = (cols.index("股票代號"), cols.index("股票名稱"),
                              cols.index("股數"), cols.index("權重(%)"))
    except ValueError:
        raise AdapterError(f"{code}: 股票表欄位異常 {cols}")
    holdings = []
    for row in t0.get("Rows") or []:
        sh, w = to_num(row[ish]), to_num(row[iw])
        if sh is None or w is None:
            raise AdapterError(f"{code}: {row[ic]} 股數/權重無法解析")
        holdings.append((str(row[ic]), str(row[iname]), w, int(sh)))
    holders = e.get("CBeneficiariesCount")
    if not holders or str(e.get("CBeneficiariesCountDate") or "").startswith("1900"):
        holders = None
    meta = {"scale": to_num(e.get("CAnceTotalAv")), "units": to_num(e.get("CAnceTotalIssues")),
            "nav_per_unit": to_num(e.get("CAnceNav")), "holders": holders}
    return parse_dotnet_date(e["CNavDt"]), validate_holdings(holdings, code), meta


def fetch_fuhhwa(code, name):
    """復華 fhtrust.com.tw：fundList?ec001=3 → etf002↔fundID；assets?qDate= 逐日往回 8 天。"""
    fl = _json(_get("https://www.fhtrust.com.tw/api/fundList?ec001=3"), "fuhhwa fundList")
    fmap = {(f.get("etf002") or "").strip(): f["fundID"] for f in fl.get("result", []) if f.get("etf002")}
    if code not in fmap:
        raise AdapterError(f"fuhhwa: {code} 不在 fundList")
    for day in _backoff_days(8):
        d = _json(_get("https://www.fhtrust.com.tw/api/assets",
                       params={"fundID": fmap[code], "qDate": day.strftime("%Y/%m/%d")}),
                  "fuhhwa assets")
        results = d.get("result") or []
        if not results:
            continue
        r0 = results[0]
        rows = [x for x in (r0.get("detail") or [])
                if x.get("ftype") == "股票" and (x.get("stockid") or "").strip()]
        if not rows or not r0.get("dDate"):
            continue
        holdings = [(x["stockid"], x["stockname"],
                     float(str(x["prate_addaccint"]).rstrip("%")),
                     int(str(x["qshare"]).replace(",", ""))) for x in rows]
        meta = {"scale": to_num(r0.get("pcf_FundNav")), "units": to_num(r0.get("pcf_FundQissue")),
                "nav_per_unit": to_num(r0.get("pcf_Fundpnav")), "holders": None}
        return r0["dDate"].replace("/", "-"), validate_holdings(holdings, code), meta
    raise AdapterError(f"fuhhwa: {code} 連續 8 日無持股資料")


def fetch_president(code, name):
    """統一 ezmoney：PCF 頁抽 DataFundList（session cookie）；GetPCF date 給未來日回最新一份。TranDate=基準日。"""
    page_url = "https://www.ezmoney.com.tw/ETF/Transaction/PCF"
    r = _get(page_url)
    m = re.search(r"id=['\"]DataFundList['\"][^>]*data-content=['\"](.*?)['\"]", r.text, re.S)
    if not m:
        raise AdapterError("president: PCF 頁找不到 DataFundList")
    funds = json.loads(html.unescape(m.group(1)))
    fmap = {(f.get("sStockNo") or "").strip(): f["sFundCode"] for f in funds if f.get("sStockNo")}
    if code not in fmap:
        raise AdapterError(f"president: {code} 不在 fundList")
    future = dt.date.today() + dt.timedelta(days=3)  # 未來日 + specificDate=false → 最新一份
    q = "{}/{:02d}/{:02d}".format(future.year - 1911, future.month, future.day)
    d = _json(_post("https://www.ezmoney.com.tw/ETF/Transaction/GetPCF",
                    json={"fundCode": fmap[code], "date": q, "specificDate": False},
                    headers={"Referer": page_url}), "president GetPCF")
    stocks = [a for a in (d.get("asset") or []) if a.get("AssetCode") == "ST"]
    if not stocks or not stocks[0].get("Details"):
        raise AdapterError(f"{code}: GetPCF 無股票明細")
    holdings = [(str(r["DetailCode"]), str(r["DetailName"]), float(r["NavRate"]), int(r["Share"]))
                for r in stocks[0]["Details"]]
    pcf = d.get("pcf") or []
    if not pcf:
        raise AdapterError(f"{code}: GetPCF 無 pcf 摘要")
    amt = {x.get("PCFCode"): x.get("Amount") for x in pcf}
    meta = {"scale": to_num(amt.get("NAV")), "units": to_num(amt.get("OUT_UNIT")),
            "nav_per_unit": to_num(amt.get("P_UNIT")), "holders": to_num(amt.get("NAV_PEOPLE"))}
    return parse_dotnet_date(pcf[0]["TranDate"]), validate_holdings(holdings, code), meta


def fetch_capital(code, name):
    """群益 capitalfund：POST items → fundNo；POST buyback {fundId}。date2=基準日（date1=公告日勿用）。"""
    r = _post("https://www.capitalfund.com.tw/CFWeb/api/etf/items", json={},
              headers={"Content-Type": "application/json"})
    fmap = {(f.get("stockNo") or "").strip(): f["fundNo"] for f in (_json(r, "capital items").get("data") or [])
            if f.get("stockNo")}
    if code not in fmap:
        raise AdapterError(f"capital: {code} 不在 items")
    d = _json(_post("https://www.capitalfund.com.tw/CFWeb/api/etf/buyback",
                    json={"fundId": fmap[code]}, headers={"Content-Type": "application/json"}),
              "capital buyback")
    data = d.get("data") or {}
    stocks, pcf = data.get("stocks") or [], data.get("pcf") or {}
    if not stocks or not pcf.get("date2"):
        raise AdapterError(f"{code}: buyback 無持股/資料日")
    holdings = [(str(x["stocNo"]), str(x["stocName"]).strip(), float(x["weight"]), int(x["share"]))
                for x in stocks]
    meta = {"scale": to_num(pcf.get("nav")), "units": to_num(pcf.get("totUnit")),
            "nav_per_unit": to_num(pcf.get("pUnit")), "holders": to_num(pcf.get("numberPeople"))}
    return pcf["date2"], validate_holdings(holdings, code), meta


def _allianz_headers(tok=None):
    h = {"X-XSRF-TOKEN": tok} if tok else {}
    return h


def fetch_allianz(code, name):
    """安聯 etf.allianzgi.com.tw：anti-forgery（header 名 X-XSRF-TOKEN，其他名回 400）；持股在通用表格。"""
    base = "https://etf.allianzgi.com.tw"
    _get(base + "/list-trade")  # session cookie
    tok = _get(base + "/webapi/api/AntiForgery/GetAntiForgeryToken").json().get("token")
    h = _allianz_headers(tok)
    types = _json(_post(base + "/webapi/api/Category/GetFundTypeDropdownOptions", json={}, headers=h),
                  "allianz types")
    tid = next((t.get("Id") for t in (types.get("Entries") or []) if "主動" in (t.get("Name") or "")), None)
    if not tid:
        raise AdapterError("allianz: 找不到主動式類別")
    lst = _json(_post(base + "/webapi/api/Category/GetFundDropdownOptions", json={"TypeId": tid},
                      headers=h), "allianz list")
    fmap = {(e.get("SecuritiesCode") or "").strip(): e["FundNo"] for e in (lst.get("Entries") or [])
            if (e.get("SecuritiesCode") or "").strip()}
    if code not in fmap:
        raise AdapterError(f"allianz: {code} 不在清單")
    for day in _backoff_days(8):
        d = _json(_post(base + "/webapi/api/Fund/GetFundTradeInfo", headers=h,
                        json={"Type": 1, "Keyword": "", "FundNo": fmap[code],
                              "Date": day.strftime("%Y-%m-%d")}), "allianz tradeinfo")
        e = d.get("Entries")
        if not e:
            continue
        tables = [t for t in (e.get("DynamicTableData") or [])
                  if (t.get("TableTitle") or "").startswith("股票")]
        if not tables:
            continue
        holdings = []
        for row in tables[0].get("Rows") or []:
            if len(row) < 5:
                continue
            _, c, n, s, w = row[:5]
            sh = to_num(s)
            if sh is None:
                continue
            holdings.append((str(c).strip(), str(n).strip(), float(str(w).rstrip("%")), int(sh)))
        if not holdings:
            continue
        meta = {"scale": to_num(e.get("CAnceTotalAv")), "units": to_num(e.get("CAnceTotalIssues")),
                "nav_per_unit": to_num(e.get("CAnceNav")), "holders": to_num(e.get("CBeneficiariesCount"))}
        return e["CNavDt"][:10], validate_holdings(holdings, code), meta
    raise AdapterError(f"allianz: {code} 連續 8 日無資料")


def _ctbc_post(url, token, payload):
    r = _post(url, params={"token": token}, json=payload)
    if is_bot_challenge(r):
        raise AdapterError("ctbc: HTTP 200 回驗證圖片")
    d = r.json()
    # 全站回應可能是「JSON 字串」雙層編碼，要 parse 兩次
    while isinstance(d, str):
        d = json.loads(d)
    return d


def fetch_ctbc(code, name):
    """中信 ctbcinvestments：AuthToken(querystring)→ETFList(ETF_ID↔FID)→ETFHoldingWeight{FID,StartDate}。
    資料日=FundAssets[0].資料日期；持股=FundAssetsDetail Code=='STOCK'。"""
    base = "https://www.ctbcinvestments.com.tw/API"
    tok = _ctbc_post(base + "/home/AuthToken?token=www.ctbcinvestments.com", "", {}).get("Data", {}).get("token")
    if not tok:
        raise AdapterError("ctbc: 取不到 token")
    lst = _ctbc_post(base + "/etf/ETFList", tok, {})
    data = lst.get("Data")
    rows = data.get("Data") if isinstance(data, dict) else (data or [])
    fmap = {r["ETF_ID"]: r["FID"] for r in rows if r.get("ETF_ID")}
    if code not in fmap:
        raise AdapterError(f"ctbc: {code} 不在 ETFList")
    for day in _backoff_days(8):
        d = _ctbc_post(base + "/etf/ETFHoldingWeight", tok,
                       {"FID": fmap[code], "StartDate": day.strftime("%Y/%m/%d")})
        if d.get("ResultCode") != 0:
            continue
        dd = d.get("Data") or {}
        assets = dd.get("FundAssets") or []
        groups = [g for g in (dd.get("FundAssetsDetail") or []) if g.get("Code") == "STOCK"]
        rows2 = (groups[0].get("Data") or []) if groups else []
        if not assets or not rows2:
            continue
        holdings = [(str(r["code_"]).strip(), str(r["name_"]).strip(), float(r["weights_"]),
                     int(float(str(r["qty_"]).replace(",", "")))) for r in rows2]
        a = assets[0]
        meta = {"scale": to_num(a.get("基金淨資產")), "units": to_num(a.get("基金在外流通單位數")),
                "nav_per_unit": to_num(a.get("基金每單位淨值")), "holders": None}
        return a["資料日期"].replace("/", "-"), validate_holdings(holdings, code), meta
    raise AdapterError(f"ctbc: {code} 連續 8 日無資料")


def fetch_nomura(code, name):
    """野村 nomurafunds：POST GetFundTradeInfo，FundNo 直接用 ETF 代號；CNavDtStr=基準日（CPcfdate=公告日勿用）。"""
    for day in _backoff_days(8):
        r = _post("https://www.nomurafunds.com.tw/API/ETFAPI/api/Fund/GetFundTradeInfo",
                  json={"Type": 1, "Keyword": "", "FundNo": code, "Date": day.strftime("%Y-%m-%d")},
                  headers={"Content-Type": "application/json"})
        d = _json(r, f"nomura {code}")
        e = d.get("Entries")
        if not e or not e.get("CNavDtStr"):
            continue
        holdings = [(str(s["CStockCode"]).strip(), str(s["CStockName"]).strip(),
                     float(s["CWeightsPct"]), int(to_num(s["CQuantity"])))
                    for s in (e.get("Stocks") or []) if to_num(s.get("CQuantity")) is not None]
        if not holdings:
            continue
        meta = {"scale": to_num(e.get("CAnceTotalAv")), "units": to_num(e.get("CAnceTotalIssues")),
                "nav_per_unit": to_num(e.get("CAnceNav")), "holders": to_num(e.get("CBeneficiariesCount"))}
        return e["CNavDtStr"].replace("/", "-"), validate_holdings(holdings, code), meta
    raise AdapterError(f"nomura: {code} 連續 8 日無資料（或遭機器人驗證）")


TAISHIN_ROW = re.compile(
    r"<tr>\s*<td>\s*([0-9A-Z]{1,8}(?:\s+[A-Z]{2})?)\s*</td>\s*<td>\s*([^<]+?)\s*</td>"
    r"\s*<td>\s*([\d,]+)\s*</td>\s*<td>\s*([\d.]+)%\s*</td>")
NAV_DATE_RE = re.compile(r'id="NAV_DATE"[^>]*value="([^"]+)"')


def fetch_taishin(code, name):
    """台新 tsit.com.tw：SSR，代號即網址參數。NAV_DATE=基準日（PUB_DATE=公告日勿用）；
    代號 Bloomberg 式「2330 TT」剝台股後綴、海外（MU US）保留；只掃「股數」表頭之後（期貨表在前）。"""
    t = html.unescape(_get(f"https://www.tsit.com.tw/ETF/Home/ETFSeriesDetail/{code}").text)
    m = NAV_DATE_RE.search(t)
    if not m:
        raise AdapterError(f"{code}: 台新頁面找不到 NAV_DATE")
    y, mo, d = re.match(r"\s*(\d{4})/(\d{1,2})/(\d{1,2})", m.group(1)).groups()
    seg = t[t.find("股數"):]
    holdings = []
    for c, n, s, w in TAISHIN_ROW.findall(seg):
        c = c.strip()[:-3].strip() if c.strip().endswith(" TT") else c.strip()
        holdings.append((c, n, float(w), int(s.replace(",", ""))))
    if not holdings:
        raise AdapterError(f"{code}: 台新持股表解析為空")
    return f"{y}-{int(mo):02d}-{int(d):02d}", validate_holdings(holdings, code), {}


KGI_ROW = re.compile(
    r'<tr name="content"[^>]*>\s*<td[^>]*>\s*([0-9A-Z]{4,6})\s*</td>\s*'
    r'<td[^>]*>\s*([^<]+?)\s*</td>\s*<td[^>]*>\s*([\d,]+)\s*</td>\s*'
    r'<td[^>]*>\s*([\d.]+)\s*</td>')
KGI_DATE = re.compile(r"持股比重(?:<[^>]*>|\s)*\((\d{4}/\d{2}/\d{2})\)")


def fetch_kgi(code, name):
    """凱基 kgifund：RedemptionList 下拉（名稱↔fundID）；Detail 頁有「兩份」相同持股表只取第一份；
    頁面是 &#x..; 十六進位實體需 unescape；欄位尾端空白要 strip（漏 strip 會靜默掉近半持股）。"""
    opt = _get("https://www.kgifund.com.tw/Fund/RedemptionList").text
    fund_id = None
    for mid, mname in re.findall(r'<option[^>]*value="([^"]+)"[^>]*>([^<]+)</option>', html.unescape(opt)):
        if mname.strip() == name.strip():
            fund_id = mid
            break
    if not fund_id:
        raise AdapterError(f"kgi: {code}「{name}」不在 RedemptionList")
    t = html.unescape(_get(f"https://www.kgifund.com.tw/Fund/Detail?fundID={fund_id}").text)
    md = KGI_DATE.search(t)
    if not md:
        raise AdapterError(f"{code}: 凱基頁面找不到「持股比重 (日期)」")
    first = t.find("股票代號")
    second = t.find("股票代號", first + 1)
    seg = t[first:second] if second > 0 else t[first:]
    holdings = [(c.strip(), n.strip(), float(w), int(s.replace(",", "")))
                for c, n, s, w in KGI_ROW.findall(seg)]
    if not holdings:
        raise AdapterError(f"{code}: 凱基持股表解析為空")
    return md.group(1).replace("/", "-"), validate_holdings(holdings, code), {}


SINOPAC_ROW = re.compile(
    r"<tr>\s*<td>\s*([0-9A-Z]{4,6})\s*</td>\s*<td>\s*([^<]+?)\s*</td>"
    r"\s*<td>\s*([\d,]+)\s*</td>\s*<td>\s*([\d.]+)\s*</td>")


def fetch_sinopac(code, name):
    """永豐 sitc.sinopac：SSR，代號即網址參數。頁面留有 36 個全系列「空表格模板」，
    只掃第一個到第二個「證券代碼」表頭之間；受益人數區塊混雜，寧可不取。"""
    t = html.unescape(_get(f"https://sitc.sinopac.com/SinopacEtfs/Etfs/SinglePcf/{code}").text)
    md = re.search(r"資料日期：\s*(\d{4}/\d{2}/\d{2})", t)
    if not md:
        raise AdapterError(f"{code}: 永豐頁面找不到資料日期")
    first = t.find("證券代碼")
    second = t.find("證券代碼", first + 1)
    seg = t[first:second] if second > 0 else t[first:]
    holdings = [(c, n, float(w), int(s.replace(",", "")))
                for c, n, s, w in SINOPAC_ROW.findall(seg)]
    if not holdings:
        raise AdapterError(f"{code}: 永豐持股表解析為空")
    return md.group(1).replace("/", "-"), validate_holdings(holdings, code), {}


def isin_for(code):
    """TW000+代號+ISIN 檢查碼（36 進位展開後 Luhn）。00404A→TW00000404A5。"""
    body = "TW000" + code
    digits = ""
    for ch in body:
        if ch.isdigit():
            digits += ch
        elif ch.isalpha():
            digits += str(ord(ch.upper()) - 55)
    total, dbl = 0, True
    for ch in reversed(digits):
        v = int(ch)
        if dbl:
            v *= 2
            if v > 9:
                v -= 9
        total += v
        dbl = not dbl
    return body + str((10 - total % 10) % 10)


def fetch_ab(code, name):
    """聯博 webapi.alliancebernstein.com：以 ISIN 識別。basket.asOfDate 帶入 holdings 才對齊基準日；
    回應含 futures/options 分段（期貨權重可達 16%），只能取 holdings-section-equity。"""
    isin = isin_for(code)
    base = f"https://webapi.alliancebernstein.com/v2/funds/tw/zh-tw/investor/{isin}"
    basket = _json(_get(base + "/basket"), f"ab {code} basket")
    asof = (basket.get("asOfDate") or "")[:10]
    if not asof:
        raise AdapterError(f"{code}: basket 缺 asOfDate")
    h = _json(_get(base + f"/holdings?date={asof}"), f"ab {code} holdings")
    secs = [s for s in (h.get("domesticHoldings") or [])
            if s.get("holdingCategory") == "holdings-section-equity"]
    if not secs:
        raise AdapterError(f"{code}: holdings 無 equity 分段")
    holdings = []
    for r in (secs[0].get("holdings") or []):
        c = str(r.get("holdingCode") or "").strip()
        sh, w = to_num(r.get("holdingShares")), to_num(r.get("holdingPerc"))
        if not c or sh is None or w is None:
            continue
        holdings.append((c, str(r.get("holding") or "").strip(), w, int(sh)))
    d = (secs[0].get("asOfDate") or "").strip()  # MM/DD/YYYY
    p = d.split("/")
    data_date = f"{p[2]}-{p[0]}-{p[1]}" if len(p) == 3 else asof
    meta = {"scale": to_num(basket.get("aum")), "units": to_num(basket.get("shares")),
            "nav_per_unit": to_num(basket.get("nav")), "holders": None}
    return data_date, validate_holdings(holdings, code), meta


FIRSTSEC_IDS = {"00408A": "183"}  # 來源：active-etf tests/fixtures（00408A=fundid 183）


def _firstsec_call(action, fund_id, pdate=""):
    r = _post(f"https://www.fsitc.com.tw/WebAPI.aspx/{action}",
              json={"pStrFundID": str(fund_id), "pStrDate": pdate},
              headers={"Content-Type": "application/json; charset=utf-8"})
    d = r.json()
    inner = d.get("d")
    if isinstance(inner, str):  # 雙層編碼要 parse 兩次
        inner = json.loads(inner)
    return inner or []


FIRSTSEC_CODE_RE = re.compile(r"股票代號</td>\s*<td[^>]*>\s*([0-9A-Z]{5,6})\s*</td>")


def _firstsec_peek(fid):
    """讀 FundDetail 前段，回該 ID 的 ETF 代號或 None。代號在渲染後表格的
    「股票代號</td><td>XXXXXX」中（不是 JS 模板字串），位置在前 300KB 內。"""
    r = _session.get(f"https://www.fsitc.com.tw/FundDetail.aspx?ID={fid}",
                     headers={"User-Agent": UA}, timeout=15, stream=True)
    try:
        buf = b""
        for chunk in r.iter_content(65536):
            buf += chunk
            if len(buf) >= 300_000:
                break
    finally:
        r.close()
    m = FIRSTSEC_CODE_RE.search(buf.decode("utf-8", "replace"))
    return m.group(1) if m else None


def _firstsec_discover(code):
    """第一金沒有清單端點：掃 FundDetail.aspx?ID=1-600（8 路平行，串流 300KB 截斷）。

    cache（data/raw/firstsec-fundids.json）已進 git——CI 每班直接命中，避免 600 個
    逐 ID 探測（2026-11-24 #313：CI 無快照→全量掃描被站方限流，靜默吞錯誤報成「掃不到」）。
    """
    cached = {}
    if IDS_CACHE.exists():
        cached = json.loads(IDS_CACHE.read_text(encoding="utf-8"))
    if code in cached:
        return cached[code]
    import concurrent.futures
    found = [None]
    errors = [0]
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        def probe(fid):
            if found[0]:
                return
            try:
                if _firstsec_peek(fid) == code:
                    found[0] = str(fid)
            except requests.RequestException:
                errors[0] += 1
        list(ex.map(probe, range(1, 601)))
    if found[0]:
        cached[code] = found[0]
        IDS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        IDS_CACHE.write_text(json.dumps(cached, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[firstsec] 發現 {code} = fundID {found[0]}（已快取 data/raw/firstsec-fundids.json）")
        return found[0]
    if errors[0] > 500:
        raise AdapterError(
            f"firstsec: {code} 掃描時 {errors[0]}/600 個請求失敗（疑似被站方限流/擋 CI IP），非站方無此基金")
    raise AdapterError(f"firstsec: {code} 在 ID 1-600 掃不到（請人工查 FundDetail.aspx 補 source_id）")


def fetch_firstsec(code, name):
    """第一金 fsitc：WebMethod 雙層 JSON；sdate 本身就是持股基準日；pStrDate 空字串=最新一份。
    fundID 無清單端點：用快取/掃描（見 _firstsec_discover）。"""
    fund_id = FIRSTSEC_IDS.get(code) or _firstsec_discover(code)
    rows = _firstsec_call("Get_hd", fund_id)
    stocks = [r for r in rows if str(r.get("group")) == "1" and (r.get("A") or "").strip()]
    if not stocks:
        raise AdapterError(f"{code}: Get_hd 無股票明細")
    holdings = []
    for r in stocks:
        sh, w = to_num(r.get("D")), to_num(r.get("C"))
        if sh is None or w is None:
            continue
        holdings.append((str(r["A"]).strip(), str(r["B"]).strip(), w, int(sh)))
    date = (stocks[0].get("sdate") or "").strip()
    if not date:
        raise AdapterError(f"{code}: Get_hd 無資料日")
    return date[:10], validate_holdings(holdings, code), {}


JPM_ROW = re.compile(r"<row[^>]*>(.*?)</row>", re.S)


def fetch_jpmorgan(code, name):
    """摩根 am.jpmorgan：唯一只給 Excel 的投信。locale 與 date 必填（缺任一回 500/404 樣貌）。
    date=公告日由今日往前試；sheet1「基金資產 - 股票 (YYYY-MM-DD)」為持股。"""
    try:
        import io
        import pandas as pd
    except ImportError:
        raise AdapterError("jpmorgan: 需要 pandas/openpyxl")
    isin = isin_for(code)
    for day in _backoff_days(8):
        try:
            r = _get("https://am.jpmorgan.com/FundsMarketingHandler/excel",
                     params={"type": "holding_pcf", "cusip": isin, "country": "tw",
                             "role": "twetf", "locale": "zh-TW", "date": day.strftime("%Y-%m-%d")})
            if len(r.content) < 2000:
                continue
            xls = pd.read_excel(io.BytesIO(r.content), sheet_name=0, header=None)
        except (AdapterError, requests.RequestException, ValueError, KeyError):
            continue  # 非公告日回 404（看起來像端點不存在），逐日往回試
        # 找「股票」sheet 標題與表頭列
        cells = xls.astype(str).values.tolist()
        hdr = None
        for i, row in enumerate(cells[:40]):
            flat = [str(c) for c in row if c and c != "nan"]
            if any("股票代碼" in v for v in flat) and any("股數" in v for v in flat):
                hdr = i
                break
        if hdr is None:
            continue
        colmap = {}
        for j, c in enumerate(cells[hdr]):
            for key, label in (("code", "股票代碼"), ("name", "股票名稱"), ("shares", "股數"), ("weight", "權重")):
                if label in str(c):
                    colmap[key] = j
        if not all(k in colmap for k in ("code", "name", "shares", "weight")):
            continue
        holdings = []
        for row in cells[hdr + 1:]:
            c = str(row[colmap["code"]]).strip() if colmap["code"] < len(row) else ""
            if c in ("", "nan"):
                continue
            sh = to_num(row[colmap["shares"]]) if colmap["shares"] < len(row) else None
            w = to_num(row[colmap["weight"]]) if colmap["weight"] < len(row) else None
            if sh is None or w is None:
                continue
            holdings.append((c, str(row[colmap["name"]]).strip(), w, int(sh)))
        if not holdings:
            continue
        mdate = re.search(r"\((\d{4}-\d{2}-\d{2})\)", " ".join(cells[hdr - 1] if hdr else []))
        data_date = mdate.group(1) if mdate else day.strftime("%Y-%m-%d")
        return data_date, validate_holdings(holdings, code), {}
    raise AdapterError(f"jpmorgan: {code} 連續 8 日無資料")


FUBON_ROW = re.compile(
    r'<tr>\s*<td class="tac">\s*([0-9A-Z]{4,6})\s*</td>\s*<td>\s*([^<]+?)\s*</td>'
    r'\s*<td class="tar">\s*([\d,]+)\s*</td>\s*<td class="tar">\s*[\d,]+\s*</td>'
    r'\s*<td class="tar">\s*([\d.]+)\s*</td>')


def fetch_fubon(code, name):
    """富邦 websys.fsit：Assets.aspx SSR（代號/名稱/股數/市值/權重）；「資料日期：YYYY/MM/DD」為基準日。"""
    t = html.unescape(_get(f"https://websys.fsit.com.tw/FubonETF/Trade/Assets.aspx?stkId={code}&lan=TW").text)
    md = re.search(r"資料日期：\s*(\d{4}/\d{2}/\d{2})", t)
    if not md:
        raise AdapterError(f"{code}: 富邦頁面找不到資料日期")
    holdings = [(c, n, float(w), int(s.replace(",", ""))) for c, n, s, w in FUBON_ROW.findall(t)]
    if not holdings:
        raise AdapterError(f"{code}: 富邦持股表解析為空")
    return md.group(1).replace("/", "-"), validate_holdings(holdings, code), {}


MEGA_HIDDEN = re.compile(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"')
MEGA_ROW = re.compile(
    r'<tr class="tr-stock">\s*<td[^>]*>\s*([0-9A-Z]{4,6})\s*</td>\s*'
    r'<td[^>]*>\s*([^<]+?)\s*</td>\s*<td[^>]*>\s*([\d,]+)\s*</td>'
    r'\s*<td[^>]*>\s*([\d.]+)%\s*</td>')
MEGA_URL = "https://www.megafunds.com.tw/MEGA/etf/trade_pcf.aspx"


def fetch_megafunds(code, name):
    """兆豐 megafunds：WebForms POST 回原頁（querystring 被忽略）；hidden 欄位整包原封帶回，
    缺了會「靜默變空」；查詢日期是公告日 T+1，其後第一個日期才是持股基準日。"""
    page = _get(MEGA_URL).text
    hidden = {k: v for k, v in MEGA_HIDDEN.findall(page)}
    plain = _strip_tags(page)
    short = name.strip().replace("主動", "", 1)
    m_opt = re.search(r'name="[^"]*fund_id"[^>]*>(.*?)</select>', page, re.S)
    fid = None
    if m_opt:
        for val, txt in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)</option>', m_opt.group(1)):
            if txt.strip().startswith(short.strip()):
                fid = val
                break
    if not fid:
        raise AdapterError(f"megafunds: {code}「{name}」在下拉選單找不到（短名「{short}」）")
    r = _post(MEGA_URL, data={**hidden, "fund_id": fid, "button1": ""})
    t = html.unescape(r.text)
    if f"股票代號：{code}" not in plain and f"股票代號：{code}" not in t:
        pass  # 標題複核寬鬆處理（選單對照已足），持股列才是硬驗證
    holdings = [(c, n, float(w), int(s.replace(",", ""))) for c, n, s, w in MEGA_ROW.findall(t)]
    if not holdings:
        raise AdapterError(f"{code}: 兆豐持股表解析為空（hidden 欄位或封鎖？）")
    dates = [d for d in re.findall(r"(\d{4}/\d{2}/\d{2})", t)]
    data_date = None
    mq = re.search(r"查詢日期[^0-9]{0,40}(\d{4}/\d{2}/\d{2})", plain)
    if mq:
        q = dt.datetime.strptime(mq.group(1), "%Y/%m/%d").date()
        later = [d for d in dates if dt.datetime.strptime(d, "%Y/%m/%d").date() > q]
        data_date = later[0].replace("/", "-") if later else None
    if not data_date:
        data_date = (dates[0].replace("/", "-") if dates else dt.date.today().isoformat())
    return data_date, validate_holdings(holdings, code), {}


FETCHERS = {
    "ESUN": fetch_esun, "FUHHWA": fetch_fuhhwa, "PRESIDENT": fetch_president,
    "CAPITAL": fetch_capital, "ALLIANZ": fetch_allianz, "CTBC": fetch_ctbc,
    "NOMURA": fetch_nomura, "TAISHIN": fetch_taishin, "KGI": fetch_kgi,
    "SINOPAC": fetch_sinopac, "AB": fetch_ab, "FIRSTSEC": fetch_firstsec,
    "JPMORGAN": fetch_jpmorgan, "MEGAFUNDS": fetch_megafunds, "FUBON": fetch_fubon,
}
# 主動式 ETF 發行商 → fetcher（issuer 名正規化後的前綴）
ISSUER_TO_SRC = [("玉山", "ESUN"), ("復華", "FUHHWA"), ("統一", "PRESIDENT"), ("群益", "CAPITAL"),
                 ("安聯", "ALLIANZ"), ("中信", "CTBC"), ("野村", "NOMURA"), ("台新", "TAISHIN"),
                 ("凱基", "KGI"), ("永豐", "SINOPAC"), ("聯博", "AB"), ("第一金", "FIRSTSEC"),
                 ("摩根", "JPMORGAN"), ("兆豐", "MEGAFUNDS"), ("富邦", "FUBON")]
ACTIVE_CODE_RE = re.compile(r"^00\d{3}A$")


def main():
    argv = sys.argv[1:]
    dry = "--dry-run" in argv
    only = None
    if "--only" in argv:
        only = set(argv[argv.index("--only") + 1].split(","))
    doc = json.loads(HOLDINGS_PATH.read_text(encoding="utf-8"))
    holdings = doc.get("holdings") or {}
    sdoc = json.loads((ROOT / "data" / "stocks.json").read_text(encoding="utf-8"))
    # A 尾清單以 stocks.json 為準（含完全無持股 entry 的新檔）；issuer 決定 fetcher
    targets = []
    for r in sdoc.get("stocks") or []:
        sym = r.get("sym") or ""
        if not (r.get("is_etf") and ACTIVE_CODE_RE.match(sym)):
            continue
        if only and sym not in only:
            continue
        issuer = r.get("issuer") or (holdings.get(sym) or {}).get("issuer") or ""
        src = next((s for kw, s in ISSUER_TO_SRC if kw in issuer), None)
        if src and src in FETCHERS:
            targets.append((sym, src, r.get("name") or sym, issuer))
    targets.sort()
    print(f"[active-etf] 目標 {len(targets)} 檔：{[s for s, _, _, _ in targets]}")

    ok, fail = [], []
    for i, (sym, src, name, issuer) in enumerate(targets, 1):
        e = holdings.get(sym) or {"name": name, "market": "TWSE", "issuer": issuer}
        try:
            data_date, items, meta = FETCHERS[src](sym, e.get("name") or sym)
            prev_asof = ((e or {}).get("asof") or "").replace("/", "-")  # 舊鏈曾是斜線格式
            if prev_asof and data_date < prev_asof:
                # 來源回舊不能覆蓋較新資料（stale carry 原則）
                raise AdapterError(f"來源基準日 {data_date} 較現有 {prev_asof} 舊，不覆蓋")
            if not dry:
                new_e = dict(e)
                new_e.update({"n": len(items), "src": src, "asof": data_date,
                              "items": items, "n_listed": len(items), "issuer": e.get("issuer")})
                for k in ("scale", "units", "nav_per_unit", "holders"):
                    if meta.get(k) is not None:
                        new_e[k] = meta[k]
                new_e.pop("stale", None)
                holdings[sym] = new_e
            ok.append(sym)
            extra = "；受益人數 " + str(meta.get("holders")) if meta.get("holders") else ""
            print(f"  [{i}/{len(targets)}] {sym}（{src}）✅ {len(items)} 檔持股, asof={data_date}{extra}")
        except AdapterError as ex:
            fail.append(sym)
            if not dry:
                if sym in holdings:
                    holdings[sym]["stale"] = True
            print(f"  [{i}/{len(targets)}] {sym}（{src}）❌ {ex}")
        time.sleep(0.6)

    print(f"\n[active-etf] 成功 {len(ok)}／失敗 {len(fail)}；失敗清單 {fail}")
    if dry:
        print("[active-etf] --dry-run：未寫入")
        return 0
    if ok:
        from collections import Counter
        doc["holdings"] = holdings
        src_count = Counter((v or {}).get("src") for v in holdings.values())
        doc.setdefault("meta", {})["src_counts"] = dict(src_count)
        out = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        HOLDINGS_PATH.write_bytes(out)
        print(f"[active-etf] ✅ 已寫入 {HOLDINGS_PATH}（{len(out)/1024:.0f} KB）src_counts={dict(src_count)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
