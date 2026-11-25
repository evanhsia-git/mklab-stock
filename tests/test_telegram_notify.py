#!/usr/bin/env python3
"""telegram_notify v1.0 單元測試——全部使用 mock，絕不呼叫真實 Telegram API。

涵蓋 TELEGram_NOTIFICATION v1.0 Phase 8 規格的 30+ 情境。
執行：python3 -m unittest tests.test_telegram_notify -v
"""
from __future__ import annotations

import io
import json
import os
import sys
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import telegram_notify as tn  # noqa: E402


def make_response(status: int, body: bytes | dict):
    if isinstance(body, dict):
        body = json.dumps(body).encode("utf-8")
    return status, body


def urlopen_mock_factory(responses, calls=None):
    """產生依序回傳 responses 的 urlopen 替身。calls 若給定則記錄每次呼叫。"""
    seq = list(responses)

    def _fake(token, chat_id, text, timeout):
        if calls is not None:
            calls.append({"text": text, "token": token, "chat_id": chat_id})
        if not seq:
            raise AssertionError("urlopen 被呼叫超過預期次數")
        item = seq.pop(0)
        if isinstance(item, Exception):
            raise item
        status, body = item
        if status >= 400:
            # HTTPError 的 fp 必須是 file-like（真實 urllib 行為），bytes 無 close()
            raise urllib.error.HTTPError("https://api.telegram.org/bot***/sendMessage",
                                         status, "mock", {}, io.BytesIO(body))
        return status, body

    return _fake


def cfg(**kw):
    base = dict(token="1234567:TESTTOKEN", chat_id="8730017948", enabled=True, dry_run=False)
    base.update(kw)
    return tn.Config(**base)


OK_BODY = {"ok": True, "result": {"message_id": 42}}


class 配置與跳過(unittest.TestCase):
    def test_01_正常發送(self):
        calls = []
        r = tn.send("🧪 測試", config=cfg(),
                    urlopen_fn=urlopen_mock_factory([make_response(200, OK_BODY)], calls))
        self.assertEqual(r.status, tn.SENT)
        self.assertEqual(r.message_id, 42)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["chat_id"], "8730017948")

    def test_02_缺BOT_TOKEN(self):
        r = tn.send("訊息", config=cfg(token=None))
        self.assertEqual(r.status, tn.SKIPPED)
        self.assertIn("TELEGRAM_BOT_TOKEN", r.detail)

    def test_03_缺CHAT_ID(self):
        r = tn.send("訊息", config=cfg(chat_id=None))
        self.assertEqual(r.status, tn.SKIPPED)
        self.assertIn("TELEGRAM_CHAT_ID", r.detail)

    def test_04_通知功能停用(self):
        r = tn.send("訊息", config=cfg(enabled=False),
                    urlopen_fn=urlopen_mock_factory([AssertionError("不應呼叫")]))
        self.assertEqual(r.status, tn.SKIPPED)

    def test_05_ENABLED以環境變數讀取(self):
        env = {"TELEGRAM_ENABLED": "false", "TELEGRAM_BOT_TOKEN": "1:t", "TELEGRAM_CHAT_ID": "2"}
        self.assertFalse(tn.load_config(env).enabled)
        env2 = {"TELEGRAM_ENABLED": "true", "TELEGRAM_BOT_TOKEN": "1:t", "TELEGRAM_CHAT_ID": "2"}
        self.assertTrue(tn.load_config(env2).enabled)
        env3 = {}  # 未設定＝啟用
        self.assertTrue(tn.load_config(env3).enabled)

    def test_06_空白訊息(self):
        r = tn.send("   \n  ", config=cfg())
        self.assertEqual(r.status, tn.SKIPPED)

    def test_07_Fork未設定Secrets全部安全跳過(self):
        r = tn.send("訊息", config=tn.Config(token=None, chat_id=None, enabled=True, dry_run=False))
        self.assertEqual(r.status, tn.SKIPPED)


class 永久性錯誤(unittest.TestCase):
    def test_08_HTTP400(self):
        calls = []
        r = tn.send("訊息", config=cfg(),
                    urlopen_fn=urlopen_mock_factory([make_response(400, {"ok": False, "description": "chat not found"})], calls))
        self.assertEqual(r.status, tn.FAILED)
        self.assertEqual(len(calls), 1, "400 不得重試")

    def test_09_HTTP401_token無效(self):
        calls = []
        r = tn.send("訊息", config=cfg(),
                    urlopen_fn=urlopen_mock_factory([make_response(401, {"ok": False, "description": "Unauthorized"})], calls))
        self.assertEqual(r.status, tn.FAILED)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("TESTTOKEN", r.detail, "detail 不得含 token")

    def test_10_HTTP403_被禁(self):
        r = tn.send("訊息", config=cfg(),
                    urlopen_fn=urlopen_mock_factory([make_response(403, {"ok": False, "description": "bot was blocked"})]))
        self.assertEqual(r.status, tn.FAILED)


