"""
2026-11-13 資料品質修正的回歸測試。
執行：python3 -m unittest tests/test_data_rules_2026_11_13.py -v
每個測試對應 docs/superpowers/plans/2026-11-13-data-quality-fix-plan.md 的一項根因。
"""
import copy
import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "skills", "data"))
import data_rules as dr  # noqa: E402


def _load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


class TaiwanCapitalAndMarketCap(unittest.TestCase):
    def test_balance_unit_thousand_to_twd(self):
        # 台積電 股本 259,303,804 仟元 → 2,593.04 億元
        self.assertEqual(dr.balance_capital_to_twd(259303804), 259303804 * 1000)

    def test_balance_zero_or_invalid_is_none(self):
        for bad in (0, -5, None, "", "abc", float("nan")):
            self.assertIsNone(dr.balance_capital_to_twd(bad), bad)

    def test_market_cap_tsmc_order_of_magnitude(self):
        cap = dr.balance_capital_to_twd(259303804)
        mc = dr.market_cap_from_capital(2395, cap)
        # 2395 × 25.93 億股 ≈ 6.2 兆元
        self.assertAlmostEqual(mc / 1e12, 62.1, delta=0.5)

    def test_market_cap_never_zero(self):
        self.assertIsNone(dr.market_cap_from_capital(0, 1e11))
        self.assertIsNone(dr.market_cap_from_capital(10, 0))
        self.assertIsNone(dr.market_cap_from_capital(None, 1e11))


class PeAndEps(unittest.TestCase):
    def test_negative_eps_drops_pe(self):
        # 福懋油 1225：EPS -1.3、PE 120.48 → PE 必須為 null
        self.assertIsNone(dr.sanitize_pe(120.48, -1.3))

    def test_zero_eps_drops_pe(self):
        self.assertIsNone(dr.sanitize_pe(50, 0))

    def test_positive_eps_keeps_pe(self):
        self.assertEqual(dr.sanitize_pe(14.2, 2.3), 14.2)

    def test_pe_out_of_range_dropped(self):
        self.assertIsNone(dr.sanitize_pe(1452.5, None))

    def test_mismatch_detection(self):
        # 微星 2377：價 145、EPS 15.18 → 價/EPS ≈ 9.55；PE 12.58 偏差 ≈ 24%（門檻 25% 以下）
        self.assertFalse(dr.pe_eps_mismatch(12.58, 145.0, 15.18))
        # 憶聲 3024：價 11.7、EPS 0.1 → 117；PE 195 明顯不一致
        self.assertTrue(dr.pe_eps_mismatch(195, 11.7, 0.1))
        # 無 EPS 時不判斷
        self.assertFalse(dr.pe_eps_mismatch(12, 10, None))


class UsUnits(unittest.TestCase):
    def test_ytd_not_scaled(self):
        # yfinance ytdReturn = 11.735（已是百分比）→ 11.74，不可變成 1173.5
        self.assertEqual(dr.us_ytd_pct(11.735), 11.73)  # float 四捨五入結果

    def test_ytd_out_of_range_none(self):
        self.assertIsNone(dr.us_ytd_pct(9999))
        self.assertIsNone(dr.us_ytd_pct(None))

    def test_dividend_from_rate_over_price(self):
        # AAPL：年股息 1.04 美元、價 354.88 → 約 0.29%，不可是 30
        info = {"currentPrice": 354.88, "dividendRate": 1.04, "dividendYield": 0.3}
        self.assertAlmostEqual(dr.us_dividend_yield_pct(info), 0.29, places=2)

    def test_dividend_fallback_and_cap(self):
        self.assertEqual(dr.us_dividend_yield_pct({"dividendYield": 0.30}), 0.3)
        self.assertIsNone(dr.us_dividend_yield_pct({"dividendYield": 58}))  # 超過 30% → None

    def test_pb_prefers_book_value(self):
        # BRK-B 類情況：priceToBook 失真（0.0011），用 price/bookValue
        info = {"currentPrice": 589.83, "bookValue": 400.0, "priceToBook": 0.0011}
        self.assertAlmostEqual(dr.us_price_to_book(info), 1.4746, places=3)

    def test_pb_absurd_is_none(self):
        self.assertIsNone(dr.us_price_to_book({"priceToBook": -113.5}))


