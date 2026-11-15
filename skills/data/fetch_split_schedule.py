#!/usr/bin/env python3
"""官方公司行為預告抓取：ETF 分割／反分割／減資的「暫停先賣後買當沖」區間。

為什麼需要（2026-11-15 Ivan 指示「讓未來哪檔 ETF 分割，還沒發生就先知道」）：
  過去只能等分割**發生後**由 K 線跳空反推（detect_corporate_actions.py）。但證交所
  其實有**預告表**，事件發生前就公告了「原因＋暫停當沖區間」。實測 2026-11-15：
    0053 元大科技市值 1151127~1151203 Reason=ETF分割
    6108 競國        1151207~1151211 Reason=減資
  因此可以在事件前就登記為 status=planned，讓 pipeline 與畫面提前知道。

來源（實測可用，皆為官方）：
  TWSE /exchangeReport/TWTBAU1  集中市場暫停先賣後買當日沖銷交易標的預告表
  TWSE /exchangeReport/TWTBAU2  同表（歷史查詢）
  TPEx  /tpex_intraday_trading_pre  上櫃暫停先賣後買當日沖銷交易標的預告表

⚠️ 安全設計（不可拿掉）：
  - 預告**只有區間與原因，沒有比率** → 一律 ratio=None 登錄，绝不推測倍數。
    （registry 沒有 ratio 者不會被拿去算還原價，見 corporate_actions.load_actions）
  - planned **不觸發停牌**（sanitize_snapshot 只對 status=pending ＋ halt_from 生效）。
  - 來源全部抓不到時**不覆寫**既有排程檔（避免把上次的預告清空）。

用法：
  python3 skills/data/fetch_split_schedule.py            # 只寫排程檔
  python3 skills/data/fetch_split_schedule.py --register  # 另把未登錄者以 planned 寫入 registry
"""
import datetime as dt
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEDULE = os.path.join(ROOT, "data", "corporate-actions-schedule.json")
REGISTRY = os.path.join(ROOT, "data", "corporate-actions.json")

SOURCES = {
    "TWSE_PRE": "https://openapi.twse.com.tw/v1/exchangeReport/TWTBAU1",
    "TWSE_HIS": "https://openapi.twse.com.tw/v1/exchangeReport/TWTBAU2",
    "TPEX_PRE": "https://www.tpex.org.tw/openapi/v1/tpex_intraday_trading_pre",
}
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
# 只看公司行為；「分配收益」「受益人大會」等與股數／價格無關者一律略過
KEYWORDS = ("分割", "減資", "換發")
ROC_OFFSET = 1911


def roc_to_iso(v):
    """民國日期（1151127）→ ISO（2026-11-27）。格式不對回 None（不猜）。"""
    s = str(v or "").strip()
    if len(s) != 7 or not s.isdigit():
        return None
    y, m, d = int(s[:3]) + ROC_OFFSET, int(s[3:5]), int(s[5:7])
    try:
        return dt.date(y, m, d).isoformat()
    except ValueError:
        return None


def classify_reason(reason):
    """由官方 Reason 判定事件類型；與公司行為無關者回 None。"""
    r = str(reason or "")
    if "反分割" in r:
        return "reverse_split"
    if "分割" in r:          # ETF分割、股票分割、面額變更分割
        return "split"
    if "減資" in r:
        return "capital_reduction"
    if "換發" in r:          # 換發新股（未寫明分割／減資時的官方用語）
        return "split"
    return None


def _event(sym, name, market, reason, roc_from, roc_to, source_url):
    kind = classify_reason(reason)
    frm, to = roc_to_iso(roc_from), roc_to_iso(roc_to)
    if not kind or not sym or not frm:
        return None
    return {
        "sym": str(sym),
        "name": str(name or "").strip(),
        "market": market,
        "kind": kind,
        "reason": str(reason),
        "day_trade_suspend_from": frm,
        "day_trade_suspend_to": to,
        "roc_from": str(roc_from),
        "roc_to": str(roc_to),
        "source": source_url,
    }


def parse_twse(rows, market="TWSE", source_url=""):
    """TWSE TWTBAU1／TWTBAU2 → 事件清單（只留公司行為）。"""
    out = []
    for r in rows or []:
        e = _event(r.get("Code"), r.get("Name"), market, r.get("Reason"),
                   r.get("StartDate"), r.get("EndDate"), source_url)
        if e:
            out.append(e)
    return out


def parse_tpex(rows, source_url=""):
    """TPEx tpex_intraday_trading_pre → 事件清單（只留公司行為）。"""
    out = []
    for r in rows or []:
        e = _event(r.get("SecuritiesCompanyCode"), r.get("CompanyName"), "TPEx", r.get("Reason"),
                   r.get("FirstDayToSuspendSellThenBuy"), r.get("DayOfReinstatingSellThenBuy"), source_url)
        if e:
            out.append(e)
    return out


def build_schedule(*event_lists):
    """合併多來源 → 去重（同代號＋同起始日＋同原因）並固定排序。"""
    seen, out = set(), []
    for lst in event_lists:
        for e in lst or []:
            key = (e["sym"], e.get("day_trade_suspend_from"), e.get("reason"))
            if key in seen:
                continue
            seen.add(key)
            out.append(e)
    out.sort(key=lambda e: (e["sym"], e.get("day_trade_suspend_from") or ""))
    return out


