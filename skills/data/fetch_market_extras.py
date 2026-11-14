#!/usr/bin/env python3
"""★★★ 官方加值資料抓取（2026-11-14 導入）

一次抓六個 TWSE OpenAPI 三顆星端點，輸出單一檔 data/market-extras.json：

| 端點 | 內容 | 用途 |
|---|---|---|
| opendata/t187ap05_L | 上市公司每月營業收入彙總表 | 月營收看板、成長動能 |
| exchangeReport/MI_MARGN | 集中市場融資融券餘額 | 籌碼面 |
| opendata/t187ap17_L | 上市公司營益分析查詢彙總表 | 官方毛利率／營益率（驗證自算值） |
| opendata/t187ap14_L | 上市公司各產業EPS統計資訊 | 官方累計 EPS（與本站年化 EPS 交叉驗證） |
| exchangeReport/TWTAWU | 集中市場暫停交易證券 | 停牌即時判斷（強化停牌鐵律） |
| holidaySchedule/holidaySchedule | 有價證券集中市場開（休）市日期 | 交易日曆 |

設計原則（遵循資料鐵律）：
- **不補值**：官方沒給就留 null，不以 0 或前值填充。
- **不自創口徑**：比率直接存官方值（`*_off`），本站自算值另存，兩者都保留可稽核。
- **冪等**：重複執行結果相同；輸出不含當下時間以外的隨機性。
"""
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data_rules  # noqa: E402
import scope_rules  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "market-extras.json")
TZ = dt.timezone(dt.timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
BASE = "https://openapi.twse.com.tw/v1"

TWSE_REVENUE = BASE + "/opendata/t187ap05_L"
TWSE_MARGIN = BASE + "/exchangeReport/MI_MARGN"
TWSE_PROFIT = BASE + "/opendata/t187ap17_L"
TWSE_EPS = BASE + "/opendata/t187ap14_L"
TWSE_HALT = BASE + "/exchangeReport/TWTAWU"
TWSE_HOLIDAY = BASE + "/holidaySchedule/holidaySchedule"

HOLIDAY_START_YEAR = 2026  # 只保留今年起（官方檔常含跨年度清單）


def http_json(url, timeout=60, retries=3):
    """取 JSON；失敗回 None（呼叫端決定是否視為致命）。"""
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as f:
                return json.loads(f.read().decode("utf-8", "ignore"))
        except Exception as e:  # noqa: BLE001
            last = e
    print(f"  [warn] {url} 失敗：{last}", file=sys.stderr)
    return None


def num(v):
    """字串轉數字；空字串／'-'／'--'／'註' 一律 None（不補 0）。"""
    if v is None:
        return None
    s = str(v).strip().replace(",", "").replace("%", "")
    if s in ("", "-", "--", "註", "N/A", "nan"):
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    if f != f:  # NaN
        return None
    return f


def roc_to_iso(v, kind="date"):
    """民國日期轉西元。kind='date' 收 7 碼（1151110）；kind='month' 收 5 碼（11510）。"""
    s = str(v or "").strip()
    if not s.isdigit():
        return None
    try:
        if kind == "month":
            if len(s) != 5:
                return None
            return f"{int(s[:3]) + 1911:04d}-{int(s[3:5]):02d}"
        if len(s) != 7:
            return None
        return f"{int(s[:3]) + 1911:04d}-{int(s[3:5]):02d}-{int(s[5:7]):02d}"
    except ValueError:
        return None


def in_scope_sym(code):
    """官方端點含權證／公發等範圍外代號 → 一律先過站內範圍規則。"""
    try:
        return scope_rules.in_scope(str(code).strip())
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------- 各端點解析

def parse_revenue(raw):
    """t187ap05_L → {sym: {ym, month, prev_month, yoy_base, mom, yoy, ytd, ytd_prev, ytd_yoy}}
    單位：千元（沿用官方；不換算，避免誤差）。"""
    out = {}
    for r in raw or []:
        code = str(r.get("公司代號", "")).strip()
        if not code or not in_scope_sym(code):
            continue
        out[code] = {
            "ym": roc_to_iso(r.get("資料年月"), "month"),
            "month": num(r.get("營業收入-當月營收")),
            "prev_month": num(r.get("營業收入-上月營收")),
            "last_year_month": num(r.get("營業收入-去年當月營收")),
            "mom": num(r.get("營業收入-上月比較增減(%)")),
            "yoy": num(r.get("營業收入-去年同月增減(%)")),
            "ytd": num(r.get("累計營業收入-當月累計營收")),
            "ytd_last_year": num(r.get("累計營業收入-去年累計營收")),
            "ytd_yoy": num(r.get("累計營業收入-前期比較增減(%)")),
        }
    return out


def parse_margin(raw):
    """MI_MARGN → {sym: {fin_buy, fin_sell, fin_cash_repay, fin_prev, fin_bal, fin_limit,
    sec_buy, sec_sell, sec_cash_repay, sec_prev, sec_bal, sec_limit, offset}}
    單位：張（融資融券慣用單位），沿用官方。"""
    out = {}
    for r in raw or []:
        code = str(r.get("股票代號", "")).strip()
        if not code or not in_scope_sym(code):
            continue
        out[code] = {
            "fin_buy": num(r.get("融資買進")),
            "fin_sell": num(r.get("融資賣出")),
            "fin_repay": num(r.get("融資現金償還")),
            "fin_prev": num(r.get("融資前日餘額")),
            "fin_bal": num(r.get("融資今日餘額")),
            "fin_limit": num(r.get("融資限額")),
            "sec_buy": num(r.get("融券買進")),
            "sec_sell": num(r.get("融券賣出")),
            "sec_repay": num(r.get("融券現券償還")),
            "sec_prev": num(r.get("融券前日餘額")),
            "sec_bal": num(r.get("融券今日餘額")),
            "sec_limit": num(r.get("融券限額")),
            "offset": num(r.get("資券互抵")),
        }
    return out


def parse_profitability(raw):
    """t187ap17_L → {sym: {period, revenue_mio, gross_pct, op_pct, pretax_pct, net_pct}}
    比率直接存官方值（不自算），供驗證本站由損益表自算的比率。"""
    out = {}
    for r in raw or []:
        code = str(r.get("公司代號", "")).strip()
        if not code or not in_scope_sym(code):
            continue
        year = str(r.get("年度", "")).strip()
        quarter = str(r.get("季別", "")).strip()
        period = f"{int(year) + 1911}Q{quarter}" if year.isdigit() and quarter.isdigit() else None
        out[code] = {
            "period": period,
            "asof": roc_to_iso(r.get("出表日期")),
            "revenue_mio": num(r.get("營業收入(百萬元)")),
            "gross_pct": num(r.get("毛利率(%)(營業毛利)/(營業收入)")),
            "op_pct": num(r.get("營業利益率(%)(營業利益)/(營業收入)")),
            "pretax_pct": num(r.get("稅前純益率(%)(稅前純益)/(營業收入)")),
            "net_pct": num(r.get("稅後純益率(%)(稅後純益)/(營業收入)")),
        }
    return out


def parse_official_eps(raw):
    """t187ap14_L → {sym: {period, eps_cum, revenue, op_income, non_op, ni}}
    注意：官方為**累計** EPS（季別 3 = 前三季累計），與本站年化 eps 不同基準 → 只做交叉驗證。"""
    out = {}
    for r in raw or []:
        code = str(r.get("公司代號", "")).strip()
        if not code or not in_scope_sym(code):
            continue
        year = str(r.get("年度", "")).strip()
        quarter = str(r.get("季別", "")).strip()
        period = f"{int(year) + 1911}Q{quarter}" if year.isdigit() and quarter.isdigit() else None
        out[code] = {
            "period": period,
            "asof": roc_to_iso(r.get("出表日期")),
            "eps_cum": num(r.get("基本每股盈餘(元)")),
            "revenue": num(r.get("營業收入")),
            "op_income": num(r.get("營業利益")),
            "non_op": num(r.get("營業外收入及支出")),
            "ni": num(r.get("稅後淨利")),
        }
    return out


def parse_halts(raw):
    """TWTAWU → {sym: {halt_date, halt_time, resume_date, resume_time}}"""
    out = {}
    for r in raw or []:
        code = str(r.get("Code", "")).strip()
        if not code:
            continue
        out[code] = {
            "name": r.get("Name"),
            "halt_date": roc_to_iso(r.get("TradingHaltDate")),
            "halt_time": r.get("TradingHaltTime") or None,
            "resume_date": roc_to_iso(r.get("TradingResumptionDate")),
            "resume_time": r.get("TradingResumptionTime") or None,
        }
    return out


def parse_holidays(raw):
    """holidaySchedule → [{date, name, weekday, desc}]（只留今年以後，排序）。"""
    out = []
    for r in raw or []:
        iso = roc_to_iso(r.get("Date"))
        if not iso or int(iso[:4]) < HOLIDAY_START_YEAR:
            continue
        out.append({
            "date": iso,
            "name": (r.get("Name") or "").strip(),
            "weekday": (r.get("Weekday") or "").strip(),
            "desc": (r.get("Description") or "").strip(),
        })
    out.sort(key=lambda x: x["date"])
    return out


def main():
    srcs = {
        "revenue": TWSE_REVENUE, "margin": TWSE_MARGIN, "profitability": TWSE_PROFIT,
        "eps_official": TWSE_EPS, "halts": TWSE_HALT, "holidays": TWSE_HOLIDAY,
    }
    fetched, failed = {}, []
    for key, url in srcs.items():
        raw = http_json(url)
        if raw is None:
            failed.append(key)
            fetched[key] = []
        else:
            fetched[key] = raw
    if len(failed) == len(srcs):
        print("所有端點皆失敗，中止（不覆蓋既有檔）", file=sys.stderr)
        return 2

    payload = {
        "meta": {
            "as_of": dt.datetime.now(TZ).strftime("%Y-%m-%d"),
            "fetched_at": dt.datetime.now(TZ).isoformat(timespec="seconds"),
            "source": "TWSE OpenAPI（免 key）",
            "endpoints": {k: v.replace(BASE, "") for k, v in srcs.items()},
            "failed": failed,
            "counts": {},
            "note": "官方加值資料。月營收單位千元、融資融券單位張；比率為官方營益分析值；"
                    "eps_official 為累計 EPS（與本站年化 eps 不同基準，僅供交叉驗證）；"
                    "範圍外代號（權證／公發等）已由 scope_rules.in_scope 濾除。",
        },
        "revenue": parse_revenue(fetched["revenue"]),
        "margin": parse_margin(fetched["margin"]),
        "profitability": parse_profitability(fetched["profitability"]),
        "eps_official": parse_official_eps(fetched["eps_official"]),
        "halts": parse_halts(fetched["halts"]),
        "holidays": parse_holidays(fetched["holidays"]),
    }
    for k in ("revenue", "margin", "profitability", "eps_official", "halts", "holidays"):
        payload["meta"]["counts"][k] = len(payload[k])

    # 保護：先前有資料而這次抓到 0 筆 → 視為來源異常，不覆蓋（避免把好資料洗成空的）
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8"))
            regress = [k for k in ("revenue", "margin", "profitability", "eps_official")
                       if old["meta"]["counts"].get(k, 0) > 0 and payload["meta"]["counts"][k] == 0]
            if regress:
                print(f"來源筆數異常歸零 {regress}，中止不覆蓋", file=sys.stderr)
                return 2
        except Exception:  # noqa: BLE001
            pass

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print("已寫入", OUT)
    for k, v in payload["meta"]["counts"].items():
        print(f"  {k:<14} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
