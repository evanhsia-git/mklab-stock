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


# 每日行情類：台股/美股週末休市，補跑班與手動 due-only 不在週末觸發
#（週六/日的正常班不受影響——正常班不做 check）。週期任務（ROE/meta/QA/月度）不受限。
MARKET_CLOSED_TASKS = {"tw-stock-daily", "us-stock-daily", "us-etf-daily"}


def check_due(task, state):
    """回傳 (due: bool, 說明)。到期＝今天(台北)尚未 succeeded，且資料日期落後或屬週期任務。"""
    info = TASKS.get(task)
    if info is None:
        raise SystemExit(f"unknown task: {task}")
    today = _today()
    rec = state.get(task) or {}
    if task in MARKET_CLOSED_TASKS and _now().weekday() >= 5:
        return False, "週末休市，行情類任務不補跑（下一個交易日的正常班會抓取）"
    last_success = rec.get("last_success")
    # last_success 存完整 ISO datetime（record 寫入時帶時分秒）——比較一律取日期部分 [:10]
    if last_success and last_success[:10] == today and rec.get("status") == "succeeded":
        return False, f"今天已 succeeded（{last_success}）"
    if last_success and last_success[:10] > today:
        return False, f"last_success {last_success} 在未來（時鐘異常防護）"

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
        # 半月制：本期（H1/H2）未全數成功 → due（per-source 由 holdings-run 判斷）
        period = _holdings_period(today)
        hrec = rec.get("period") == period and rec.get("status") == "succeeded"
        return (not hrec), f"本期 {period} " + ("已完成" if hrec else "未完成")
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
        rec["last_success"] = now
        rec["period"] = _current_period(args.task)
        data_as_of = _auto_data_as_of(args.task)
        if data_as_of:
            rec["data_as_of"] = data_as_of
    _save_state(doc)
    print(f"[update-state] {args.task}: status={args.status} recorded")
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