def write_schedule(path, events, sources=None, today=None):
    """輸出排程檔（冪等：同一天重跑內容完全相同）。

    排序在函式內做（呼叫端忘了先 build_schedule 也不會產生不穩定的檔案）。
    """
    today = today or dt.date.today().isoformat()
    events = sorted(events or [], key=lambda e: (e["sym"], e.get("day_trade_suspend_from") or ""))
    doc = {
        "meta": {
            "note": ("官方公司行為預告（TWSE TWTBAU1／TWTBAU2、TPEx tpex_intraday_trading_pre）。"
                     "這裡的區間是**暫停先賣後買當日沖銷**的範圍，用來提前得知事件；"
                     "**不含比率**，比率一律等事件發生後由官方公告補登到 corporate-actions.json。"),
            "as_of": today,
            "count": len(events),
            "sources": sources or {},
        },
        "events": [dict(e, when=("upcoming" if (e.get("day_trade_suspend_to") or e.get("day_trade_suspend_from") or "") >= today
                                 else "past")) for e in events],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return doc


def register_planned(registry_path, events, today=None):
    """把尚未登錄的預告事件以 status=planned、ratio=None 寫進 registry。

    回傳新加入的代號（排序）。已存在者（任何 status）一律不覆寫——人工登錄的
    比率與停牌日比預告精確，不可被預告蓋掉。
    """
    today = today or dt.date.today().isoformat()
    try:
        with open(registry_path, encoding="utf-8") as f:
            reg = json.load(f)
    except (OSError, json.JSONDecodeError):
        reg = {"meta": {}, "actions": []}
    have = {str(a.get("sym")) for a in reg.get("actions", [])}
    added = []
    for e in events:
        if e["sym"] in have:
            continue
        if (e.get("day_trade_suspend_to") or e.get("day_trade_suspend_from") or "") < today:
            continue          # 已過去的預告不補登（事件已完成者另有偵測器負責）
        reg.setdefault("actions", []).append({
            "sym": e["sym"],
            "name": e["name"],
            "type": e["kind"],
            "ratio": None,             # 預告沒有比率 → 絕不推測
            "cash_refund": None,
            "halt_from": None,
            "resume_date": None,
            "status": "planned",
            "source": f"{e['source']}（{e['market']} 暫停先賣後買當日沖銷交易標的預告表）",
            "source_note": (f"官方預告：{e['reason']}，暫停當沖區間 {e['roc_from']}~{e['roc_to']}"
                            f"（民國，＝{e['day_trade_suspend_from']}~{e.get('day_trade_suspend_to')}）。"
                            "**尚未有官方比率**；事件完成後補登 ratio／cash_refund 與停牌日，才會套用還原價。"),
        })
        have.add(e["sym"])
        added.append(e["sym"])
    if added:
        reg.setdefault("meta", {})["updated"] = today
        reg["actions"].sort(key=lambda a: (str(a.get("resume_date") or a.get("halt_from") or "9999"),
                                           str(a.get("sym"))))
        with open(registry_path, "w", encoding="utf-8") as f:
            json.dump(reg, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return sorted(added)


def fetch_json(url, timeout=25):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as e:      # 網路／WAF／格式問題都不該讓每日更新整批失敗
        print(f"[fetch_split_schedule] 抓取失敗 {url}: {e}")
        return []


def main(argv=None, register=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if register is None:
        register = "--register" in argv
    got = {k: fetch_json(u) for k, u in SOURCES.items()}
    ok = {k: v for k, v in got.items() if v}
    if not ok:
        print("[fetch_split_schedule] 三個來源全部失敗 → 不覆寫既有排程檔")
        return 1
    events = build_schedule(
        parse_twse(ok.get("TWSE_PRE", []), source_url=SOURCES["TWSE_PRE"]),
        parse_twse(ok.get("TWSE_HIS", []), source_url=SOURCES["TWSE_HIS"]),
        parse_tpex(ok.get("TPEX_PRE", []), source_url=SOURCES["TPEX_PRE"]),
    )
    doc = write_schedule(SCHEDULE, events, sources={k: SOURCES[k] for k in ok})
    up = [e for e in doc["events"] if e["when"] == "upcoming"]
    print(f"[fetch_split_schedule] 來源可用 {len(ok)}/{len(SOURCES)}；"
          f"公司行為預告 {len(events)} 筆（未來 {len(up)} 筆）→ {os.path.relpath(SCHEDULE, ROOT)}")
    for e in doc["events"]:      # doc 內才有 when（write_schedule 補上的）
        print(f"   {e['sym']:<8}{e['name'][:12]:<14}{e['kind']:<18}{e['reason']:<8}"
              f"{e['day_trade_suspend_from']}~{e.get('day_trade_suspend_to')}  [{e['when']}]")
    if register:
        added = register_planned(REGISTRY, events)
        print(f"[fetch_split_schedule] 新登錄為 planned：{added or '無'}")
        if added:
            print("   ⚠️ 這些還沒有比率，不會套用還原價；事件完成後請補 ratio 與停牌日")
    return 0


if __name__ == "__main__":
    sys.exit(main())