class 暫時性錯誤與重試(unittest.TestCase):
    def test_11_HTTP429_retry_after後成功(self):
        calls = []
        sleeps = []
        r = tn.send("訊息", config=cfg(),
                    urlopen_fn=urlopen_mock_factory([
                        make_response(429, {"ok": False, "parameters": {"retry_after": 2}}),
                        make_response(200, OK_BODY)], calls),
                    sleep_fn=sleeps.append)
        self.assertEqual(r.status, tn.SENT)
        self.assertEqual(len(calls), 2)
        self.assertEqual(sleeps, [2], "429 應等待 retry_after")

    def test_12_HTTP429_持續限流至上限(self):
        calls = []
        r = tn.send("訊息", config=cfg(),
                    urlopen_fn=urlopen_mock_factory([make_response(429, {"ok": False})] * 5, calls))
        self.assertEqual(r.status, tn.FAILED)
        self.assertEqual(len(calls), tn.MAX_ATTEMPTS, "重試不得超過上限")

    def test_13_HTTP500暫時錯誤後成功(self):
        calls = []
        r = tn.send("訊息", config=cfg(),
                    urlopen_fn=urlopen_mock_factory([
                        make_response(500, {"ok": False}),
                        make_response(200, OK_BODY)], calls),
                    sleep_fn=lambda s: None)
        self.assertEqual(r.status, tn.SENT)
        self.assertEqual(len(calls), 2)

    def test_14_HTTP502_503(self):
        for status in (502, 503):
            calls = []
            r = tn.send("訊息", config=cfg(),
                        urlopen_fn=urlopen_mock_factory([make_response(status, {"ok": False})] * 4, calls),
                        sleep_fn=lambda s: None)
            self.assertEqual(r.status, tn.FAILED, f"HTTP {status}")
            self.assertEqual(len(calls), tn.MAX_ATTEMPTS)

    def test_15_網路timeout重試(self):
        calls = []
        r = tn.send("訊息", config=cfg(),
                    urlopen_fn=urlopen_mock_factory([
                        urllib.error.URLError("timed out"),
                        make_response(200, OK_BODY)], calls),
                    sleep_fn=lambda s: None)
        self.assertEqual(r.status, tn.SENT)
        self.assertEqual(len(calls), 2)

    def test_16_DNS解析失敗(self):
        calls = []
        r = tn.send("訊息", config=cfg(),
                    urlopen_fn=urlopen_mock_factory([urllib.error.URLError("Name or service not known")] * 4, calls),
                    sleep_fn=lambda s: None)
        self.assertEqual(r.status, tn.FAILED)
        self.assertEqual(len(calls), tn.MAX_ATTEMPTS)

    def test_17_重試等待時間上限(self):
        # retry_after 陣狂值（如 3600）必須被 cap 到 30 秒內
        sleeps = []
        tn.send("訊息", config=cfg(),
                urlopen_fn=urlopen_mock_factory([make_response(429, {"ok": False, "parameters": {"retry_after": 3600}}),
                                                 make_response(200, OK_BODY)]),
                sleep_fn=sleeps.append)
        self.assertLessEqual(sleeps[0], 30)

    def test_18_重複通知限制_不得宣稱去重(self):
        # timeout 後重試可能造成 Telegram 端重複——規格明文不宣稱去重
        self.assertNotIn("去重", tn.send.__doc__ or "去重")
        doc = (tn.__doc__ or "") + (tn.send.__doc__ or "")
        self.assertIn("不做去重", doc)


class 回應驗證(unittest.TestCase):
    def test_19_JSON回應格式錯誤(self):
        calls = []
        r = tn.send("訊息", config=cfg(),
                    urlopen_fn=urlopen_mock_factory([make_response(200, b"<html>not json</html>")], calls))
        self.assertEqual(r.status, tn.FAILED)
        self.assertEqual(len(calls), 1, "2xx 但回應異常：不得重試（避免重複發送）")

    def test_20_HTTP200但ok_false(self):
        r = tn.send("訊息", config=cfg(),
                    urlopen_fn=urlopen_mock_factory([make_response(200, {"ok": False, "description": "X"})]))
        self.assertEqual(r.status, tn.FAILED)

    def test_21_回應缺message_id(self):
        r = tn.send("訊息", config=cfg(),
                    urlopen_fn=urlopen_mock_factory([make_response(200, {"ok": True, "result": {}})]))
        self.assertEqual(r.status, tn.FAILED)


