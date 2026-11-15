#!/usr/bin/env python3
"""公司行為（ETF 分割）處理：還原價、死值列剔除、自動偵測。

對應 2026-11-15 Ivan 指示：「能完整應對未來其他 ETF 產生股票拆分的情況，可以立即回應與改善」。
設計：選項 1（只有技術指標用還原價，畫面顯示原始價＋已分割標註）＋ 自動偵測 ＋ 死值剔除。

實測事實（本測試以此為斷言基礎，不依賴猜測）：
  0052 富邦科技  2025-11-18 收 245.3 →（11-19~11-25 五列 o=h=l=c=60.6 且 vol 完全相同）
                 → 2025-11-26 收 35.35；245.3/35.35 = 6.94 ≈ 公告 7
  00631L 元大台灣50正2 2026-03-24 收 443.15 →（03-25~03-30 四列 35.26、vol 相同）→ 03-31 收 19.26
  00685L 群益臺灣加權正2 2026-06-30 收 306.0 → 2026-07-07 收 12.23（無死值列，history 該兩日無此檔）
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "data"))

import corporate_actions as ca  # noqa: E402


def _mk(root, actions):
    os.makedirs(os.path.join(root, "data", "kline"), exist_ok=True)
    with open(os.path.join(root, "data", "corporate-actions.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": {}, "actions": actions}, f, ensure_ascii=False)


class TestLoadActions(unittest.TestCase):
    def test_entry_without_source_is_ignored(self):
        """沒有來源的公司行為不得套用（Ivan 的資料原則：每筆都要有依據）。"""
        with tempfile.TemporaryDirectory() as t:
            _mk(t, [
                {"sym": "1111", "type": "split", "ratio": 2, "halt_from": "2026-01-05",
                 "resume_date": "2026-01-10", "status": "done", "source": "官方公告"},
                {"sym": "2222", "type": "split", "ratio": 2, "halt_from": "2026-01-05",
                 "resume_date": "2026-01-10", "status": "done", "source": ""},
            ])
            acts = ca.load_actions(root=t)
            self.assertEqual([a["sym"] for a in acts], ["1111"])

    def test_unconfirmed_detected_entries_excluded_by_default(self):
        """自動偵測但未經確認者，預設不得套用到指標（避免把真實崩跌當成分割還原掉）。"""
        with tempfile.TemporaryDirectory() as t:
            _mk(t, [
                {"sym": "3333", "type": "split", "ratio": 3, "resume_date": "2026-02-02",
                 "status": "detected", "source": "auto:price_discontinuity"},
                {"sym": "4444", "type": "split", "ratio": 3, "resume_date": "2026-02-02",
                 "status": "done", "source": "官方公告"},
            ])
            self.assertEqual([a["sym"] for a in ca.load_actions(root=t)], ["4444"])
            self.assertEqual([a["sym"] for a in ca.load_actions(root=t, include_unconfirmed=True)],
                             ["3333", "4444"])

    def test_missing_ratio_or_dates_is_ignored(self):
        """倍數或事件日期不明的登錄不可用於還原（沒有基準就無法還原，不可猜）。"""
        with tempfile.TemporaryDirectory() as t:
            _mk(t, [
                {"sym": "5555", "type": "split", "ratio": None, "resume_date": "2026-01-05",
                 "status": "planned", "source": "新聞"},
                {"sym": "6666", "type": "split", "ratio": 8, "resume_date": None,
                 "halt_from": None, "status": "planned", "source": "新聞"},
            ])
            self.assertEqual(ca.load_actions(root=t), [])


class TestAdjustRows(unittest.TestCase):
    ROWS = [("20260101", 100.0, 101.0, 99.0, 100.0),
            ("20260102", 90.0, 92.0, 89.0, 91.0),      # 事件前最後一根
            ("20260105", 20.0, 20.5, 19.5, 20.0),      # 停牌後復牌（÷5）
            ("20260106", 21.0, 21.5, 20.5, 21.0)]
    ACT = [{"sym": "9999", "type": "split", "ratio": 5.0, "halt_from": "2026-01-03",
            "resume_date": "2026-01-05", "status": "done", "source": "官方"}]

    def test_pre_event_rows_are_divided_by_ratio(self):
        out, applied = ca.adjust_rows("9999", self.ROWS, self.ACT)
        self.assertEqual(out[0][4], 20.0)   # 100 / 5
        self.assertEqual(out[1][4], 18.2)   # 91 / 5
        self.assertEqual(out[1][1], 18.0)   # open 90 / 5
        self.assertEqual(out[1][2], 18.4)   # high 92 / 5
        self.assertEqual(out[1][3], 17.8)   # low 89 / 5
        self.assertEqual(out[2][4], 20.0)   # 事件當日（復牌）不動
        self.assertEqual(out[3][4], 21.0)
        self.assertEqual(applied[0]["ratio"], 5.0)

    def test_series_becomes_continuous(self):
        """還原後相鄰日漲跌幅必須落在合理範圍（原本 91 → 20 是 -78%）。"""
        out, _ = ca.adjust_rows("9999", self.ROWS, self.ACT)
        pct = abs(out[2][4] / out[1][4] - 1)
        self.assertLess(pct, 0.15)

    def test_other_symbol_and_no_event_untouched(self):
        out, applied = ca.adjust_rows("8888", self.ROWS, self.ACT)
        self.assertEqual(out, self.ROWS)
        self.assertEqual(applied, [])

    def test_idempotent_when_called_on_already_adjusted(self):
        """只依「日期 < 事件日」判定，重複套用不會二次除。"""
        out1, _ = ca.adjust_rows("9999", self.ROWS, self.ACT)
        out2, _ = ca.adjust_rows("9999", out1, self.ACT)
        self.assertEqual([r[4] for r in out2], [r[4] for r in out1])


class TestImpliedRatio(unittest.TestCase):
    def test_implied_ratio(self):
        self.assertAlmostEqual(ca.implied_ratio(245.3, 35.35), 6.94, places=2)
        self.assertAlmostEqual(ca.implied_ratio(306.0, 12.23), 25.02, places=2)

    def test_implied_ratio_none_on_bad_input(self):
        self.assertIsNone(ca.implied_ratio(None, 10))
        self.assertIsNone(ca.implied_ratio(10, 0))


class TestDeadRuns(unittest.TestCase):
    def _rows(self):
        return [("20251118", 247.85, 247.95, 243.2, 245.3, 12055630),
                ("20251119", 60.6, 60.6, 60.6, 60.6, 51417349),
                ("20251120", 60.6, 60.6, 60.6, 60.6, 51417349),
                ("20251121", 60.6, 60.6, 60.6, 60.6, 51417349),
                ("20251124", 60.6, 60.6, 60.6, 60.6, 51417349),
                ("20251125", 60.6, 60.6, 60.6, 60.6, 51417349),
                ("20251126", 35.38, 35.4, 35.2, 35.35, 272824460)]

    def test_mid_series_dead_run_found(self):
        runs = ca.find_dead_runs(self._rows())
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["dates"], ["20251119", "20251120", "20251121", "20251124", "20251125"])

    def test_real_rows_with_moving_volume_not_flagged(self):
        rows = [("20260102", 10.0, 10.0, 10.0, 10.0, 100),
                ("20260103", 10.0, 10.0, 10.0, 10.0, 250),   # 一字平盤但量不同＝真實
                ("20260104", 10.0, 10.0, 10.0, 10.0, 300)]
        self.assertEqual(ca.find_dead_runs(rows), [])

    def test_short_run_below_threshold_ignored(self):
        rows = [("20260102", 10.0, 10.0, 10.0, 10.0, 100),
                ("20260103", 10.0, 10.0, 10.0, 10.0, 100),
                ("20260104", 11.0, 11.0, 11.0, 11.0, 500)]
        self.assertEqual(ca.find_dead_runs(rows), [])


class TestRepairHistoryDeadRuns(unittest.TestCase):
    """repair_history 原本只檢查「開頭前導」的補值列，中段（停牌復牌）的漏掉 → 0052/00631L 存活。"""

    def _snaps(self):
        seq = {
            "20251118": (247.85, 247.95, 243.2, 245.3, 12055630),
            "20251119": (60.6, 60.6, 60.6, 60.6, 51417349),
            "20251120": (60.6, 60.6, 60.6, 60.6, 51417349),
            "20251121": (60.6, 60.6, 60.6, 60.6, 51417349),
            "20251126": (35.38, 35.4, 35.2, 35.35, 272824460),
        }
        snaps = []
        for date, (o, h, l, c, v) in sorted(seq.items()):
            rows = [{"stock_id": "0052", "stock_name": "富邦科技", "open": o, "high": h,
                     "low": l, "close": c, "volume": v},
                    {"stock_id": "2330", "stock_name": "台積電", "open": 1400.0, "high": 1415.0,
                     "low": 1395.0, "close": 1395.0, "volume": 42661060}]
            snaps.append((f"/tmp/{date}.json", {"trade_date": date, "stocks": rows}, rows))
        return snaps

    def test_mid_series_dead_rows_are_marked(self):
        import repair_history as rh
        marked, detail = rh.find_dead_rows(self._snaps())
        self.assertEqual(sorted(d for d, s in marked), ["20251119", "20251120", "20251121"])
        self.assertTrue(all(s == "0052" for _, s in marked))
        self.assertEqual(detail[0]["dead_days"], 3)

    def test_normal_symbol_not_marked(self):
        import repair_history as rh
        marked, _ = rh.find_dead_rows(self._snaps())
        self.assertNotIn(("20251119", "2330"), marked)


class TestDetector(unittest.TestCase):
    def test_scan_series_finds_jump(self):
        rows = [("20260102", 100, 101, 99, 100), ("20260105", 20, 20.5, 19.5, 20)]
        hits = ca.scan_for_discontinuity("9999", rows, threshold=0.2)
        self.assertEqual(len(hits), 1)
        self.assertAlmostEqual(hits[0]["implied_ratio"], 5.0, places=2)
        self.assertEqual(hits[0]["before_date"], "20260102")
        self.assertEqual(hits[0]["after_date"], "20260105")

    def test_scan_ignores_normal_moves(self):
        rows = [("20260102", 100, 101, 99, 100), ("20260105", 110, 111, 109, 110)]
        self.assertEqual(ca.scan_for_discontinuity("9999", rows, threshold=0.2), [])


class TestRealData(unittest.TestCase):
    """以本站真實資料驗證（資料存在才跑，缺檔時略過以免在乾淨環境誤報失敗）。"""

    def test_0052_adjusted_series_is_continuous(self):
        path = os.path.join(ROOT, "data", "kline", "0052.json")
        if not os.path.exists(path):
            self.skipTest("缺 data/kline/0052.json")
        doc = json.load(open(path, encoding="utf-8"))
        rows = [(str(r[0]).replace("-", ""), r[1], r[2], r[3], r[4]) for r in doc["rows"]]
        acts = ca.load_actions(root=ROOT)
        out, applied = ca.adjust_rows("0052", rows, acts)
        self.assertTrue(applied, "0052 的 1:7 分割未被套用")
        self.assertAlmostEqual(applied[0]["ratio"], 7.0, places=1)

    def test_registry_entries_all_have_source(self):
        reg = json.load(open(os.path.join(ROOT, "data", "corporate-actions.json"), encoding="utf-8"))
        for a in reg["actions"]:
            self.assertTrue(str(a.get("source") or "").strip(), f"{a.get('sym')} 缺來源")


if __name__ == "__main__":
    unittest.main(verbosity=2)
