"""
fetch_us_returns.py 的單元測試（不連網，使用合成價格序列）。
執行：python3 -m unittest tests/test_us_returns.py -v
"""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "skills", "data"))
import fetch_us_returns as fr  # noqa: E402


def _series(start, end, growth=0.0005, base=100.0):
    """工作日序列，每日複利 growth（不含假日，足以測試交易日索引）。"""
    out, d, i = [], start, 0
    while d <= end:
        if d.weekday() < 5:
            out.append((d, base * (1 + growth) ** i))
            i += 1
        d += dt.timedelta(days=1)
    return out


AS_OF = dt.date(2026, 11, 13)


class ComputeReturns(unittest.TestCase):
    def setUp(self):
        self.s = _series(dt.date(2025, 1, 1), AS_OF)
        self.closes = [c for _, c in self.s]
        self.last = self.closes[-1]

    def test_one_month_uses_21_sessions(self):
        r = fr.compute_returns(self.s, AS_OF)
        expect = round((self.last / self.closes[-1 - 21] - 1) * 100, 2)
        self.assertEqual(r["chg_1m"], expect)

    def test_one_year_uses_252_sessions(self):
        r = fr.compute_returns(self.s, AS_OF)
        expect = round((self.last / self.closes[-1 - 252] - 1) * 100, 2)
        self.assertEqual(r["chg_1y"], expect)

    def test_ytd_uses_last_close_of_previous_year(self):
        r = fr.compute_returns(self.s, AS_OF)
        prev = [c for d, c in self.s if d.year == 2025][-1]
        self.assertEqual(r["chg_ytd"], round((self.last / prev - 1) * 100, 2))

    def test_unsorted_input_is_handled(self):
        r1 = fr.compute_returns(self.s, AS_OF)
        r2 = fr.compute_returns(list(reversed(self.s)), AS_OF)
        self.assertEqual(r1, r2)

    def test_stale_data_returns_all_none(self):
        r = fr.compute_returns(self.s, AS_OF + dt.timedelta(days=10))
        self.assertEqual(r, {"chg_1m": None, "chg_ytd": None, "chg_1y": None})

    def test_seven_day_gap_still_accepted(self):
        r = fr.compute_returns(self.s, AS_OF + dt.timedelta(days=7))
        self.assertIsNotNone(r["chg_1m"])

    def test_short_history_leaves_long_windows_none(self):
        short = _series(dt.date(2026, 10, 1), AS_OF)  # 約 30 個交易日、無前一年資料
        r = fr.compute_returns(short, AS_OF)
        self.assertIsNotNone(r["chg_1m"])
        self.assertIsNone(r["chg_1y"])
        self.assertIsNone(r["chg_ytd"])

    def test_empty_or_bad_rows_ignored(self):
        bad = [(AS_OF, None), (AS_OF, float("nan")), (AS_OF, 0.0), (AS_OF, -5.0)]
        self.assertEqual(fr.compute_returns(bad, AS_OF)["chg_1m"], None)
        self.assertEqual(fr.compute_returns([], AS_OF)["chg_ytd"], None)

    def test_future_rows_after_as_of_are_excluded(self):
        future = self.s + [(AS_OF + dt.timedelta(days=3), 999999.0)]
        self.assertEqual(fr.compute_returns(future, AS_OF), fr.compute_returns(self.s, AS_OF))

    def test_extreme_value_becomes_none(self):
        s = [(dt.date(2025, 12, 31), 0.01), (AS_OF, 500.0)]
        self.assertIsNone(fr.compute_returns(s, AS_OF)["chg_ytd"])


