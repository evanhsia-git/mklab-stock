#!/usr/bin/env python3
"""資料更新狀態紀錄與到期判斷（2026-11-26 五組整合——多 job 共用）。

狀態存放：data/fetch-log.json 頂層新增 "update_state" 鍵（向下相容——
daily 班 fetch_data.py 既有欄位一律不動；本模組讀寫時保留全部既有鍵）。

子命令:
  check <task>                 exit 0 = 到期(due)、exit 1 = 未到期(not-due)、exit 2 = 用法錯誤
  record <task> --status attempted|succeeded|failed [--failed-sources a,b]
                               succeeded/failed 時 last_* 取當下；succeeded 時自動讀對應
                               資料檔日期寫入 data_as_of（不信任呼叫者自報）。
  holdings-run [--dry-run]     投信持股半月制（上半月 1-15 日 / 下半月 16-月底）：
                               每來源獨立狀態，本期已成功的不重抓，只補失敗與未跑來源。

日期一律以 Asia/Taipei 為準（資料檔日期皆為台股/美股對應的台北更新日）。
到期判斷原則（Ivan 2026-11-26 審核規範第四節）：
  - due = 「今天(台北)還沒有成功的紀錄」且「資料日期落後」——不假設資料日期等於成功日期，
    record succeeded 時的 data_as_of 由本模組直接讀資料檔。
  - last_attempt 已在今天但未成功 → 仍視為 due（嘗試失敗需要重試）。
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 測試可透過 UPDATE_STATE_PATH 指向暫存檔，避免動到正式 fetch-log.json
STATE_PATH = os.environ.get("UPDATE_STATE_PATH") or os.path.join(ROOT, "data", "fetch-log.json")
_TPEI = timezone(timedelta(hours=8))


def _now():
    return datetime.now(_TPEI)


def _today():
    return _now().strftime("%Y-%m-%d")


def _load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            doc = json.load(f)
        if not isinstance(doc, dict):
            doc = {}
    except (OSError, ValueError):
        doc = {}
    state = doc.setdefault("update_state", {})
    if not isinstance(state, dict):
        doc["update_state"] = state = {}
    return doc, state


def _save_state(doc):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, STATE_PATH)


def _read_meta_date(rel, keys=("as_of", "date", "last_updated")):
    """讀資料檔的 meta 日期（回傳 YYYY-MM-DD 或 None）。us/*.json 的 'YYYY-MM-DD HH:MM:SS UTC' 取前 10 碼。"""
    p = os.path.join(ROOT, rel)
    try:
        with open(p, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return None
    meta = doc.get("meta") or {}
    for k in keys:
        v = meta.get(k)
        if isinstance(v, str) and len(v) >= 10:
            return v[:10]
    # index-holdings：holdings_asof 在頂層（逐檔），取全部檔案最新
    return None


def _latest_index_holdings_month():
    """data/index-holdings/*.json 的最大 holdings_asof 月份。"""
    import glob as _glob
    latest = None
    for p in _glob.glob(os.path.join(ROOT, "data", "index-holdings", "*.json")):
        try:
            with open(p, encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, ValueError):
            continue
        v = doc.get("holdings_asof")
        if isinstance(v, str) and (latest is None or v > latest):
            latest = v
    return latest[:7] if latest else None


# task → (說明, 到期判斷需要的資料檔)
TASKS = {
    "tw-stock-daily": {"file": "data/stocks.json"},
    "tw-stock-roe": {"file": None},               # 週六備援班：今天(台北週六)沒成功即到期
    "tw-stock-fundamentals": {"file": "data/raw/official/ 財報月檔"},
    "tw-etf-nav": {"file": "data/etf-nav.json"},
    "tw-etf-holdings": {"file": "data/etf-holdings.json"},
    "tw-etf-meta": {"file": "data/etf-meta.json"},
    "tw-etf-qa": {"file": None},                  # 每週一稽核：今天沒成功即到期
    "us-stock-daily": {"file": "data/us/us-stocks.json"},
    "us-etf-daily": {"file": "data/us/us-etfs.json"},
    "us-etf-holdings": {"file": "data/index-holdings/"},
    "global-indices": {"file": "data/indices.json"},
    "global-history": {"file": None},             # 月檔累積：今天沒成功即到期
}


# 每日行情類 → 對應市場（到期判斷以「最近有效交易日」為準，Phase 5 P0-4——
# 不再用星期幾擋：台北週六日 21:00 補跑班仍可補「美股週五／台股週五」未取得的資料。
# 交易日曆採「週一~五為工作日」（零依賴）；國定假日／美股休市日會讓 check 判斷到期、
# 跑步後資料日期不變 → record succeeded（當日）→ 次日再到期 → 交易日恢復後自然取得。
# 白跑成本可接受（冪等抓取），不得因週末放棄尚未取得的交易日資料（Ivan 審核規範四）。
DAILY_TASK_MARKET = {
    "tw-stock-daily": "tw",
    "us-stock-daily": "us",
    "us-etf-daily": "us",
    "global-indices": "tw",      # indices.json 的 as_of 為台北更新日
    "global-history": "us",      # 美股週期月檔（無單一日期欄位，以 last_success 代替）
}


def _last_workday(market, now=None):
    """最近一個「已完成交易」的工作日（Phase 5 補充 P0-3：含收盤時間判斷）。

    tw=台北曆（13:30 收盤）；us=美東曆（16:00 收盤，zoneinfo 自動夏令/冬令）。
    收盤前的當日**不算**已完成交易日（未完成的盤中資料不得視為收盤資料）；
    美東夏令/冬令由 zoneinfo 自動換算（台北 06:30 = 美東 17:30/18:30，皆已過 16:00）。
    交易所休市日曆暫不處理（已知限制：假日誤判到期→冪等白跑，不覆蓋有效資料）。
    """
    try:
        from zoneinfo import ZoneInfo
        tz = _TPEI if market == "tw" else ZoneInfo("America/New_York")
    except ImportError:
        tz = _TPEI
    local = (now.astimezone(tz) if now else datetime.now(tz))
    d = local.date()
    hourf = local.hour + local.minute / 60
    if market == "tw" and hourf < 13.5:       # 台股 13:30 收盤
        d -= timedelta(days=1)
    elif market == "us" and hourf < 16:       # 美股 16:00 美東收盤
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


def check_due(task, state):
    """回傳 (due: bool, 說明)。到期＝資料/成功日期落後最近有效交易日，或週期任務本期未完成。"""
    info = TASKS.get(task)
    if info is None:
        raise SystemExit(f"unknown task: {task}")
    today = _today()
    rec = state.get(task) or {}
    last_success = rec.get("last_success")
    # last_success 存完整 ISO datetime（record 寫入時帶時分秒）——比較一律取日期部分 [:10]
    if last_success and last_success[:10] == today and rec.get("status") == "succeeded":
        return False, f"今天已 succeeded（{last_success}）"
    if last_success and last_success[:10] > today:
        return False, f"last_success {last_success} 在未來（時鐘異常防護）"

    # ── 每日行情類：資料日期（或 last_success）至少要達到「最近有效交易日」──
    if task in DAILY_TASK_MARKET:
        lw = _last_workday(DAILY_TASK_MARKET[task], _now())
        data_date = None
        if info.get("file") and info["file"].startswith("data/") and not info["file"].endswith("/"):
            data_date = _read_meta_date(info["file"])
        if not data_date:
            data_date = (last_success or "")[:10] or None
        if not data_date or data_date < lw:
            return True, f"資料日期 {data_date or '無'} < 最近交易日 {lw}（{DAILY_TASK_MARKET[task].upper()} 曆）"
        return False, f"資料已達最近交易日（{data_date} = {lw}）"

    # 子任務級週期判斷
    if task == "tw-stock-fundamentals":
        # 每月 20 日起：本月尚無 succeeded 紀錄 → due
        if int(today[8:10]) < 20:
            return False, f"本月 {today[5:7]} 月尚未到 20 日"
        return True, f"{today[5:7]} 月財報未更新"
    if task == "us-etf-holdings":
        # 每月 2 日起（台北）：index-holdings 的最大 holdings_asof 月份 < 本月 → due
        if int(today[8:10]) < 2:
            return False, "本月尚未到 2 日"
        latest = _latest_index_holdings_month()
        if latest is None:
            return True, "index-holdings 無資料"
        if latest < today[:7]:
            return True, f"最新持股月份 {latest} < 本月 {today[:7]}"
        return False, f"本月持股已更新（{latest}）"
    if task in ("tw-etf-nav", "tw-etf-meta", "us-stock-daily", "us-etf-daily", "global-indices", "tw-stock-daily"):
        # 每日班：資料日期落後今天 → due（不假設成功日期＝資料日期）
        data_date = _read_meta_date(info["file"])
        if data_date is None:
            return True, f"{info['file']} 無法讀取（視為到期）"
        if data_date < today:
            return True, f"資料日期 {data_date} < 今天 {today}"
        return False, f"資料已是最新（{data_date}）"
    if task == "tw-etf-holdings":
        # 半月制：本期（H1/H2）全數成功且無 failed_sources → not-due；
        # 部分失敗（succeeded 但 failed_sources 非空）→ due（21:00 補跑班補失敗來源）
        period = _holdings_period(today)
        hrec_ok = (rec.get("period") == period and rec.get("status") == "succeeded"
                   and not rec.get("failed_sources"))
        return (not hrec_ok), f"本期 {period} " + ("已完成" if hrec_ok else "未完成或有失敗來源")
    # 無資料檔的週期任務（roe/qa/history）：今天沒成功即到期
    return True, f"今天尚未執行（last_success={last_success or '無'}）"


def _holdings_period(today):
    return f"{today[:7]}-H1" if 1 <= int(today[8:10]) <= 15 else f"{today[:7]}-H2"


# 投信持股來源（與 daily 班 workflow 既有 5 支腳本一一對應；順序＝現行順序）
HOLDINGS_SOURCES = [
    ("cathay", "skills/data/fetch_etf_holdings_cathay.py"),
    ("usitc", "skills/data/fetch_etf_holdings_usitc.py"),
    ("uobam", "skills/data/fetch_etf_holdings_uobam.py"),
    ("ftft", "skills/data/fetch_etf_holdings_ftft_monthly.py"),
    ("active", "skills/data/fetch_etf_holdings_active.py"),
]


def cmd_record(args):
    doc, state = _load_state()
    rec = state.setdefault(args.task, {})
    now = _now().isoformat(timespec="seconds")
    rec["last_attempt"] = now
    rec["status"] = args.status
    if args.failed_sources:
        rec["failed_sources"] = [s for s in args.failed_sources.split(",") if s]
    else:
        rec.pop("failed_sources", None)
    if args.status == "succeeded":
        data_as_of = _auto_data_as_of(args.task)
        market = DAILY_TASK_MARKET.get(args.task)
        # P0（2026-11-28 稽核）：行情類任務必須驗證 requested_date == actual_data_date。
        # 資料日期早於應有交易日（例：週六凌晨跑，來源回前一交易日）→ 不得記 SUCCESS，
        # 降級為 stale：check_due 視為未成功（次日/補跑班自動重試），且不擋本次 push
        # （歷史缺口不得無條件阻止最新有效資料發布——Ivan 審核規範七）。
        expected = _last_workday(market, _now()) if market else None
        if expected and data_as_of and str(data_as_of)[:10] < expected:
            rec["status"] = "stale"
            rec["stale_reason"] = (
                f"資料日期 {data_as_of} < 應有交易日 {expected}（行情來源未提供該日資料；"
                "舊資料不得冒充新資料）"
            )
            rec["data_as_of"] = data_as_of
        else:
            rec["status"] = "succeeded"
            rec["last_success"] = now
            rec["period"] = _current_period(args.task)
            if data_as_of:
                rec["data_as_of"] = data_as_of
            rec.pop("stale_reason", None)
    _save_state(doc)
    print(f"[update-state] {args.task}: status={rec.get('status')} recorded"
          + (f"（{rec['stale_reason']}）" if rec.get("stale_reason") else ""))
    return 0


def _current_period(task):
    today = _today()
    if task in ("tw-stock-roe", "tw-etf-meta", "tw-etf-qa"):
        return f"{today[:7]}-W{(_now().isocalendar()[1]):02d}"
    if task == "tw-stock-fundamentals":
        return f"{today[:7]}-monthly"
    if task == "us-etf-holdings":
        return f"{today[:7]}-monthly"
    if task == "tw-etf-holdings":
        return _holdings_period(today)
    return f"{today[:7]}-daily"


def _auto_data_as_of(task):
    info = TASKS.get(task) or {}
    f = info.get("file")
    if f and f.startswith("data/") and not f.endswith("/"):
        return _read_meta_date(f)
    if task == "us-etf-holdings":
        latest = _latest_index_holdings_month()
        return latest if latest else None
    return None  # roe/qa/history 無單一資料日期


def cmd_holdings_run(args):
    """投信持股半月制：本期已成功來源不重抓；只跑失敗與未跑來源。部分失敗不擋 job（狀態記錄供補跑）。"""
    doc, state = _load_state()
    today = _today()
    period = _holdings_period(today)
    rec = state.get("tw-etf-holdings")
    if not isinstance(rec, dict) or rec.get("period") != period:
        rec = state["tw-etf-holdings"] = {"period": period}
    sources = rec.setdefault("sources", {})
    dry = args.dry_run
    failures = []
    ran = []
    for name, script in HOLDINGS_SOURCES:
        prev = sources.get(name) or {}
        if prev.get("period") == period and prev.get("status") == "succeeded" and not args.force:
            print(f"[holdings] {name}: 本期已成功，跳過")
            continue
        if dry:
            print(f"[holdings] {name}: dry-run 待執行（{script}）")
            ran.append(name)
            continue
        print(f"[holdings] {name}: 執行 {script}")
        p = subprocess.run([sys.executable, os.path.join(ROOT, script)])
        ok = p.returncode == 0
        sources[name] = {"period": period, "status": "succeeded" if ok else "failed",
                         "last_attempt": _now().isoformat(timespec="seconds")}
        ran.append(name)
        if not ok:
            failures.append(name)
    all_ok = not failures and ran
    rec["status"] = "succeeded" if all_ok else ("failed" if len(failures) == len(ran) and ran else "partial")
    rec["failed_sources"] = failures
    rec["last_attempt"] = _now().isoformat(timespec="seconds")
    if all_ok:
        rec["last_success"] = rec["last_attempt"]
    if not dry:
        _save_state(doc)  # dry-run 不得產生任何持久副作用（連 runner 本地狀態都不留）
    print(f"[holdings] 週期 {period}: 執行 {len(ran)} 來源，失敗 {failures or '無'} → status={rec['status']}")
    if dry:
        return 0
    # 全部來源都失敗才讓 job 紅（觸發 retry）；部分失敗＝partial，交由 21:00 補跑班補齊
    return 1 if (ran and len(failures) == len(ran)) else 0


def cmd_check(args):
    doc, state = _load_state()
    due, why = check_due(args.task, state)
    print(f"[update-state] {args.task}: {'DUE' if due else 'NOT-DUE'}（{why}）")
    return 0 if due else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=(__doc__ or "update_state").splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("task", choices=sorted(TASKS))
    r = sub.add_parser("record")
    r.add_argument("task", choices=sorted(TASKS))
    r.add_argument("--status", required=True, choices=["attempted", "succeeded", "failed"])
    r.add_argument("--failed-sources", default="")
    h = sub.add_parser("holdings-run")
    h.add_argument("--force", action="store_true", help="忽略 per-source 本期已成功，全部重抓")
    h.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "check":
        return cmd_check(args)
    if args.cmd == "record":
        return cmd_record(args)
    return cmd_holdings_run(args)


if __name__ == "__main__":
    sys.exit(main())
