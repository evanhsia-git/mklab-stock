"""美股 DCF 估值欄位測試：python3 -m unittest tests/test_us_valuation_fields.py"""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "skills", "data"))
import data_rules as dr  # noqa: E402


class UsValuationInputs(unittest.TestCase):
    def test_units_are_millions(self):
        info = {"freeCashflow": 99_584_000_000, "totalCash": 61_000_000_000,
                "totalDebt": 98_000_000_000, "sharesOutstanding": 14_776_353_000}
        v = dr.us_valuation_inputs(info)
        self.assertEqual(v["fcf_musd"], 99584.0)
        self.assertEqual(v["cash_musd"], 61000.0)
        self.assertEqual(v["debt_musd"], 98000.0)
        self.assertAlmostEqual(v["shares_mln"], 14776.353, places=3)

    def test_missing_fields_are_none_not_zero(self):
        v = dr.us_valuation_inputs({})
        self.assertEqual(v, {"fcf_musd": None, "cash_musd": None, "debt_musd": None,
                             "shares_mln": None, "fcf_source": None, "cash_source": None,
                             "debt_source": None, "shares_source": "yfinance_info_sharesOutstanding",
                             "shares_is_estimated": False})

    def test_zero_or_bad_shares_rejected(self):
        self.assertIsNone(dr.us_valuation_inputs({"sharesOutstanding": 0})["shares_mln"])
        self.assertIsNone(dr.us_valuation_inputs({"sharesOutstanding": "x"})["shares_mln"])

    def test_negative_fcf_kept_as_is(self):
        # 負的自由現金流是真實資料，不應被清成 null（DCF 端會以 ok=false 說明原因）
        v = dr.us_valuation_inputs({"freeCashflow": -5_000_000})
        self.assertEqual(v["fcf_musd"], -5.0)


if __name__ == "__main__":
    unittest.main()
