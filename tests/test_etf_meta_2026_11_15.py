#!/usr/bin/env python3
"""ETF 補充資料官方自動化（2026-11-15 導入）的單元測試。

重點：
  1. TPEx `api/etfFilter` 的欄位對應（含 `rorYTD` 是**數字**而非字串的實測坑）
  2. 官方抓取失敗時的備援順序（人工 CSV → 上次結果）與「不覆寫」護欄
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


def _load(name):
    path = os.path.join(ROOT, "skills", "data", name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fme = _load("fetch_etf_meta")
pem = _load("parse_etf_meta")


def tpex_row(**over):
    base = {"issuerID": "A00009", "listingDate": "20260826", "issuerLink": "https://www.ezmoney.com.tw/",
            "stockName": "主動統一前沿科技", "totalAv": "43.78", "holders": "23,869",
            "indexName": "", "valueYTD": "171.2", "volumeYTD": "17,140,520",
            "rorYTD": 0, "stockNo": "00411A", "issuer": "統一投信"}
    base.update(over)
    return base


class TpexJsonParsing(unittest.TestCase):
    def test_field_mapping(self):
        out = fme.parse_tpex_json({"data": [tpex_row()]})
        self.assertEqual(len(out), 1)
        r = out[0]
        self.assertEqual(r["sym"], "00411A")
        self.assertEqual(r["name"], "主動統一前沿科技")
        self.assertEqual(r["market"], "TPEx")
        self.assertEqual(r["listing_date"], "2026-08-26")
        self.assertIsNone(r["tracking_index"])           # 空字串 → None（不補值）
        self.assertEqual(r["net_assets_100m"], 43.78)
        self.assertEqual(r["beneficiaries"], 23869.0)    # "23,869" 去千分位
        self.assertEqual(r["avg_value_1m"], 171.2)
        self.assertEqual(r["avg_volume"], 17140520.0)
        self.assertEqual(r["ytd_return_pct"], 0)
        self.assertEqual(r["issuer"], "統一投信")
        self.assertIsNone(r["close"])                    # 此 API 無收盤價，不重複存

    def test_numeric_ror_ytd_does_not_crash(self):
        """實測坑：rorYTD 是 int/float，不是字串。

        第一版直接把每個欄位丟給 pem._num（內部做 raw.strip()）→
        TypeError: 'int' object has no attribute 'strip'，導致 TPEx 自動抓取整批失敗。
        """
        for v in (0, 171.2, -3):
            out = fme.parse_tpex_json({"data": [tpex_row(rorYTD=v)]})
            self.assertEqual(out[0]["ytd_return_pct"], v, v)

    def test_non_code_rows_dropped(self):
        """標題／合計／空代號一律排除（沿用 parse_etf_meta._is_code 的既有語意）。

        註：6 碼數字（如權證 030123）**會**通過 `_is_code`（該函式接受 4~6 碼數字），
        但 TPEx 這支 ETF 專用 API 只會回 ETF，實務上不會出現權證，故不額外過濾。
        """
        payload = {"data": [tpex_row(), tpex_row(stockNo=""), tpex_row(stockNo="合計"),
                            tpex_row(stockNo="999")]}
        self.assertEqual([r["sym"] for r in fme.parse_tpex_json(payload)], ["00411A"])

    def test_empty_payload(self):
        for p in ({}, {"data": []}, {"data": None}, None):
            self.assertEqual(fme.parse_tpex_json(p), [])

    def test_bad_listing_date(self):
        for v in ("", "2026826", "abcdefgh"):
            out = fme.parse_tpex_json({"data": [tpex_row(listingDate=v)]})
            self.assertIsNone(out[0]["listing_date"], v)


class TypeHelpers(unittest.TestCase):
    def test_num_safe(self):
        self.assertEqual(fme._n("1,234.5"), 1234.5)
        self.assertEqual(fme._n(7), 7)
        self.assertIsNone(fme._n(None))
        self.assertIsNone(fme._n(True))
        self.assertIsNone(fme._n(float("nan")))
        self.assertIsNone(fme._n("-"))

    def test_str_safe(self):
        self.assertEqual(fme._s("  x "), "x")
        self.assertIsNone(fme._s(""))
        self.assertIsNone(fme._s(None))
        self.assertEqual(fme._s(123), "123")


class GuardsAndFallback(unittest.TestCase):
    """以臨時目錄驗證護欄與備援（不動到真的 data/）。"""

    # 注意：必須 patch `fme.pem`（fetch_etf_meta 實際使用的那個模組物件），
    # 不能 patch 測試檔自行載入的 pem —— 那是**另一份模組實例**，改了不會生效
    # （第一版就是這樣寫，結果測試偷偷讀了真的 data/raw/*.csv，看起來「通過」但沒測到東西）。
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="etfmeta_")
        self._saved = (fme.OUT_PATH, fme.RAW, fme.http_get,
                       fme.pem.TWSE_CSV, fme.pem.TPEX_CSV, fme.pem.parse_tpex)
        fme.OUT_PATH = os.path.join(self.tmp, "etf-meta.json")
        fme.RAW = self.tmp
        fme.pem.TWSE_CSV = os.path.join(self.tmp, "twse_etf.csv")
        fme.pem.TPEX_CSV = os.path.join(self.tmp, "tpex_etf.csv")

    def tearDown(self):
        (fme.OUT_PATH, fme.RAW, fme.http_get,
         fme.pem.TWSE_CSV, fme.pem.TPEX_CSV, fme.pem.parse_tpex) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    # 必須含真實表頭關鍵字（fetch_twse 會擋掉不含「受益人數」的回應，避免把錯誤頁存成 CSV）
    TWSE_CSV_BODY = ("ETF 投資篩選器\n"
                     "\"股票代號\",\"ETF名稱\",\"上市日期\",\"標的指數\",\"資產規模(億元)\",\"收盤價\","
                     "\"年初至今日均成交值(百萬元)\",\"年初至今日均成交量(股)\",\"受益人數(人)\","
                     "\"發行人\",\"\"\n"
                     "=\"0050\",\"元大台灣50\",\"2003.06.25\",\"\",\"1\",\"100\",\"1\",\"1\",\"1\","
                     "\"元大投信\",\"\"\n")

    def _write_prev(self, twse_n, tpex_n):
        etfs = ([{"sym": f"{1000 + i:04d}", "market": "TWSE", "name": "t"} for i in range(twse_n)]
                + [{"sym": f"{2000 + i:04d}", "market": "TPEx", "name": "p"} for i in range(tpex_n)])
        doc = {"meta": {"as_of": "2026-11-02", "count": len(etfs)}, "etfs": etfs}
        json.dump(doc, open(fme.OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False)
        return doc

    def test_all_sources_fail_does_not_overwrite(self):
        """兩邊都抓不到、也沒有可用備援 → 中止且不覆寫既有檔。"""
        prev = self._write_prev(100, 100)
        fme.http_get = lambda *a, **k: (_ for _ in ()).throw(OSError("boom"))
        fme.pem.parse_tpex = lambda: []  # 也沒有 TPEx 的「上次結果」以外的備援
        rc = fme.main()
        self.assertEqual(rc, 2)
        self.assertEqual(json.load(open(fme.OUT_PATH, encoding="utf-8")), prev, "不得覆寫既有檔")

    def test_per_market_guard_catches_one_sided_failure(self):
        """逐市場護欄：TWSE 全掛但 TPEx 正常時，不可寫出 TWSE 空掉的檔。

        這是第一版的漏洞——只看總數的話，「TWSE 0 檔 + TPEx 118 檔」會通過，
        前端會整批少掉上市 ETF。
        """
        prev = self._write_prev(100, 100)
        fme.http_get = lambda *a, **k: (_ for _ in ()).throw(OSError("twse only down"))
        rc = fme.main()
        self.assertEqual(rc, 2, "TWSE 0 檔 vs 上次 100 檔應被擋下")
        self.assertEqual(json.load(open(fme.OUT_PATH, encoding="utf-8")), prev)

    def test_tpex_falls_back_to_previous_result(self):
        """TPEx 掛掉但上次結果可用 → 沿用上次（provenance=previous），TWSE 正常 → 可寫入。"""
        self._write_prev(1, 1)
        fme.http_get = (lambda url, *a, **k: self.TWSE_CSV_BODY.encode("cp950")
                        if "etfExcel" in url else (_ for _ in ()).throw(OSError("tpex down")))
        rc = fme.main()
        self.assertEqual(rc, 0)
        doc = json.load(open(fme.OUT_PATH, encoding="utf-8"))
        self.assertEqual(doc["meta"]["provenance"], {"TWSE": "auto", "TPEx": "previous"})
        self.assertTrue(any("沿用上次結果" in n for n in doc["meta"]["log"]), doc["meta"]["log"])
        self.assertEqual(doc["meta"]["counts"], {"TWSE": 1, "TPEx": 1})

    def test_points_to_expected_endpoints(self):
        self.assertIn("ETFortune/etfExcel", fme.TWSE_CSV_URL)
        self.assertIn("info.tpex.org.tw/api/etfFilter", fme.TPEX_API_URL)


if __name__ == "__main__":
    unittest.main()