class 訊息內容(unittest.TestCase):
    def test_22_超長訊息分段(self):
        calls = []
        text = "台股快訊\n" + "x" * 100 + "\n" * 60  # 多行且 >4096
        text = "\n".join(f"第{i}行 資料數據內容測試用" for i in range(500))  # >4096 字元
        r = tn.send(text, config=cfg(),
                    urlopen_fn=urlopen_mock_factory([make_response(200, OK_BODY)] * 10, calls))
        self.assertEqual(r.status, tn.SENT)
        self.assertGreater(r.segments, 1, "超長訊息必須分段")
        for c in calls:
            self.assertLessEqual(len(c["text"]), tn.MAX_LEN)

    def test_23_單行超長硬切(self):
        segs = tn._split_message("A" * 10000)
        self.assertGreater(len(segs), 1)
        self.assertTrue(all(len(s) <= tn.MAX_LEN for s in segs))

    def test_24_中文與Emoji(self):
        calls = []
        r = tn.send("🧪 台股收盤 2330 收 2230.0 ▲＋1.2% ◕‿◕\n第二行：数据", config=cfg(),
                    urlopen_fn=urlopen_mock_factory([make_response(200, OK_BODY)], calls))
        self.assertEqual(r.status, tn.SENT)
        self.assertEqual(calls[0]["text"], "🧪 台股收盤 2330 收 2230.0 ▲＋1.2% ◕‿◕\n第二行：数据")

    def test_25_特殊字元純文字不解析(self):
        calls = []
        text = "<b>粗體</b> & \"引號\" '單引號' _底線_ *星號* [連結](url)"
        r = tn.send(text, config=cfg(),
                    urlopen_fn=urlopen_mock_factory([make_response(200, OK_BODY)], calls))
        self.assertEqual(r.status, tn.SENT)
        self.assertEqual(calls[0]["text"], text, "純文字模式不得改寫特殊字元")


class DryRun與安全(unittest.TestCase):
    def test_26_DryRun不發送(self):
        calls = []
        r = tn.send("🧪 測試", config=cfg(dry_run=True),
                    urlopen_fn=urlopen_mock_factory([AssertionError("dry-run 不應呼叫")], calls))
        self.assertEqual(r.status, tn.SENT)
        self.assertIn("dry-run", r.detail)
        self.assertEqual(len(calls), 0)

    def test_27_敏感資訊遮蔽_token(self):
        masked = tn.mask_secret("呼叫 https://api.telegram.org/bot1234567890:ABCdefGHIjklMNOpqrsTUVwxyz/sendMessage 失敗")
        self.assertNotIn("ABCdefGHIjklMNOpqrsTUVwxyz", masked)
        self.assertIn("***", masked)

    def test_28_敏感資訊遮蔽_chat_id(self):
        masked = tn.mask_secret("chat_id=8730017948 無效")
        self.assertNotIn("8730017948", masked)

    def test_29_錯誤detail不含token(self):
        r = tn.send("訊息", config=cfg(),
                    urlopen_fn=urlopen_mock_factory([make_response(500, {"ok": False})] * 4),
                    sleep_fn=lambda s: None)
        self.assertNotIn("TESTTOKEN", r.detail)

    def test_30_失敗不影響主流程_CLI預設exit0(self):
        # CLI：FAILED 且未加 --strict → exit 0
        with mock.patch("sys.stdin") as fake_stdin, \
             mock.patch("scripts.telegram_notify.send",
                        return_value=tn.Result(tn.FAILED, "x")):
            fake_stdin.read.return_value = "訊息"
            self.assertEqual(tn.main([]), 0)


class 狀態區分(unittest.TestCase):
    def test_31_SENT_SKIPPED_FAILED三種結果(self):
        self.assertEqual({tn.SENT, tn.SKIPPED, tn.FAILED}, {"SENT", "SKIPPED", "FAILED"})
        ok = tn.send("訊息", config=cfg(),
                     urlopen_fn=urlopen_mock_factory([make_response(200, OK_BODY)]))
        self.assertEqual(ok.status, tn.SENT)
        skip = tn.send("訊息", config=cfg(token=None))
        self.assertEqual(skip.status, tn.SKIPPED)
        fail = tn.send("訊息", config=cfg(),
                       urlopen_fn=urlopen_mock_factory([make_response(400, {"ok": False})]))
        self.assertEqual(fail.status, tn.FAILED)

    def test_32_workflow_CANCELLED與SKIPPED不是PASS(self):
        # 規格：不得把 SKIPPED/CANCELLED/UNKNOWN 當 PASS——呼叫端必須檢查 status 字串
        for bad in (tn.SKIPPED, tn.FAILED):
            self.assertNotEqual(bad, tn.SENT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
