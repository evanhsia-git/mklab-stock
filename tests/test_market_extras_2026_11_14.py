#!/usr/bin/env python3
"""★ 官方加值資料（2026-11-14 導入）的單元測試。

覆蓋六個端點的解析、範圍過濾、停牌語意，以及整合的冪等與「不補值」保證。
"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "data"))


def _load(name):
    path = os.path.join(ROOT, "skills", "data", name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fme = _load("fetch_market_extras")
ime = _load("integrate_market_extras")


class RocDate(unittest.TestCase):
    def test_date_7digit(self):
        self.assertEqual(fme.roc_to_iso("1151110"), "2026-11-10")
        self.assertEqual(fme.roc_to_iso("1160101"), "2027-01-01")

    def test_month_5digit(self):
        self.assertEqual(fme.roc_to_iso("11510", "month"), "2026-10")
        # 5 碼傳成 date 模式、7 碼傳成 month 模式 → 一律 None，不猜
        self.assertIsNone(fme.roc_to_iso("11510"))
        self.assertIsNone(fme.roc_to_iso("1151110", "month"))

    def test_garbage_is_none(self):
        for v in ("", None, "abc", "115111", "11511100", "註"):
            self.assertIsNone(fme.roc_to_iso(v), v)


class NumParsing(unittest.TestCase):
    def test_blank_forms_are_null_not_zero(self):
        # 資料鐵律：官方沒給就是 null，不得變成 0
        for v in ("", "-", "--", "註", "N/A", None, "nan"):
            self.assertIsNone(fme.num(v), repr(v))

    def test_numbers(self):
        self.assertEqual(fme.num("1,234.5"), 1234.5)
        self.assertEqual(fme.num("12.34%"), 12.34)
        self.assertEqual(fme.num(-5), -5.0)


class ParseRevenue(unittest.TestCase):
    ROW = {"資料年月": "11510", "公司代號": "2330", "公司名稱": "台積電",
           "營業收入-當月營收": "586890319", "營業收入-上月營收": "511857399",
           "營業收入-去年當月營收": "367473051", "營業收入-上月比較增減(%)": "14.66",
           "營業收入-去年同月增減(%)": "59.71",
           "累計營業收入-當月累計營收": "4485617293", "累計營業收入-去年累計營收": "3130436902",
           "累計營業收入-前期比較增減(%)": "43.29"}

    def test_parse(self):
        out = fme.parse_revenue([self.ROW])["2330"]
        self.assertEqual(out["ym"], "2026-10")
        self.assertEqual(out["month"], 586890319.0)
        self.assertEqual(out["yoy"], 59.71)
        self.assertEqual(out["ytd_yoy"], 43.29)

    def test_out_of_scope_dropped(self):
        rows = [self.ROW, {**self.ROW, "公司代號": "030123"}]  # 權證（範圍外）
        self.assertEqual(list(fme.parse_revenue(rows)), ["2330"])

    def test_blank_fields_stay_null(self):
        out = fme.parse_revenue([{**self.ROW, "營業收入-本月營收": "",
                                 "營業收入-去年同月增減(%)": "-"}])["2330"]
        self.assertIsNone(out["yoy"])
        self.assertNotEqual(out["yoy"], 0)


class ParseMargin(unittest.TestCase):
    ROW = {"股票代號": "2330", "股票名稱": "台積電", "融資買進": "680", "融資賣出": "477",
           "融資現金償還": "83", "融資前日餘額": "32256", "融資今日餘額": "32376",
           "融資限額": "6483092", "融券買進": "20", "融券賣出": "5", "融券現券償還": "9",
           "融券前日餘額": "74", "融券今日餘額": "50", "融券限額": "6483092", "資券互抵": "3"}

    def test_parse(self):
        o = fme.parse_margin([self.ROW])["2330"]
        self.assertEqual(o["fin_bal"], 32376.0)
        self.assertEqual(o["sec_bal"], 50.0)
        self.assertEqual(o["offset"], 3.0)

    def test_etf_included(self):
        # MI_MARGN 含 ETF（可融資券），ETF 在站內範圍內 → 應保留
        self.assertIn("0050", fme.parse_margin([{**self.ROW, "股票代號": "0050"}]))


class ParseProfitabilityAndEps(unittest.TestCase):
    def test_profit_period(self):
        row = {"年度": "115", "季別": "3", "出表日期": "1151114", "公司代號": "2330",
               "營業收入(百萬元)": "3898726.97",
               "毛利率(%)(營業毛利)/(營業收入)": "66.79",
               "營業利益率(%)(營業利益)/(營業收入)": "59.05",
               "稅前純益率(%)(稅前純益)/(營業收入)": "63.13",
               "稅後純益率(%)(稅後純益)/(營業收入)": "52.40"}
        o = fme.parse_profitability([row])["2330"]
        self.assertEqual(o["period"], "2026Q3")
        self.assertEqual(o["gross_pct"], 66.79)
        self.assertEqual(o["asof"], "2026-11-14")

    def test_eps_is_cumulative_marked(self):
        row = {"年度": "115", "季別": "3", "出表日期": "1151114", "公司代號": "2330",
               "基本每股盈餘(元)": "78.75"}
        self.assertEqual(fme.parse_official_eps([row])["2330"]["eps_cum"], 78.75)


class HaltSemantics(unittest.TestCase):
    """TWTAWU 可能含『已恢復』的紀錄 → 只有仍在停止期間才算停牌。"""

    def test_past_halt_is_not_suspended(self):
        h = {"halt_date": "2026-11-10", "resume_date": "2026-11-11"}
        self.assertFalse(ime.is_halted_on(h, "2026-11-14"))  # 2314 台揚實例

    def test_ongoing_halt(self):
        h = {"halt_date": "2026-11-10", "resume_date": None}
        self.assertTrue(ime.is_halted_on(h, "2026-11-14"))

    def test_resume_day_counts_as_resumed(self):
        # 恢復日當天即已恢復交易（官方給的是恢復時點，如 08:00），
        # 因此 resume_date == today ⇒ 不算停牌。錯了會讓已恢復的股票一直被標停牌。
        h = {"halt_date": "2026-11-10", "resume_date": "2026-11-14"}
        self.assertFalse(ime.is_halted_on(h, "2026-11-14"))

    def test_future_halt_is_not_yet(self):
        h = {"halt_date": "2026-11-20", "resume_date": None}
        self.assertFalse(ime.is_halted_on(h, "2026-11-14"))

    def test_none(self):
        self.assertFalse(ime.is_halted_on(None, "2026-11-14"))


class MergeRecord(unittest.TestCase):
    EX = {"revenue": {"2330": {"ym": "2026-10", "month": 586890319.0, "mom": 14.66,
                               "yoy": 59.71, "ytd": 4485617293.0, "ytd_yoy": 43.29}},
          "margin": {"2330": {"fin_bal": 32376.0, "sec_bal": 50.0, "fin_prev": 32256.0,
                              "sec_prev": 74.0}},
          "profitability": {"2330": {"gross_pct": 66.79, "op_pct": 59.05, "net_pct": 52.4,
                                     "period": "2026Q3", "asof": "2026-11-14"}},
          "halts": {}}

    def test_does_not_embed_heavy_extras(self):
        """體積預算：月營收／融資融券／三率**不得**寫進 stocks.json（會讓單檔爆到 1,751 KB）。

        資料本體在 data/market-extras.json，由前端按需載入。
        """
        rec = {"sym": "2330", "trading_status": "active"}
        ime.merge_record(rec, self.EX, "2026-11-14")
        for k in ("rev_month", "rev_ym", "rev_yoy", "rev_ytd", "margin_fin", "margin_sec",
                  "gross_margin_off", "operating_margin_off", "net_margin_off", "profit_period"):
            self.assertNotIn(k, rec, k)
        # 未停牌者只多了兩個停牌欄位（且為 null）
        self.assertIsNone(rec["halt_date"])
        self.assertIsNone(rec["halt_resume"])
        self.assertEqual(rec["trading_status"], "active")

    def test_no_halt_gives_null_not_date(self):
        rec = {"sym": "9999"}
        ime.merge_record(rec, self.EX, "2026-11-14")
        self.assertIsNone(rec["halt_date"])
        self.assertIsNone(rec["halt_resume"])

    def test_idempotent(self):
        rec = {"sym": "2330"}
        ime.merge_record(rec, self.EX, "2026-11-14")
        first = dict(rec)
        ime.merge_record(rec, self.EX, "2026-11-14")
        self.assertEqual(first, rec)

    def test_ongoing_halt_marks_suspended(self):
        ex = {**self.EX, "halts": {"2330": {"halt_date": "2026-11-10", "resume_date": None}}}
        rec = {"sym": "2330", "trading_status": "active"}
        ime.merge_record(rec, ex, "2026-11-14")
        self.assertEqual(rec["trading_status"], "suspended")
        self.assertEqual(rec["suspended_reason"], "halt")
        self.assertEqual(rec["halt_date"], "2026-11-10")

    def test_halt_ended_resumes_only_own_suspension(self):
        ex = {**self.EX, "halts": {"2330": {"halt_date": "2026-11-10", "resume_date": "2026-11-11"}}}
        # 由本檔造成的停牌 → 應解除
        rec = {"sym": "2330", "trading_status": "suspended", "suspended_reason": "halt"}
        ime.merge_record(rec, ex, "2026-11-14")
        self.assertEqual(rec["trading_status"], "active")
        self.assertNotIn("suspended_reason", rec)

    def test_other_suspension_untouched(self):
        ex = {**self.EX, "halts": {"2330": {"halt_date": "2026-11-10", "resume_date": "2026-11-11"}}}
        # 別的原因造成的停牌（例如無當日成交價）不得被本檔解除
        rec = {"sym": "2330", "trading_status": "suspended"}
        ime.merge_record(rec, ex, "2026-11-14")
        self.assertEqual(rec["trading_status"], "suspended")


class CatalogConsistency(unittest.TestCase):
    """解析出的欄位名稱必須與整合腳本的對應表一致（防止改名後半邊失效）。"""

    def test_keys_align(self):
        rev_row = {"資料年月": "11510", "公司代號": "1101", "營業收入-當月營收": "1",
                   "營業收入-上月營收": "1", "營業收入-去年當月營收": "1",
                   "營業收入-上月比較增減(%)": "1", "營業收入-去年同月增減(%)": "1",
                   "累計營業收入-當月累計營收": "1", "累計營業收入-去年累計營收": "1",
                   "累計營業收入-前期比較增減(%)": "1"}
        parsed = fme.parse_revenue([rev_row])["1101"]
        self.assertEqual(set(parsed), {"ym", "month", "prev_month", "last_year_month",
                                       "mom", "yoy", "ytd", "ytd_last_year", "ytd_yoy"})


if __name__ == "__main__":
    unittest.main()
