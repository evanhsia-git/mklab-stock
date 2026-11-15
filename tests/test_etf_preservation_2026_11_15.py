#!/usr/bin/env python3
"""ETF 保留／停牌分割／市值與股本口徑（2026-11-15）的單元測試。

對應問題：
  1. 00662 富邦NASDAQ 因 5 拆 1 停牌 → 整檔從 stocks.json 消失
  2. price 為 null 卻留著舊 market_cap（4 筆）
  3. ETF capital_stock 為 0（233 筆）→ 前端顯示成「真實的零元」
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "data"))


def _load(name, sub="data"):
    path = os.path.join(ROOT, "skills", sub, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dr = _load("data_rules")
ss = _load("sanitize_snapshot")


class SanitizeRules(unittest.TestCase):
    def test_price_null_clears_market_cap(self):
        rec = {"sym": "00625K", "price": None, "market_cap": 3_800_000_000}
        notes = dr.sanitize_stock_record(rec)
        self.assertIsNone(rec["market_cap"])
        self.assertTrue(any("market_cap" in n for n in notes))
        # 再跑一次不得重複改（冪等）
        self.assertEqual(dr.sanitize_stock_record(rec), [])

    def test_valid_price_keeps_market_cap(self):
        rec = {"sym": "2330", "price": 2350.0, "market_cap": 60_000_000_000_000}
        dr.sanitize_stock_record(rec)
        self.assertEqual(rec["market_cap"], 60_000_000_000_000)

    def test_etf_capital_stock_zero_becomes_null(self):
        rec = {"sym": "0050", "security_type": "etf", "capital_stock": 0}
        notes = dr.sanitize_stock_record(rec)
        self.assertIsNone(rec["capital_stock"])
        self.assertTrue(any("ETF" in n for n in notes))

    def test_stock_capital_stock_zero_untouched(self):
        """一般股票的 0 是真的異常（要重抓財報），不可在這裡被改成 null。"""
        rec = {"sym": "1234", "security_type": "stock", "capital_stock": 0}
        dr.sanitize_stock_record(rec)
        self.assertEqual(rec["capital_stock"], 0)

    def test_etf_with_real_capital_stock_untouched(self):
        rec = {"sym": "0050", "security_type": "etf", "capital_stock": 1_000_000}
        dr.sanitize_stock_record(rec)
        self.assertEqual(rec["capital_stock"], 1_000_000)


class RestoreAndCorporateActions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="etfpres_")
        self._saved = (ss.ETf_CLASSIFIED, ss.ETF_META, ss.CORPORATE_ACTIONS, ss.KLINE_DIR)
        ss.ETf_CLASSIFIED = os.path.join(self.tmp, "etf-classified.json")
        ss.ETF_META = os.path.join(self.tmp, "etf-meta.json")
        ss.CORPORATE_ACTIONS = os.path.join(self.tmp, "corporate-actions.json")
        ss.KLINE_DIR = os.path.join(self.tmp, "kline")
        os.makedirs(ss.KLINE_DIR, exist_ok=True)
        self._json(ss.ETf_CLASSIFIED, {"etfs": [{"sym": "00662", "name": "富邦NASDAQ", "market": "TWSE"},
                                                 {"sym": "0050", "name": "元大台灣50", "market": "TWSE"}]})
        self._json(ss.ETF_META, {"etfs": [{"sym": "00662", "name": "富邦NASDAQ", "market": "TWSE",
                                           "listing_date": "2016-06-17"},
                                          {"sym": "0050", "name": "元大台灣50", "market": "TWSE",
                                           "listing_date": "2003-06-25"}]})
        self._json(os.path.join(ss.KLINE_DIR, "00662.json"),
                   {"sym": "00662", "fields": ["date", "open", "high", "low", "close"],
                    "rows": [["2026-11-09", 114.0, 114.65, 113.05, 114.4],
                             ["2026-11-10", 117.6, 118.0, 117.25, 117.8]]})

    def tearDown(self):
        (ss.ETf_CLASSIFIED, ss.ETF_META, ss.CORPORATE_ACTIONS, ss.KLINE_DIR) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    @staticmethod
    def _json(path, obj):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)

    def test_restore_missing_etf_keeps_identity_and_last_close(self):
        doc = {"stocks": [{"sym": "0050", "security_type": "etf"}]}
        notes = []
        added = ss.restore_missing_etfs(doc, notes)
        self.assertEqual(added, ["00662 富邦NASDAQ（最後成交 2026-11-10 收 117.8）"])
        rec = doc["stocks"][-1]
        self.assertEqual(rec["security_type"], "etf")
        self.assertTrue(rec["is_etf"])
        self.assertEqual(rec["name"], "富邦NASDAQ")
        self.assertEqual(rec["source"], "TWSE")
        self.assertEqual(rec["listing_date"], "2016-06-17")
        # 不冒充現價：price 留 null，最後成交價另存
        self.assertIsNone(rec["price"])
        self.assertEqual(rec["last_close"], 117.8)
        self.assertEqual(rec["last_close_date"], "2026-11-10")
        self.assertEqual(rec["price_asof"], "2026-11-10")
        self.assertEqual(rec["trading_status"], "suspended")
        self.assertIsNone(rec["capital_stock"])
        self.assertIsNone(rec["market_cap"])

    def test_restore_is_idempotent(self):
        doc = {"stocks": [{"sym": "0050"}]}
        ss.restore_missing_etfs(doc, [])
        n = len(doc["stocks"])
        self.assertEqual(ss.restore_missing_etfs(doc, []), [])
        self.assertEqual(len(doc["stocks"]), n)

    def test_restore_without_kline_does_not_invent_price(self):
        os.remove(os.path.join(ss.KLINE_DIR, "00662.json"))
        doc = {"stocks": []}
        ss.restore_missing_etfs(doc, [])
        rec = doc["stocks"][0]
        self.assertIsNone(rec["price"])
        self.assertIsNone(rec["last_close"])   # 沒有來源就不編造
        self.assertIsNone(rec["price_asof"])

    def test_corporate_action_marks_suspended_and_clears_price(self):
        self._json(ss.CORPORATE_ACTIONS, {"actions": [
            {"sym": "00662", "type": "split", "ratio": 5.0, "halt_from": "2026-11-11",
             "resume_date": "2026-11-17", "status": "pending", "source": "test"}]})
        doc = {"stocks": [{"sym": "00662", "price": 117.8, "chg": -0.2, "market_cap": 1}]}
        notes = []
        touched = ss.apply_corporate_actions(doc, notes, today="2026-11-15")
        rec = doc["stocks"][0]
        self.assertEqual(len(touched), 1)
        self.assertEqual(rec["trading_status"], "suspended")
        self.assertEqual(rec["suspended_reason"], "corporate_action")
        self.assertEqual(rec["halt_date"], "2026-11-11")
        self.assertEqual(rec["halt_resume"], "2026-11-17")
        for k in ("price", "chg", "market_cap"):
            self.assertIsNone(rec[k], k)
        self.assertEqual(rec["corporate_action"]["ratio"], 5.0)

    def test_corporate_action_not_applied_before_halt_date(self):
        """停止日還沒到就不該標停牌（例如事先登記未來要分割的標的）。"""
        self._json(ss.CORPORATE_ACTIONS, {"actions": [
            {"sym": "00662", "type": "split", "ratio": 5.0, "halt_from": "2026-12-01",
             "resume_date": "2026-12-08", "status": "pending", "source": "test"}]})
        doc = {"stocks": [{"sym": "00662", "price": 117.8, "trading_status": "active"}]}
        ss.apply_corporate_actions(doc, [], today="2026-11-15")
        rec = doc["stocks"][0]
        self.assertEqual(rec["trading_status"], "active")
        self.assertEqual(rec["price"], 117.8)
        self.assertIn("corporate_action", rec)   # 仍標示，供前端預告

    def test_done_actions_are_labeled_but_never_suspended(self):
        """已完成的分割仍要標示（畫面的「已分割 N:1」），但不可標成停牌清掉現價。"""
        self._json(ss.CORPORATE_ACTIONS, {"actions": [
            {"sym": "0052", "type": "split", "ratio": 7.0, "halt_from": "2025-11-19",
             "resume_date": "2025-11-26", "status": "done", "source": "test"}]})
        doc = {"stocks": [{"sym": "0052", "price": 44.1, "chg": 0.5, "market_cap": 1}]}
        ss.apply_corporate_actions(doc, [], today="2026-11-15")
        rec = doc["stocks"][0]
        self.assertEqual(rec["corporate_action"]["ratio"], 7.0)
        self.assertEqual(rec["corporate_action"]["status"], "done")
        self.assertNotIn("suspended_reason", rec)
        self.assertEqual(rec["price"], 44.1)     # 已復牌 → 現價不得被清

    def test_detected_action_is_not_applied(self):
        """自動偵測但未經確認者，不得寫入快照（避免把真實崩跌當成公司行為）。"""
        self._json(ss.CORPORATE_ACTIONS, {"actions": [
            {"sym": "00662", "type": "split", "ratio": 5.0, "resume_date": "2026-11-17",
             "status": "detected", "source": "auto:price_discontinuity"}]})
        doc = {"stocks": [{"sym": "00662", "price": 23.5}]}
        ss.apply_corporate_actions(doc, [], today="2026-11-20")
        self.assertNotIn("corporate_action", doc["stocks"][0])

    def test_missing_file_is_noop(self):
        doc = {"stocks": [{"sym": "0050"}]}
        self.assertEqual(ss.apply_corporate_actions(doc, [], today="2026-11-15"), [])
        self.assertNotIn("corporate_action", doc["stocks"][0])


class MetaRecompute(unittest.TestCase):
    def test_recompute(self):
        doc = {"meta": {"count": 999, "sources": {"X": 1}, "price_asof_counts": {"1999-01-01": 9}},
               "stocks": [{"sym": "a", "source": "TWSE", "price_asof": "2026-11-13"},
                          {"sym": "b", "source": "TPEX", "price_asof": "2026-11-13"},
                          {"sym": "c", "source": "TWSE", "price_asof": "2026-11-10"}]}
        ss.recompute_meta(doc)
        self.assertEqual(doc["meta"]["count"], 3)
        self.assertEqual(doc["meta"]["sources"], {"TWSE": 2, "TPEX": 1})
        self.assertEqual(doc["meta"]["price_asof_counts"], {"2026-11-13": 2, "2026-11-10": 1})


class QaExemption(unittest.TestCase):
    """QA 的異常漲跌規則必須排除公司行為，否則 00662 恢復交易日（11-17）會誤擋 CI。"""

    def test_qa_gate_exempts_corporate_action(self):
        src = open(os.path.join(ROOT, "skills", "qa-gate", "qa_gate.py"), encoding="utf-8").read()
        self.assertIn('if s_.get("corporate_action")', src)
        self.assertIn("公司行為", src)

    def test_data_rules_carry_etf_ref(self):
        """fetch_data 的沿用判定必須納入 ETF 清單，否則停牌 ETF 會整檔消失。"""
        src = open(os.path.join(ROOT, "skills", "data", "fetch_data.py"), encoding="utf-8").read()
        self.assertIn("_listed = set(capital_stock_map.keys()) | set(etf_ref or ())", src)


if __name__ == "__main__":
    unittest.main()
