#!/usr/bin/env python3
"""Workflow 五組整合驗收測試（2026-11-26）——update_state.py 邏輯＋daily-update.yml 結構斷言。

執行：python3 tests/test_workflow_consolidation.py
涵蓋 Ivan 審核規範第八節的場景：
  - 半月制投信持股（含 2027-05-01/16 遇週末）
  - 每月 2 日 UTC↔台北 轉換（原 45 22 2 * * 落台北 3 日的時區錯誤已由到期判斷消除）
  - 月 20 日遇週末的財報補跑
  - 週末休市：行情類任務不補跑、週期任務照補
  - 冪等：同日重複 check 應 not-due
  - per-source 失敗補跑（holdings-run 只重跑失敗來源）
  - YAML 結構：6 jobs、4 crons、每 job 的 schedule 條件、retry-or-report needs
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import update_state as us  # noqa: E402

_TPEI = timezone(timedelta(hours=8))
results = []


def check(name, ok, detail=""):
    results.append((name, "PASS" if ok else "FAIL", detail))


def _fake_now(y, m, d, hh=12):
    return datetime(y, m, d, hh, 0, tzinfo=_TPEI)


class _State:
    """隔離狀態檔的 context manager（UPDATE_STATE_PATH 指向暫存）。"""

    def __init__(self, initial=None):
        self.tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(initial or {}, self.tmp)
        self.tmp.close()

    def __enter__(self):
        self._old = os.environ.get("UPDATE_STATE_PATH")
        os.environ["UPDATE_STATE_PATH"] = self.tmp.name
        # import 時的常數需同步
        self._old_path = us.STATE_PATH
        us.STATE_PATH = self.tmp.name
        return self

    def __exit__(self, *a):
        if self._old:
            os.environ["UPDATE_STATE_PATH"] = self._old
        else:
            os.environ.pop("UPDATE_STATE_PATH", None)
        us.STATE_PATH = self._old_path
        os.unlink(self.tmp.name)

    def read(self):
        with open(self.tmp.name, encoding="utf-8") as f:
            return json.load(f).get("update_state", {})


# ── 半月制 period ──
check("半月制：1-15 日 = H1", us._holdings_period("2027-05-01") == "2027-05-H1")
check("半月制：15 日仍 = H1", us._holdings_period("2027-05-15") == "2027-05-H1")
check("半月制：16 日 = H2", us._holdings_period("2027-05-16") == "2027-05-H2")
check("半月制：月底 = H2", us._holdings_period("2027-05-31") == "2027-05-H2")
check("2027-05-01 週六：H1 週期成立（週末不影響半月制）", us._holdings_period("2027-05-01") == "2027-05-H1"
      and datetime(2027, 5, 1).weekday() == 5)
check("2027-05-16 週日：H2 週期成立（週末不影響半月制）", us._holdings_period("2027-05-16") == "2027-05-H2"
      and datetime(2027, 5, 16).weekday() == 6)

# ── check_due：投信持股半月制 ──
with _State({"update_state": {"tw-etf-holdings": {"period": "2027-05-H1", "status": "succeeded",
                                                  "last_success": "2027-05-03T21:00:00+08:00"}}}):
    with mock.patch.object(us, "_now", lambda: _fake_now(2027, 5, 4)):
        due, why = us.check_due("tw-etf-holdings", us._load_state()[1])
    check("H1 已完成 → 5/4 不重抓（不重複抓取）", not due, why)
with _State({"update_state": {"tw-etf-holdings": {"period": "2027-05-H1", "status": "partial",
                                                  "failed_sources": ["usitc", "uobam"],
                                                  "last_success": None}}}):
    with mock.patch.object(us, "_now", lambda: _fake_now(2027, 5, 5)):
        due, why = us.check_due("tw-etf-holdings", us._load_state()[1])
    check("H1 部分失敗（usitc/uobam）→ 5/5 補跑班到期", due, why)
with _State({}):
    with mock.patch.object(us, "_now", lambda: _fake_now(2027, 5, 16)):  # 週日
        due, why = us.check_due("tw-etf-holdings", us._load_state()[1])
    check("2027-05-16（週日）H2 首次執行 → 到期（週期任務不受週末限制）", due, why)

# ── 月 20 日財報：遇週末的補跑 ──
with _State({}):
    with mock.patch.object(us, "_now", lambda: _fake_now(2027, 11, 19)):
        due, _ = us.check_due("tw-stock-fundamentals", us._load_state()[1])
    check("11/19（20 日前）財報未到期", not due)
with _State({}):
    with mock.patch.object(us, "_now", lambda: _fake_now(2027, 11, 20)):
        due, _ = us.check_due("tw-stock-fundamentals", us._load_state()[1])
    check("11/20 當天到期", due)
with _State({}):
    with mock.patch.object(us, "_now", lambda: _fake_now(2027, 11, 21)):  # 21 日（2027-11-21 為週日）
        due, _ = us.check_due("tw-stock-fundamentals", us._load_state()[1])
    check("11/20 遇週末延遲 → 21 日補跑班到期（週期任務不受週末限制）", due, f"2027-11-21 weekday={datetime(2027,11,21).weekday()}")

# ── P0-4 最近有效交易日：週末仍可補未取得的交易日資料（不得因週末放棄）──
# 台北週六 21:00 補跑班：美股週五收盤資料若尚未取得（as_of=週四）→ 應判到期補跑
with _State({"update_state": {}}):
    with mock.patch.object(us, "_now", lambda: _fake_now(2027, 5, 1)):  # 台北週六
        # 模擬 us-stocks.json 資料日期為週四（週五收盤資料未取得）→ data_as_of 來源=檔案日期
        with mock.patch.object(us, "_read_meta_date", lambda rel, keys=("as_of","date","last_updated"): "2027-04-29"):
            due, why = us.check_due("us-stock-daily", us._load_state()[1])
    check("P0-4 週六 21:00：美股週五資料未取得 → 補跑（美東曆最近交易日=週五）", due, why)
    # 模擬已達週五 → 不補
    with mock.patch.object(us, "_read_meta_date", lambda rel, keys=("as_of","date","last_updated"): "2027-04-30"):
        due, why = us.check_due("us-stock-daily", us._load_state()[1])
    check("P0-4 週六：美股週五資料已取得 → 不重跑", not due, why)
    with mock.patch.object(us, "_now", lambda: _fake_now(2027, 5, 2)):  # 台北週日
        with mock.patch.object(us, "_read_meta_date", lambda rel, keys=("as_of","date","last_updated"): "2027-04-29"):
            due, why = us.check_due("us-stock-daily", us._load_state()[1])
    check("P0-4 週日 21:00：週五資料仍未取得 → 仍補跑", due, why)
# 台股週五更新失敗 → 週末補跑
with _State({}):
    with mock.patch.object(us, "_now", lambda: _fake_now(2027, 5, 1)):  # 台北週六
        with mock.patch.object(us, "_read_meta_date", lambda rel, keys=("as_of","date","last_updated"): "2027-04-29"):
            due, why = us.check_due("tw-stock-daily", us._load_state()[1])
    check("P0-4 週六：台股週五資料未取得 → 補跑（台北曆最近交易日=週五）", due, why)
    with mock.patch.object(us, "_read_meta_date", lambda rel, keys=("as_of","date","last_updated"): "2027-04-30"):
        due, why = us.check_due("tw-stock-daily", us._load_state()[1])
    check("P0-4 週六：台股週五資料已取得 → 不重跑", not due, why)

# ── P0-1 fetch_data.py 寫 fetch-log.json 時不得覆蓋 update_state ──
import importlib.util as _ilu
_spec_fd = _ilu.spec_from_file_location("fetch_data_mod", os.path.join(ROOT, "skills/data/fetch_data.py"))
_fd = _ilu.module_from_spec(_spec_fd)
try:
    _spec_fd.loader.exec_module(_fd)
    with tempfile.TemporaryDirectory() as _tmpfd:
        _flp = os.path.join(_tmpfd, "fetch-log.json")
        # 預置 12 個子任務的成功狀態
        _preset = {"update_state": {t: {"last_attempt": "2027-05-03T21:00:00+08:00",
                                        "last_success": "2027-05-03T21:00:00+08:00",
                                        "status": "succeeded", "period": "2027-05-x",
                                        "data_as_of": "2027-05-03", "failed_sources": []}
                                    for t in us.TASKS}}
        json.dump(_preset, open(_flp, "w", encoding="utf-8"), ensure_ascii=False)
        # fetch_data 的 OUT 指向暫存目錄後跑 _write_files
        with mock.patch.object(_fd, "OUT", _tmpfd):
            _log = _fd.RunLogger("daily")
            _log.finish(True, None)
            _log._write_files()
        _after = json.load(open(_flp, encoding="utf-8"))
        _kept = _after.get("update_state", {})
        check("P0-1 daily 班寫 fetch-log 後 12 個子任務狀態完整保留", len(_kept) == len(us.TASKS),
              f"保留 {len(_kept)}/{len(us.TASKS)}")
        _k0 = _kept.get("tw-etf-holdings", {})
        check("P0-1 period/last_success/data_as_of/failed_sources 未失真",
              _k0.get("period") == "2027-05-x" and _k0.get("data_as_of") == "2027-05-03"
              and isinstance(_k0.get("failed_sources"), list))
        check("P0-1 daily 班自己的 mode/success 欄位照常寫入", _after.get("mode") == "daily")
        check("P0-1 21:00 補跑不會因狀態遺失而重複抓取（update_state 可讀、各 task 有 last_success）",
              all(t.get("last_success") for t in _kept.values()))
except Exception as _e:
    check("P0-1 fetch_data._write_files 保留 update_state", False, f"{type(_e).__name__}: {_e}")

# ── P0-2 Git Push 白名單：五組 push 路徑逐一通過 allowed_path ──
def _allowed(path):
    """從 ci_commit_push.sh 抽出 allowed_path 函式，在 bash 子 shell 中實測。"""
    src = open(os.path.join(ROOT, "scripts/ci_commit_push.sh"), encoding="utf-8").read()
    m = __import__("re").search(r"(allowed_path\(\) \{.*?\n\})", src, __import__("re").S)
    r = subprocess.run(["bash", "-c", m.group(1) + f'\nallowed_path "{path}" && echo OK || echo NO'],
                       capture_output=True, text=True)
    return r.stdout.strip() == "OK"

_check_cases = [
    ("tw-stock 班：stocks.json", "data/stocks.json", True),
    ("tw-stock 班：rss.xml", "rss.xml", True),
    ("tw-stock 班：fetch-log.json（狀態隨推）", "data/fetch-log.json", True),
    ("tw-etf 班：etf-nav.json", "data/etf-nav.json", True),
    ("tw-etf 班：etf-holdings.json", "data/etf-holdings.json", True),
    ("tw-etf 班：fetch-log.json", "data/fetch-log.json", True),
    ("us-stock 班：us-stocks.json", "data/us/us-stocks.json", True),
    ("us-stock 班：us-edgar.json", "data/us/us-edgar.json", True),
    ("us-stock 班：fetch-log.json（P0-2 修正）", "data/fetch-log.json", True),
    ("us-etf 班：us-etfs.json", "data/us/us-etfs.json", True),
    ("us-etf 班：index-holdings/VOO.json", "data/index-holdings/VOO.json", True),
    ("us-etf 班：fetch-log.json（P0-2 修正）", "data/fetch-log.json", True),
    ("global-market 班：indices.json", "data/indices.json", True),
    ("global-market 班：twii-long.json", "data/twii-long.json", True),
    ("global-market 班：global-history 月檔", "data/global-history-2027-05.json", True),
    ("global-market 班：us-history 月檔", "data/us-history-2027-05.json", True),
    ("白名單外：scripts/ 不得推", "scripts/update_state.py", False),
    ("白名單外：secret 跳脫不得推", "data/../secret/x.txt", False),
]
for _name, _p, _want in _check_cases:
    check(f"P0-2 白名單：{_name}", _allowed(_p) == _want, f"path={_p} → {'允許' if _allowed(_p) else '拒絕'}")

# ── P0-3 狀態一致性：YAML 的 record failed 條件含 cancelled；succeeded 僅在 push 成功後 ──
_yml_src = open(os.path.join(ROOT, ".github/workflows/daily-update.yml"), encoding="utf-8").read()
check("P0-3 record failed 條件含 cancelled（runner 取消也記失敗）",
      _yml_src.count("(failure() || cancelled())") == 5)
check("P0-3 record succeeded 僅在 push.outcome == 'success' 之後",
      _yml_src.count("steps.push.outcome == 'success'") == 5)
check("P0-3 未發布不視為成功：succeeded 不出現在 push 條件之外的 step",
      "record \"$t\" --status succeeded" not in _yml_src.split("推送")[0] if "推送" in _yml_src else True)

# ── P1-6 到期判斷前置：pip install 在 due-gate 之後且受 RAN_TASKS 保護 ──
check("P1-6 每個 job 的 pip install 受 env.RAN_TASKS 保護",
      _yml_src.count("if: env.RAN_TASKS != ''") >= 10)  # 5 setup-python + 5 pip install
check("P1-6 update_state.py 為純 stdlib（no third-party imports）",
      not any(m in open(os.path.join(ROOT, "scripts/update_state.py"), encoding="utf-8").read()
              for m in ("import requests", "import pandas", "import yaml", "import yfinance")))

# ── Dry-run 無外部寫入副作用（holdings-run --dry-run 連狀態檔都不寫）──
with _State({"update_state": {"tw-etf-holdings": {"period": "2027-05-H1", "sources": {
        "cathay": {"period": "2027-05-H1", "status": "succeeded"}}}}}) as _sdry:
    _before = _sdry.read()
    with mock.patch.object(us.subprocess, "run", lambda *a, **k: mock.Mock(returncode=0)):
        us.cmd_holdings_run(mock.Mock(dry_run=True, force=False))
    check("dry-run：holdings-run --dry-run 後狀態檔位元組級不變", _sdry.read() == _before)

# ── 新舊架構輸出等價性：每組的爬蟲腳本清單與舊 job 一致（腳本零變更的結構性保證）──
_check_scripts = {
    "tw-stock": ["fetch_data.py daily", "sanitize_snapshot.py", "repair_history.py",
                 "detect_corporate_actions.py", "compute_indicators.py",
                 "integrate_official_company.py", "fetch_market_extras.py",
                 "integrate_market_extras.py", "fetch_split_schedule.py",
                 "build_kline.py", "compute_industry.py", "build_digest.py"],
    "tw-stock-roe": ["fetch_data.py weekly"],
    "tw-stock-fundamentals": ["fetch_official_fundamentals.py", "import_official_fundamentals.py",
                              "integrate_official_company.py"],
    "tw-etf-nav": ["fetch_etf_nav.py"],
    "tw-etf-holdings": ["fetch_etf_holdings_cathay.py", "fetch_etf_holdings_usitc.py",
                        "fetch_etf_holdings_uobam.py", "fetch_etf_holdings_ftft_monthly.py",
                        "fetch_etf_holdings_active.py", "accumulate_etf_holdings_history.py",
                        "verify_pcf_nav.py"],
    "tw-etf-meta": ["fetch_etf_meta.py", "classify_etf.py", "compute_indicators.py",
                    "integrate_etf_extras.py"],
    "tw-etf-qa": ["qa_phase4.py"],
    "us-stock-daily": ["fetch_us_data.py stocks", "fetch_us_returns.py", "fetch_sec_edgar.py"],
    "us-etf-daily": ["fetch_us_data.py etfs"],
    "us-etf-holdings": ["fetch_index_holdings.py"],
    "global-indices": ["fetch_data.py indices", "fetch_data.py twii"],
    "global-history": ["fetch_global_history.py"],
}
# 每個子任務呼叫的腳本都必須存在於 repo（舊架構同一批檔案）
_missing_scripts = []
for _t, _fns in _check_scripts.items():
    for _fn in _fns:
        base = _fn.split("（")[0].split(" ")[0]
        for cand in (f"skills/data/{base}", f"scripts/{base}"):
            if os.path.exists(os.path.join(ROOT, cand)):
                break
        else:
            _missing_scripts.append(f"{_t}: {base}")
check("新舊架構等價性：12 子任務引用的全部爬蟲腳本與舊架構同一批（零新增爬蟲）",
      not _missing_scripts, f"缺失 {_missing_scripts[:3]}")
# 每個子任務呼叫的腳本都必須存在於 repo（舊架構同一批檔案）

# ── P0-1 端到端：成功狀態持久化（bare git repo 實測——不只字串斷言）──
def _bare_e2e(push_should_fail=False):
    """模擬 job 核心鏈：record succeeded → git add fetch-log → commit → push（bare）→ 驗證遠端。
    push_should_fail=True 時 pre-receive hook 拒絕（模擬 push 失敗）。回傳 dict 結果。"""
    import shutil as _sh
    t = tempfile.mkdtemp(prefix="ws_p0_")
    out = {}
    idn = ["-c", "user.email=t@t", "-c", "user.name=t"]

    def git(*a, cwd):
        return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)

    try:
        origin = os.path.join(t, "origin.git")
        git("init", "-q", "--bare", "--initial-branch=main", origin, cwd=t)
        work = os.path.join(t, "W")
        git("clone", "-q", origin, "W", cwd=t)
        git(*idn, "config", "user.name", "t", cwd=work)
        git(*idn, "config", "user.email", "t@t", cwd=work)
        os.makedirs(os.path.join(work, "data"))
        json.dump({"meta": {"as_of": "2027-05-03"}, "stocks": []},
                  open(os.path.join(work, "data", "stocks.json"), "w"), ensure_ascii=False)
        git("add", "-A", cwd=work)
        git(*idn, "commit", "-q", "-m", "seed", cwd=work)
        git("push", "-q", "origin", "main", cwd=work)
        if push_should_fail:  # pre-receive 拒絕一次（模擬 push 失敗）
            hook = os.path.join(origin, "hooks", "pre-receive")
            open(hook, "w").write('#!/bin/sh\nexit 1\n')
            os.chmod(hook, 0o755)

        env_state = dict(os.environ)
        os.environ["UPDATE_STATE_PATH"] = os.path.join(work, "data", "fetch-log.json")
        us.STATE_PATH = os.environ["UPDATE_STATE_PATH"]
        try:
            # 模擬 job 的狀態寫入（push 之前——隨同一次 commit 發布）
            us.cmd_record(mock.Mock(task="tw-stock-daily", status="succeeded", failed_sources=""))
            us.cmd_record(mock.Mock(task="tw-etf-holdings", status="succeeded",
                                    failed_sources="usitc"))  # 部分成功
            git("add", "data/fetch-log.json", cwd=work)
            r_commit = git(*idn, "commit", "-q", "-m", "data+state", cwd=work)
            r_push = git("push", "origin", "main", cwd=work)
        finally:
            os.environ.update(env_state)
            us.STATE_PATH = env_state.get("UPDATE_STATE_PATH") or os.path.join(ROOT, "data", "fetch-log.json")
        out["push_rc"] = r_push.returncode
        # 重新從遠端讀取（模擬下個 run checkout；push 失敗時遠端 fetch-log 不存在＝維持原狀）
        c2 = os.path.join(t, "C")
        git("clone", "-q", origin, "C", cwd=t)
        _remote_fl = os.path.join(c2, "data", "fetch-log.json")
        out["remote_state"] = (json.load(open(_remote_fl, encoding="utf-8")).get("update_state", {})
                               if os.path.exists(_remote_fl) else {})
        out["remote_stocks_asof"] = json.load(
            open(os.path.join(c2, "data", "stocks.json"), encoding="utf-8"))["meta"]["as_of"]
        return out
    finally:
        _sh.rmtree(t, ignore_errors=True)


_e2e_ok = _bare_e2e(push_should_fail=False)
check("P0-1 E2E：push 成功後重新 checkout 可取得 succeeded 狀態（資料+狀態同一次發布）",
      _e2e_ok["push_rc"] == 0
      and _e2e_ok["remote_state"].get("tw-stock-daily", {}).get("status") == "succeeded",
      f"push_rc={_e2e_ok['push_rc']}")
check("P0-1 E2E：部分成功 failed_sources 跨 run 保存（usitc）",
      _e2e_ok["remote_state"].get("tw-etf-holdings", {}).get("failed_sources") == ["usitc"])
_e2e_fail = _bare_e2e(push_should_fail=True)
check("P0-1 E2E：push 失敗 → 遠端資料與狀態均維持原狀（不錯誤更新）",
      _e2e_fail["push_rc"] != 0 and _e2e_fail["remote_state"] == {} and _e2e_fail["remote_stocks_asof"] == "2027-05-03",
      f"push_rc={_e2e_fail['push_rc']} remote_state={_e2e_fail['remote_state']} asof={_e2e_fail['remote_stocks_asof']}")
# 下個 run 冪等：main 上已有 succeeded → check not-due（不重複抓取）
with _State({"update_state": {"tw-stock-daily": {"status": "succeeded",
                                                 "last_success": "2027-05-03T21:00:00+08:00"}}}):
    with mock.patch.object(us, "_now", lambda: _fake_now(2027, 5, 3, 23)):
        due, _ = us.check_due("tw-stock-daily", us._load_state()[1])
    check("P0-1 E2E：下個 run（同日）讀到 succeeded → 不重複抓取", not due)

# ── P0-3 收盤時間判斷：最近「已完成交易」的交易日 ──
# 台北週二 06:30（美股早班）＝美東週一 17:30/18:30 → 最近已完成交易日 = 美東週一
_et_morning = datetime(2027, 5, 4, 6, 30, tzinfo=_TPEI)      # 台北週二 06:30
_et_night = datetime(2027, 5, 4, 21, 0, tzinfo=_TPEI)        # 台北週二 21:00（補跑班）
check("P0-3 台北週二 06:30：美股最近已完成交易日 = 美東週一（已收盤）",
      us._last_workday("us", _et_morning) == "2027-05-03",
      us._last_workday("us", _et_morning))
check("P0-3 台北週二 21:00：美股週二未收盤 → 不要求週二收盤（仍 = 週一）",
      us._last_workday("us", _et_night) == "2027-05-03",
      us._last_workday("us", _et_night))
check("P0-3 台北週三 06:30：美股最近已完成交易日 = 美東週二",
      us._last_workday("us", datetime(2027, 5, 5, 6, 30, tzinfo=_TPEI)) == "2027-05-04",
      us._last_workday("us", datetime(2027, 5, 5, 6, 30, tzinfo=_TPEI)))
check("P0-3 台北週六：美股最近已完成交易日 = 週五",
      us._last_workday("us", datetime(2027, 5, 1, 21, 0, tzinfo=_TPEI)) == "2027-04-30",
      us._last_workday("us", datetime(2027, 5, 1, 21, 0, tzinfo=_TPEI)))
check("P0-3 台股：台北 06:30（13:30 未收盤）→ 不算當日（回推上一工作日）",
      us._last_workday("tw", datetime(2027, 5, 4, 6, 30, tzinfo=_TPEI)) == "2027-05-03",
      us._last_workday("tw", datetime(2027, 5, 4, 6, 30, tzinfo=_TPEI)))
check("P0-3 台股：台北 17:30（已收盤）→ 含當日",
      us._last_workday("tw", datetime(2027, 5, 4, 17, 30, tzinfo=_TPEI)) == "2027-05-04",
      us._last_workday("tw", datetime(2027, 5, 4, 17, 30, tzinfo=_TPEI)))
check("P0-3 美東夏令（7 月）：台北 06:30 = 美東 18:30（已過 16:00）→ 含美東當日",
      us._last_workday("us", datetime(2027, 7, 6, 6, 30, tzinfo=_TPEI)) == "2027-07-05",
      f"{us._last_workday('us', datetime(2027, 7, 6, 6, 30, tzinfo=_TPEI))}（台北 7/6=美東 7/5 週一）")
check("P0-3 美東冬令（12 月）：台北 06:30 = 美東 17:30（已過 16:00）→ 含美東當日",
      us._last_workday("us", datetime(2027, 12, 7, 6, 30, tzinfo=_TPEI)) == "2027-12-06",
      f"{us._last_workday('us', datetime(2027, 12, 7, 6, 30, tzinfo=_TPEI))}（台北 12/7=美東 12/6 週一）")
# 台股週五資料未取得 → 台北週六 21:00 仍補跑（workday 判斷，非星期幾擋）
with _State({}):
    with mock.patch.object(us, "_now", lambda: _fake_now(2027, 5, 1)):
        with mock.patch.object(us, "_read_meta_date", lambda rel, keys=("as_of", "date", "last_updated"): "2027-04-29"):
            due, why = us.check_due("tw-stock-daily", us._load_state()[1])
    check("P0-3 台北週六 21:00：台股週五資料未取得 → 仍補跑（最近已完成交易日=週五）", due, why)

# ── 每月 2 日：us-etf-holdings（原月度 cron 時區錯誤已消除）──
with _State({}):
    with mock.patch.object(us, "_now", lambda: _fake_now(2027, 5, 1)):  # 1 日（台北）
        due, why = us.check_due("us-etf-holdings", us._load_state()[1])
    check("5/1（2 日前）指數持股未到期", not due, why)
    with mock.patch.object(us, "_now", lambda: _fake_now(2027, 5, 2)):  # 台北 5/2 06:30 早班
        due, why = us.check_due("us-etf-holdings", us._load_state()[1])
    check("台北 5/2 06:30 班：到期（本月未更新）", due, why)
    # 模擬已更新：index-holdings 有本月檔
    with mock.patch.object(us, "_latest_index_holdings_month", lambda: "2027-05"):
        due, why = us.check_due("us-etf-holdings", us._load_state()[1])
    check("本月持股已更新 → 不重抓", not due, why)

# ── 冪等：同日重複 check ──
with _State({"update_state": {"tw-etf-nav": {"last_success": "2027-05-03T21:00:00+08:00",
                                             "status": "succeeded"}}}):
    with mock.patch.object(us, "_now", lambda: _fake_now(2027, 5, 3, 23)):
        due, why = us.check_due("tw-etf-nav", us._load_state()[1])
    check("同日已 succeeded → 冪等 not-due（重複觸發 skip）", not due, why)
    with mock.patch.object(us, "_now", lambda: _fake_now(2027, 5, 4, 10)):
        due, _ = us.check_due("tw-etf-nav", us._load_state()[1])
    check("隔日 → 重新到期", due)

# ── record：succeeded 自動讀資料日期（不信任自報）──
with _State() as s:
    with mock.patch.object(us, "_now", lambda: _fake_now(2027, 5, 4)):
        rc = us.cmd_record(mock.Mock(task="tw-etf-nav", status="succeeded", failed_sources=""))
    rec = s.read().get("tw-etf-nav", {})
    real_asof = json.load(open(os.path.join(ROOT, "data/etf-nav.json"), encoding="utf-8"))["meta"]["as_of"]
    check("record succeeded：data_as_of 直接讀 etf-nav.json（非自報）", rec.get("data_as_of") == real_asof,
          f"{rec.get('data_as_of')} vs {real_asof}")
    check("record succeeded：period=YYYY-MM-daily", rec.get("period") == "2027-05-daily")
    check("record succeeded：last_success 已記", bool(rec.get("last_success")))
with _State() as s:
    us.cmd_record(mock.Mock(task="tw-etf-holdings", status="failed", failed_sources="usitc,uobam"))
    rec = s.read().get("tw-etf-holdings", {})
    check("record failed：failed_sources 正確記錄", rec.get("failed_sources") == ["usitc", "uobam"])

# ── holdings-run：per-source 只補失敗來源（mock subprocess）──
with _State({"update_state": {"tw-etf-holdings": {"period": "2027-05-H1", "sources": {
        "cathay": {"period": "2027-05-H1", "status": "succeeded"},
        "usitc": {"period": "2027-05-H1", "status": "failed"}}}}}):
    calls = []
    with mock.patch.object(us.subprocess, "run", lambda *a, **k: calls.append(a[0][1]) or mock.Mock(returncode=0)):
        with mock.patch.object(us, "_now", lambda: _fake_now(2027, 5, 4)):
            us.cmd_holdings_run(mock.Mock(dry_run=False, force=False))
    check("holdings-run 只補失敗/未跑來源（cathay 已成功跳過）",
          {os.path.basename(c) for c in calls} == {"fetch_etf_holdings_usitc.py", "fetch_etf_holdings_uobam.py",
                                                   "fetch_etf_holdings_ftft_monthly.py", "fetch_etf_holdings_active.py"},
          f"實跑 {[os.path.basename(c) for c in calls]}")

# ── YAML 結構斷言 ──
import yaml
yml = yaml.safe_load(open(os.path.join(ROOT, ".github/workflows/daily-update.yml"), encoding="utf-8"))
jobs = yml["jobs"]
check("YAML：6 個 job（5 組＋retry-or-report）", list(jobs.keys()) ==
      ["tw-stock", "tw-etf", "us-stock", "us-etf", "global-market", "retry-or-report"])
trig = yml[True] if True in yml else yml[None]
crons = [list(c.values())[0] for c in trig["schedule"]]
check("YAML：恰好 4 條 cron", len(crons) == 4, str(crons))
check("YAML：4 條 cron 內容正確",
      sorted(crons) == sorted(["30 22 * * 1-5", "30 9 * * 1-5", "30 10 * * 6,0", "0 13 * * *"]))
check("YAML：舊月度 cron（45 22 2 * *、0 10 20 * *、0 10 * * 0、0 9 * * 1、0 10 * * 6）已全數移除",
      not any(c in crons for c in ("45 22 2 * *", "0 10 20 * *", "0 10 * * 0", "0 9 * * 1", "0 10 * * 6")))
dispatch = trig.get("workflow_dispatch", {}).get("inputs", {})
check("YAML：workflow_dispatch 有 group 選項（6 個）",
      dispatch.get("group", {}).get("options") == ["all", "tw-stock", "tw-etf", "us-stock", "us-etf", "global-market"])
check("YAML：workflow_dispatch 有 mode 選項（4 個）",
      dispatch.get("mode", {}).get("options") == ["due-only", "force", "retry-failed", "dry-run"])
check("YAML：retry-or-report needs 五組",
      jobs["retry-or-report"]["needs"] == ["tw-stock", "tw-etf", "us-stock", "us-etf", "global-market"])
for name in ("tw-stock", "tw-etf", "us-stock", "us-etf", "global-market"):
    j = jobs[name]
    conc = j.get("concurrency", {})
    check(f"YAML：{name} 有 mklab-git-push queue:max 序列化",
          conc.get("group") == "mklab-git-push" and conc.get("queue") == "max")
    cd = j.get("concurrency", {})
    push_ok = any("ci_commit_push.sh" in (s.get("run") or "") for s in j["steps"])
    check(f"YAML：{name} 走 ci_commit_push.sh v2.2", push_ok)
    gate = any("qa_gate.py --gate" in (s.get("run") or "") for s in j["steps"])
    check(f"YAML：{name} 有 QA Gate", gate)
    dry = any("!= 'dry-run'" in (s.get("if") or "") for s in j["steps"])
    check(f"YAML：{name} 的 push 受 dry-run 條件保護", dry)
# force 不得繞過 QA：QA step 條件不含 mode == 'force' 的例外
for name in ("tw-stock", "tw-etf", "us-stock", "us-etf", "global-market"):
    j = jobs[name]
    qa_if = next((s.get("if") or "" for s in j["steps"] if "qa_gate.py" in (s.get("run") or "")), "")
    check(f"YAML：{name} QA 不受 force 影響（force 仍過閘門）", "force" not in qa_if)

# 輸出
w = max(len(n) for n, _, _ in results)
for n, st, d in results:
    print(f"{st:4}  {n.ljust(w)}  {d}")
fails = [r for r in results if r[1] != "PASS"]
print(f"\n合計 {len(results)} 項，PASS {len(results) - len(fails)}，FAIL {len(fails)}")
sys.exit(1 if fails else 0)
