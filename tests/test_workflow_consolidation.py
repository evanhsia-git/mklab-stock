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

# ── 週末休市：行情類不補跑 ──
with _State({}):
    with mock.patch.object(us, "_now", lambda: _fake_now(2027, 5, 1)):  # 週六
        due, why = us.check_due("tw-stock-daily", us._load_state()[1])
    check("週六：tw-stock-daily 不補跑（休市）", not due, why)
    with mock.patch.object(us, "_now", lambda: _fake_now(2027, 5, 2)):  # 週日
        due, _ = us.check_due("us-stock-daily", us._load_state()[1])
    check("週日：us-stock-daily 不補跑（休市）", not due)
    with mock.patch.object(us, "_now", lambda: _fake_now(2027, 5, 3)):  # 週一
        due, _ = us.check_due("tw-stock-daily", us._load_state()[1])
    check("週一：tw-stock-daily 到期（正常補跑）", due)

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