class SnapshotSanitizeIdempotent(unittest.TestCase):
    def test_us_stock_div_batch_fix_once(self):
        doc = {"stocks": [{"sym": "AAPL", "div": 30.0}, {"sym": "AMZN", "div": 0.0}]}
        dr.sanitize_us_stocks_doc(doc)
        self.assertEqual(doc["stocks"][0]["div"], 0.3)
        self.assertEqual(doc["meta"]["units"]["div"], "pct")
        # 第二次執行不得再除一次
        dr.sanitize_us_stocks_doc(doc)
        self.assertEqual(doc["stocks"][0]["div"], 0.3)

    def test_us_etf_ytd_batch_fix_once(self):
        doc = {"etfs": [{"sym": "VOO", "ytd_return": 1173.5}, {"sym": "BND", "ytd_return": -42.84}]}
        dr.sanitize_us_etfs_doc(doc)
        self.assertEqual(doc["etfs"][0]["ytd_return"], 11.73)
        self.assertEqual(doc["etfs"][1]["ytd_return"], -0.43)
        dr.sanitize_us_etfs_doc(doc)
        self.assertEqual(doc["etfs"][0]["ytd_return"], 11.73)

    def test_stock_pe_sanitize_record(self):
        s = {"sym": "1225", "pe": 120.48, "eps": -1.3}
        dr.sanitize_stock_record(s)
        self.assertIsNone(s["pe"])


class ValidateSnapshotRules(unittest.TestCase):
    def _codes(self, issues):
        return {i["code"] for i in issues}

    def test_clean_synthetic_snapshot_has_no_errors(self):
        st = {"stocks": [{"sym": "2330", "security_type": "stock", "capital_stock": 2.6e11,
                          "price": 2395, "eps": 98.66, "pe": 24.28, "source": "TWSE",
                          "price_asof": "2026-11-12", "market_cap": 6.2e13}]}
        us = {"stocks": [{"sym": "AAPL", "div": 0.29, "pb": 46.0}]}
        ue = {"etfs": [{"sym": "VOO", "ytd_return": 11.73, "expense_ratio": 0.03}]}
        errs = [i for i in dr.validate_snapshot(st, us, ue) if i["level"] == "ERROR"]
        self.assertEqual(errs, [])

    def test_zero_capital_is_error(self):
        st = {"stocks": [{"sym": "2330", "security_type": "stock", "capital_stock": 0, "price": 1}]}
        self.assertIn("CAPITAL_ZERO", self._codes(dr.validate_snapshot(st)))

    def test_neg_eps_with_pe_is_error(self):
        st = {"stocks": [{"sym": "1225", "security_type": "stock", "eps": -1.3, "pe": 120.48,
                          "capital_stock": 1, "price": 25}]}
        self.assertIn("NEG_EPS_PE", self._codes(dr.validate_snapshot(st)))

    def test_twse_lag_one_session_is_warning_only(self):
        # TWSE STOCK_DAY_ALL 結構上只發 T-1、TPEX 發 T-0，落後 1 個交易日屬預期行為
        st = {"stocks": [
            {"sym": "2330", "source": "TWSE", "price_asof": "2026-11-11", "security_type": "stock", "capital_stock": 1, "price": 1},
            {"sym": "6488", "source": "TPEX", "price_asof": "2026-11-12", "security_type": "stock", "capital_stock": 1, "price": 1},
        ]}
        issues = dr.validate_snapshot(st)
        codes = self._codes(issues)
        self.assertIn("TWSE_T_MINUS_1", codes)
        self.assertNotIn("TWSE_STALE", codes)
        self.assertNotIn("ERROR", {i["level"] for i in issues})

    def test_twse_lag_two_sessions_is_error(self):
        # 落後 ≥2 個交易日才是真的沒更新（交易日曆取自快照內出現過的 price_asof）
        st = {"stocks": [
            {"sym": "2330", "source": "TWSE", "price_asof": "2026-11-10", "security_type": "stock", "capital_stock": 1, "price": 1},
            {"sym": "6488", "source": "TPEX", "price_asof": "2026-11-11", "security_type": "stock", "capital_stock": 1, "price": 1},
            {"sym": "6489", "source": "TPEX", "price_asof": "2026-11-12", "security_type": "stock", "capital_stock": 1, "price": 1},
        ]}
        self.assertIn("TWSE_STALE", self._codes(dr.validate_snapshot(st)))

    def test_same_date_not_stale(self):
        st = {"stocks": [
            {"sym": "2330", "source": "TWSE", "price_asof": "2026-11-12", "security_type": "stock", "capital_stock": 1, "price": 1},
            {"sym": "6488", "source": "TPEX", "price_asof": "2026-11-12", "security_type": "stock", "capital_stock": 1, "price": 1},
        ]}
        self.assertNotIn("TWSE_STALE", self._codes(dr.validate_snapshot(st)))

    def test_us_etf_unit_batch_detected(self):
        ue = {"etfs": [{"sym": s, "ytd_return": v} for s, v in
                       [("VOO", 1173.5), ("VTI", 1176.88), ("BND", -42.84), ("GLD", -946.29)]]}
        self.assertIn("US_YTD_UNIT", self._codes(dr.validate_snapshot({"stocks": []}, None, ue)))

    def test_us_div_unit_batch_detected(self):
        us = {"stocks": [{"sym": s, "div": v} for s, v in
                         [("KO", 217.0), ("PG", 260.0), ("JNJ", 191.0), ("AAPL", 30.0), ("MSFT", 75.0)]]}
        self.assertIn("US_DIV_UNIT", self._codes(dr.validate_snapshot({"stocks": []}, us, None)))


