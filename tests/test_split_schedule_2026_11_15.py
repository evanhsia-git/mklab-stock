#!/usr/bin/env python3
"""官方公司行為預告（ETF分割／減資）抓取：解析、冪等、自動登錄 planned。

對應 2026-11-15 Ivan 指示「把 TWTBAU1 接入每日更新，讓未來分割還沒發生就先知道」。

實測（2026-11-15）：TWSE `TWTBAU1`（暫停先賣後買當沖預告表）帶 Reason：
  0053 元大科技市值 1151127~1151203 Reason=ETF分割
  6108 競國        1151207~1151211 Reason=減資
TPEx `tpex_intraday_trading_pre` 為上櫃對應表。

設計原則：
  - 預告只給「區間＋原因」，**沒有比率** → 一律以 status=planned、ratio=null 登錄，
    絕不推測倍數（推測值會直接被拿去算還原價）。
  - planned 不會觸發停牌（sanitize 只對 pending + halt_from 生效），也不影響指標。
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "data"))

import fetch_split_schedule as fss  # noqa: E402
import corporate_actions as ca  # noqa: E402

TWSE_ROWS = [
    {"Code": "0053", "Name": "元大科技市值", "StartDate": "1151127", "EndDate": "1151203", "Reason": "ETF分割"},
    {"Code": "6108", "Name": "競國", "StartDate": "1151207", "EndDate": "1151211", "Reason": "減資"},
    {"Code": "0051", "Name": "元大中型100", "StartDate": "1151117", "EndDate": "1151123", "Reason": "分配收益"},
    {"Code": "006208", "Name": "富邦台50", "StartDate": "1151112", "EndDate": "1151118", "Reason": "受益人大會"},
]
TPEX_ROWS = [
    {"Date": "1151115~1151115", "SecuritiesCompanyCode": "00887", "CompanyName": "永豐中國科技50大",
     "FirstDayToSuspendSellThenBuy": "1141021", "DayOfReinstatingSellThenBuy": "1141027", "Reason": "ETF反分割"},
    {"Date": "1151115~1151115", "SecuritiesCompanyCode": "00740B", "CompanyName": "富邦全球投等債",
     "FirstDayToSuspendSellThenBuy": "1151112", "DayOfReinstatingSellThenBuy": "1151118", "Reason": "分配收益"},
]


class TestRocDate(unittest.TestCase):
    def test_roc_to_iso(self):
        self.assertEqual(fss.roc_to_iso("1151127"), "2026-11-27")
        self.assertEqual(fss.roc_to_iso("1140101"), "2025-01-01")

    def test_roc_to_iso_rejects_junk(self):
        for bad in ("", None, "abc", "115", "115112"):
            self.assertIsNone(fss.roc_to_iso(bad))


class TestClassify(unittest.TestCase):
    def test_known_reasons(self):
        self.assertEqual(fss.classify_reason("ETF分割"), "split")
        self.assertEqual(fss.classify_reason("ETF反分割"), "reverse_split")
        self.assertEqual(fss.classify_reason("減資"), "capital_reduction")
        self.assertEqual(fss.classify_reason("換發新股"), "split")

    def test_irrelevant_reasons_skipped(self):
        for r in ("分配收益", "受益人大會", "", "暫停交易"):
            self.assertIsNone(fss.classify_reason(r))


class TestParse(unittest.TestCase):
    def test_twse_keeps_only_split_like(self):
        ev = fss.parse_twse(TWSE_ROWS, source_url="https://example/twtbau1")
        self.assertEqual([e["sym"] for e in ev], ["0053", "6108"])
        self.assertEqual(ev[0]["kind"], "split")
        self.assertEqual(ev[0]["day_trade_suspend_from"], "2026-11-27")
        self.assertEqual(ev[0]["day_trade_suspend_to"], "2026-12-03")
        self.assertEqual(ev[1]["kind"], "capital_reduction")
        self.assertEqual(ev[0]["market"], "TWSE")
        self.assertTrue(ev[0]["source"].startswith("https://example"))

    def test_tpex_keeps_only_split_like(self):
        ev = fss.parse_tpex(TPEX_ROWS, source_url="https://example/tpex_pre")
        self.assertEqual([e["sym"] for e in ev], ["00887"])
        self.assertEqual(ev[0]["kind"], "reverse_split")
        self.assertEqual(ev[0]["market"], "TPEx")
        self.assertEqual(ev[0]["day_trade_suspend_from"], "2025-10-21")

    def test_bad_dates_dropped(self):
        rows = [{"Code": "1234", "Name": "x", "StartDate": "xx", "EndDate": "yy", "Reason": "減資"}]
        self.assertEqual(fss.parse_twse(rows, source_url="s"), [])


class TestScheduleFile(unittest.TestCase):
    def _events(self):
        return fss.parse_twse(TWSE_ROWS, source_url="u1") + fss.parse_tpex(TPEX_ROWS, source_url="u2")

    def test_write_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            fss.write_schedule(p, self._events(), sources={"TWSE_PRE": "u1"}, today="2026-11-15")
            first = open(p, encoding="utf-8").read()
            fss.write_schedule(p, self._events(), sources={"TWSE_PRE": "u1"}, today="2026-11-15")
            self.assertEqual(first, open(p, encoding="utf-8").read())
            doc = json.loads(first)
            self.assertEqual(doc["meta"]["count"], 3)
            self.assertEqual([e["sym"] for e in doc["events"]], sorted([e["sym"] for e in doc["events"]]))

    def test_upcoming_flag_uses_today(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            fss.write_schedule(p, self._events(), sources={}, today="2025-01-01")
            doc = json.load(open(p, encoding="utf-8"))
            self.assertTrue(all(e["when"] == "upcoming" for e in doc["events"]))
            fss.write_schedule(p, self._events(), sources={}, today="2027-01-01")
            doc = json.load(open(p, encoding="utf-8"))
            self.assertTrue(all(e["when"] == "past" for e in doc["events"]))


class TestRegisterPlanned(unittest.TestCase):
    def _reg(self, d):
        os.makedirs(os.path.join(d, "data"), exist_ok=True)
        p = os.path.join(d, "data", "corporate-actions.json")
        json.dump({"meta": {}, "actions": [
            {"sym": "0053", "type": "split", "ratio": 8.0, "resume_date": "2026-12-08",
             "status": "pending", "source": "Ivan"}]}, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        return p

    def test_adds_planned_without_ratio(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._reg(d)
            ev = fss.parse_twse(TWSE_ROWS, source_url="https://twse/1")
            added = fss.register_planned(p, ev, today="2026-11-15")
            self.assertEqual(added, ["6108"])          # 0053 已登錄 → 不重複
            acts = json.load(open(p, encoding="utf-8"))["actions"]
            new = [a for a in acts if a["sym"] == "6108"][0]
            self.assertEqual(new["status"], "planned")
            self.assertIsNone(new["ratio"])            # 預告沒有比率，不得推測
            self.assertTrue(new["source"])
            self.assertIn("1151207", new["source_note"])

    def test_planned_entries_are_not_used_for_adjustment(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._reg(d)
            fss.register_planned(p, fss.parse_twse(TWSE_ROWS, source_url="u"), today="2026-11-15")
            self.assertEqual([a["sym"] for a in ca.load_actions(root=d)], ["0053"])

    def test_register_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._reg(d)
            ev = fss.parse_twse(TWSE_ROWS, source_url="u")
            fss.register_planned(p, ev, today="2026-11-15")
            before = open(p, encoding="utf-8").read()
            added2 = fss.register_planned(p, ev, today="2026-11-15")
            self.assertEqual(added2, [])
            self.assertEqual(before, open(p, encoding="utf-8").read())


if __name__ == "__main__":
    unittest.main()
