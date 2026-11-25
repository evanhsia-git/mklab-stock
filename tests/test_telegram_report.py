#!/usr/bin/env python3
"""telegram_report v1.1 分派規則單元測試（mock API）＋組裝煙霧測試。

防濫發分派規則是 Phase 7 的核心契約：
- daily-update failure/cancelled → P0 彙整告警
- daily-update success 且 daily job success → 每日報告
- daily-update success 但 daily job skipped（其他班次）→ 靜默
- qa-gate failure → P0；success → 靜默
- pages failure → P0；success → 靜默
- 未監聽的 workflow → 靜默
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import telegram_report as tr  # noqa: E402

RUN = {"id": 1, "name": "daily-update", "conclusion": "success", "head_sha": "a" * 8,
       "html_url": "u", "run_started_at": "2026-11-25T09:00:00Z",
       "updated_at": "2026-11-25T09:01:00Z"}


def jobs_payload(name="daily", conclusion="success"):
    return {"jobs": [{"name": name, "conclusion": conclusion}]}


class 分派規則(unittest.TestCase):
    def setUp(self):
        self.token = "github_pat_test"

    def test_01_daily_failure告警(self):
        with mock.patch.object(tr, "_get", return_value=jobs_payload("daily", "failure")):
            notify, msg = tr.decide_and_build("daily-update", "failure", dict(RUN), self.token)
        self.assertTrue(notify)
        self.assertIn("每日更新失敗", msg)

    def test_02_daily_success發每日報告(self):
        with mock.patch.object(tr, "_get", return_value=jobs_payload("daily", "success")):
            notify, msg = tr.decide_and_build("daily-update", "success", dict(RUN), self.token)
        self.assertTrue(notify)
        self.assertIn("每日系統報告", msg)

    def test_03_其他班次run靜默(self):
        with mock.patch.object(tr, "_get", return_value=jobs_payload("daily", "skipped")):
            notify, _ = tr.decide_and_build("daily-update", "success", dict(RUN), self.token)
        self.assertFalse(notify)

    def test_04_qa_gate_failure告警(self):
        with mock.patch.object(tr, "_get", return_value={"artifacts": []}):
            notify, msg = tr.decide_and_build("qa-gate", "failure", dict(RUN), self.token)
        self.assertTrue(notify)
        self.assertIn("QA 異常", msg)

    def test_05_qa_gate_success靜默(self):
        notify, _ = tr.decide_and_build("qa-gate", "success", dict(RUN), self.token)
        self.assertFalse(notify)

    def test_06_pages_failure告警與success靜默(self):
        n1, m1 = tr.decide_and_build("pages build and deployment", "failure", dict(RUN), self.token)
        self.assertTrue(n1)
        self.assertIn("Pages 部署失敗", m1)
        n2, _ = tr.decide_and_build("pages build and deployment", "success", dict(RUN), self.token)
        self.assertFalse(n2)

    def test_07_未監聽workflow靜默(self):
        notify, _ = tr.decide_and_build("some-other", "failure", dict(RUN), self.token)
        self.assertFalse(notify)

    def test_08_cancelled不是PASS(self):
        # cancelled 視為需告警的非正常結束，絕不當成功
        with mock.patch.object(tr, "_get", return_value=jobs_payload("daily", "cancelled")):
            notify, _ = tr.decide_and_build("daily-update", "cancelled", dict(RUN), self.token)
        self.assertTrue(notify)


class 資料誠信(unittest.TestCase):
    def test_09_線上資料取不到時標NA而非猜測(self):
        with mock.patch.object(tr, "_fetch_json_or_none", return_value=None), \
             mock.patch.object(tr, "_get", return_value={"workflow_runs": []}):
            msg = tr.build_daily_report(dict(RUN), None)
        self.assertIn("N/A", msg)
        self.assertIn("UNKNOWN", msg)
        self.assertIn("LKG 狀態：未啟用", msg)  # 不得宣稱 LKG 可用

    def test_10_錯誤訊息遮蔽token(self):
        masked = tr.mask_secret("artifact 下載失敗 Bearer github_pat_ABCDEF1234567890xyz")
        self.assertNotIn("github_pat_ABCDEF1234567890xyz", masked)


if __name__ == "__main__":
    unittest.main(verbosity=2)