class RealSnapshotRegression(unittest.TestCase):
    """用 repo 內真實快照驗證：修正前一定有錯；套用確定性修正後，美股單位錯誤必須消失。

    2026-11-13 更新：股本與 TWSE 日期同日已用實抓資料修正（股本 1099/1099、TWSE 為 T-1），
    所以「股本為 0」的斷言改用固定的修正前樣本，不再耦合 data/stocks.json 的當下狀態
    （否則資料修好後測試會反過來失敗，變成「修好=壞掉」的假訊號）。
    """

    # 修正前的台股樣本（股本全為 0）：固定驗證 CAPITAL_ZERO 規則，不依賴線上快照狀態。
    PRE_FIX_TW = {"stocks": [
        {"sym": "2330", "source": "TWSE", "security_type": "stock", "capital_stock": 0,
         "price": 2395.0, "price_asof": "2026-11-11"},
        {"sym": "6488", "source": "TPEX", "security_type": "stock", "capital_stock": 0,
         "price": 100.0, "price_asof": "2026-11-12"},
    ]}

    @classmethod
    def setUpClass(cls):
        cls.stocks = _load("data/stocks.json")
        cls.us = _load("data/us/us-stocks.json")
        cls.ue = _load("data/us/us-etfs.json")

    def test_before_fix_units_are_flagged(self):
        # 使用修正前的原始快照（固定 fixture ＋ 固定台股樣本），確保回歸測試不隨資料變動而失效
        us_pre = _load("tests/fixtures/us-stocks-pre-2026-11-13.json")
        ue_pre = _load("tests/fixtures/us-etfs-pre-2026-11-13.json")
        codes = {i["code"] for i in dr.validate_snapshot(self.PRE_FIX_TW, us_pre, ue_pre)}
        self.assertIn("US_DIV_UNIT", codes)
        self.assertIn("US_YTD_UNIT", codes)
        self.assertIn("CAPITAL_ZERO", codes)

    def test_after_sanitize_us_units_clean(self):
        st, us, ue = copy.deepcopy(self.stocks), copy.deepcopy(self.us), copy.deepcopy(self.ue)
        dr.sanitize_us_stocks_doc(us)
        dr.sanitize_us_etfs_doc(ue)
        for r in st["stocks"]:
            dr.sanitize_stock_record(r)
        codes = {i["code"] for i in dr.validate_snapshot(st, us, ue) if i["level"] == "ERROR"}
        self.assertNotIn("US_DIV_UNIT", codes)
        self.assertNotIn("US_YTD_UNIT", codes)
        self.assertNotIn("US_DIV_RANGE", codes)
        self.assertNotIn("NEG_EPS_PE", codes)
        # 股本（已由官方實抓補齊）與 TWSE 日期（T-1 屬預期行為）都不應再是 ERROR
        self.assertNotIn("CAPITAL_ZERO", codes)
        self.assertNotIn("TWSE_STALE", codes)

    def test_sanitize_cannot_fix_capital_zero(self):
        # 快照確定性修正「不可能」修好股本（需要重抓官方資料）→ 修正後仍必須 ERROR，
        # 避免有人以為跑一下 sanitize_snapshot.py 就沒事。
        st = copy.deepcopy(self.PRE_FIX_TW)
        for r in st["stocks"]:
            dr.sanitize_stock_record(r)
        codes = {i["code"] for i in dr.validate_snapshot(st) if i["level"] == "ERROR"}
        self.assertIn("CAPITAL_ZERO", codes)


if __name__ == "__main__":
    unittest.main()


class CapitalUnitFuse(unittest.TestCase):
    def test_thousand_twd_unit_is_plausible(self):
        caps = [dr.balance_capital_to_twd(x) for x in [259303804, 3000000, 500000, 120000] * 15]
        self.assertTrue(dr.capital_unit_plausible(caps))

    def test_wrong_unit_is_rejected(self):
        # 若來源其實已是元（不是仟元），換算後股數會爆表 → 必須拒絕
        caps = [dr.balance_capital_to_twd(x) for x in [3e9, 5e8, 1.2e8, 2.6e11] * 15]
        self.assertFalse(dr.capital_unit_plausible(caps))

    def test_too_few_rows_rejected(self):
        self.assertFalse(dr.capital_unit_plausible([1e10] * 10))