def _rj(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _rt(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, doc, pretty=True):
    with open(path, "w", encoding="utf-8") as f:
        if pretty:
            f.write(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
        else:
            f.write(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sp = os.path.join(self.tmp, "us-stocks.json")
        self.ep = os.path.join(self.tmp, "us-etfs.json")
        _write(self.sp, {"meta": {"as_of": "x"}, "stocks": [
            {"sym": "AAPL", "price": 1, "chg_1m": 9.99},
            {"sym": "BAD", "price": 1, "chg_1m": 7.77},
        ]})
        _write(self.ep, {"meta": {"as_of": "x"}, "etfs": [
            {"sym": "VOO", "price": 1, "chg_1y": 8.88},
        ]})
        self.good = _series(dt.date(2025, 1, 1), AS_OF)

    def fetch(self, sym):
        if sym == "BAD":
            raise RuntimeError("rate limited")
        return self.good

    def test_success_updates_and_failure_keeps_old(self):
        rc = fr.run(self.sp, self.ep, fetch=self.fetch, as_of=AS_OF, sleep_sec=0)
        stocks = {x["sym"]: x for x in _rj(self.sp)["stocks"]}
        self.assertIsNotNone(stocks["AAPL"]["chg_1m"])
        self.assertIsNotNone(stocks["AAPL"]["chg_1y"])
        self.assertEqual(stocks["BAD"]["chg_1m"], 7.77)  # 失敗保留前次值
        self.assertEqual(rc, 0)  # 1/3 失敗，低於 50%

    def test_meta_lists_failures_per_file(self):
        fr.run(self.sp, self.ep, fetch=self.fetch, as_of=AS_OF, sleep_sec=0)
        sm = _rj(self.sp)["meta"]
        em = _rj(self.ep)["meta"]
        self.assertEqual(sm["returns_failed"], ["BAD"])
        self.assertEqual(em["returns_failed"], [])
        self.assertEqual(sm["returns_as_of"], AS_OF.isoformat())

    def test_etf_etfs_key_updated(self):
        fr.run(self.sp, self.ep, fetch=lambda s: self.good, as_of=AS_OF, sleep_sec=0)
        voo = _rj(self.ep)["etfs"][0]
        self.assertIsNotNone(voo["chg_1m"])
        self.assertIsNotNone(voo["chg_ytd"])

    def test_majority_failure_returns_nonzero(self):
        rc = fr.run(self.sp, self.ep, fetch=lambda s: (_ for _ in ()).throw(RuntimeError("down")),
                    as_of=AS_OF, sleep_sec=0)
        self.assertEqual(rc, 1)

    def test_pretty_format_preserved(self):
        fr.run(self.sp, self.ep, fetch=self.fetch, as_of=AS_OF, sleep_sec=0)
        raw = _rt(self.sp)
        self.assertTrue(raw.startswith("{\n"))
        self.assertTrue(raw.endswith("}\n"))

    def test_dry_run_does_not_write(self):
        before = _rt(self.sp)
        fr.run(self.sp, self.ep, fetch=self.fetch, as_of=AS_OF, sleep_sec=0, dry_run=True)
        self.assertEqual(_rt(self.sp), before)


class CarryOver(unittest.TestCase):
    """fetch_us_data 整檔覆寫時，須保留前次的月／年漲跌欄位。"""

    def test_return_fields_survive_overwrite(self):
        import fetch_us_data as fud  # noqa: E402
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "us-stocks.json")
            _write(p, {"stocks": [{"sym": "AAPL", "chg_1m": 3.5, "chg_1y": 20.1, "chg_ytd": 11.0}]})
            rows = [{"sym": "AAPL", "price": 300}, {"sym": "NEW", "price": 1}]
            fud.carry_return_fields(p, rows)
            self.assertEqual(rows[0]["chg_1m"], 3.5)
            self.assertEqual(rows[0]["chg_1y"], 20.1)
            self.assertNotIn("chg_1m", rows[1])

    def test_missing_old_file_is_noop(self):
        import fetch_us_data as fud  # noqa: E402
        rows = [{"sym": "AAPL"}]
        fud.carry_return_fields("/nonexistent/us-stocks.json", rows)
        self.assertEqual(rows, [{"sym": "AAPL"}])


class ReturnsCoverageRule(unittest.TestCase):
    def test_warns_when_monthly_return_mostly_missing(self):
        import data_rules as dr  # noqa: E402
        us = {"stocks": [{"sym": str(i), "chg_1m": None} for i in range(10)]}
        codes = {i["code"] for i in dr.validate_snapshot({"stocks": []}, us, None)}
        self.assertIn("US_RETURNS_MISSING", codes)

    def test_no_warning_when_covered(self):
        import data_rules as dr  # noqa: E402
        us = {"stocks": [{"sym": str(i), "chg_1m": 1.0} for i in range(10)]}
        codes = {i["code"] for i in dr.validate_snapshot({"stocks": []}, us, None)}
        self.assertNotIn("US_RETURNS_MISSING", codes)


if __name__ == "__main__":
    unittest.main()
