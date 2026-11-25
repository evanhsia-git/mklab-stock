#!/usr/bin/env python3
"""MKLAB-STOCK Telegram 通知核心模組 v1.0（2026-11-25）。

設計原則（TELEGRAM_NOTIFICATION v1.0 規格）：
- 純 Python 標準庫（urllib.request/json/os/logging），零第三方依賴
- 通知失敗一律不影響主流程：CLI 預設 exit 0；--strict 僅供測試 workflow 判別
- 未設定 Secrets → SKIPPED（Fork 即可運作）
- Token 只從環境變數讀取，所有例外訊息與日誌經遮蔽，永不輸出 URL
- 預設純文字（不送 parse_mode），避免 Markdown/HTML 特殊字元解析失敗
- 重試有限（預設 3 次）：僅對暫時性錯誤（429/5xx/網路層）重試；
  400/401/403 視為永久錯誤立即失敗
- 已知限制：timeout 後重試可能造成重複通知（Telegram 端已送達但客戶端
  未收到回應）；本模組不做去重，不得宣稱具備完全去重能力

CLI：
    python3 scripts/telegram_notify.py --message-file MSG.txt [--dry-run] [--strict]

    exit 0：SENT 或 SKIPPED
    exit 1：僅 --strict 模式下 FAILED 時（一般 workflow 整合不使用）

程式介面：
    from scripts.telegram_notify import send, Result
    result = send("文字訊息")           # Result(status="SENT"|"SKIPPED"|"FAILED", detail=...)
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

API_BASE = "https://api.telegram.org/bot"
MAX_LEN = 4096          # Telegram sendMessage 官方單則上限（字元數）
DEFAULT_TIMEOUT = 10    # 秒
MAX_ATTEMPTS = 3        # 含首次；重試上限，避免無限迴圈
RETRY_DELAYS = (1, 2, 4)  # 指數退避秒數；429 以 retry_after 為準

log = logging.getLogger("telegram_notify")

SENT = "SENT"
SKIPPED = "SKIPPED"
FAILED = "FAILED"


@dataclass
class Result:
    status: str            # SENT / SKIPPED / FAILED
    detail: str = ""
    message_id: int | None = None
    segments: int = 0      # 實際發送（或將於 dry-run 發送）的則數


# ---------------------------------------------------------------- 遮蔽 ----

_TOKEN_RE = re.compile(r"bot(\d{4,}):([A-Za-z0-9_-]{8,})")
_NUM_RE = re.compile(r"\b(\d{5,})\b")


def mask_secret(text: str) -> str:
    """遮蔽例外訊息／日誌中的敏感資訊：bot token、數字型 chat_id。"""
    if not text:
        return ""
    text = _TOKEN_RE.sub(lambda m: f"bot{m.group(1)}:***", text)
    text = _NUM_RE.sub(lambda m: "*" * min(len(m.group(1)), 6), text)
    return text


# ---------------------------------------------------------------- 設定 ----

@dataclass
class Config:
    token: str | None
    chat_id: str | None
    enabled: bool          # TELEGRAM_ENABLED 總開關（未設定＝啟用）
    dry_run: bool


def load_config(environ=None) -> Config:
    env = environ if environ is not None else os.environ
    enabled_raw = (env.get("TELEGRAM_ENABLED") or "").strip().lower()
    enabled = enabled_raw not in ("0", "false", "no", "off")
    return Config(
        token=(env.get("TELEGRAM_BOT_TOKEN") or "").strip() or None,
        chat_id=(env.get("TELEGRAM_CHAT_ID") or "").strip() or None,
        enabled=enabled,
        dry_run=False,
    )


# -------------------------------------------------------------- 發送層 ----

def _post_sendmessage(token: str, chat_id: str, text: str, timeout: int):
    """呼叫 sendMessage。回傳 (http_status, json_body_bytes)。永不輸出 URL。"""
    req = urllib.request.Request(
        f"{API_BASE}{token}/sendMessage",
        data=json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:  # 4xx/5xx 一律帶 body
        return exc.code, exc.read()
    # urllib.error.URLError（DNS/timeout）與其他例外由呼叫端捕捉


def _validate_response(body: bytes) -> dict:
    """驗證 Telegram API 回應：合法 JSON 且 ok=true。失敗時 raise ValueError。"""
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"回應非合法 JSON: {exc}") from exc
    if not isinstance(payload, dict) or "ok" not in payload:
        raise ValueError("回應缺少 ok 欄位")
    if payload["ok"] is not True:
        desc = payload.get("description", "無說明")
        raise ValueError(f"API ok=false: {desc}")
    result = payload.get("result")
    if not isinstance(result, dict) or "message_id" not in result:
        raise ValueError("回應缺少 result.message_id")
    return payload


def _split_message(text: str, limit: int = MAX_LEN) -> list[str]:
    """超長訊息安全分段（依行邊界優先，最長 4096 字元）。"""
    if len(text) <= limit:
        return [text] if text.strip() else []
    chunks, current = [], ""
    for line in text.splitlines(keepends=True):
        if len(line) > limit:  # 單行超長：硬切
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(line), limit):
                chunks.append(line[i:i + limit])
            continue
        if len(current) + len(line) > limit:
            chunks.append(current)
            current = line
        else:
            current += line
    if current.strip():
        chunks.append(current)
    return [c for c in chunks if c.strip()]


def _is_permanent(status: int) -> bool:
    """400/401/403 視為永久錯誤（參數錯/Token 錯/被禁），不重試。"""
    return status in (400, 401, 403)


def _retry_after(body: bytes) -> int | None:
    try:
        payload = json.loads(body.decode("utf-8"))
        params = (payload.get("parameters") or {}) if isinstance(payload, dict) else {}
        ra = params.get("retry_after")
        return int(ra) if isinstance(ra, (int, float)) else None
    except Exception:
        return None


def send(text: str, *, config: Config | None = None, timeout: int = DEFAULT_TIMEOUT,
         max_attempts: int = MAX_ATTEMPTS, urlopen_fn=None, sleep_fn=time.sleep) -> Result:
    """發送通知。永遠回傳 Result，不 raise；失敗不影響呼叫端主流程。

    urlopen_fn/sleep_fn 僅供單元測試注入，生產路徑不使用。
    """
    cfg = config or load_config()
    urlopen_fn = urlopen_fn or _post_sendmessage

    if not cfg.enabled:
        return Result(SKIPPED, "TELEGRAM_ENABLED 停用通知")
    if not text or not text.strip():
        return Result(SKIPPED, "空白訊息，不發送")
    if not cfg.token or not cfg.chat_id:
        missing = [k for k, v in (("TELEGRAM_BOT_TOKEN", cfg.token),
                                  ("TELEGRAM_CHAT_ID", cfg.chat_id)) if not v]
        return Result(SKIPPED, f"未設定 Secrets: {', '.join(missing)}（安全跳過，不影響主流程）")

    if cfg.dry_run:
        segs = _split_message(text)
        for i, seg in enumerate(segs, 1):
            log.info("[dry-run] 第 %d/%d 則:\n%s", i, len(segs), seg)
        return Result(SENT, "dry-run：未實際發送", None, len(segs))

    segments = _split_message(text)
    if not segments:  # 防禦：理論上已在空白檢查擋下
        return Result(SKIPPED, "分段後無內容")
    last_detail = ""
    sent_id = None
    for seg_no, seg in enumerate(segments, 1):
        sent_id = None
        for attempt in range(1, max_attempts + 1):
            try:
                status, body = urlopen_fn(cfg.token, cfg.chat_id, seg, timeout)
            except urllib.error.HTTPError as exc:
                # HTTPError 是 URLError 子類，必須先於一般 URLError 分流，
                # 否則 400/401/403/429/5xx 會被誤當網路層錯誤重試。
                status, body = exc.code, exc.read()
            except Exception as exc:  # URLError（DNS／timeout）／其他網路層
                last_detail = mask_secret(f"網路層錯誤: {exc}")
                log.warning("第 %d 則第 %d 次暫時性失敗: %s", seg_no, attempt, last_detail)
                if attempt < max_attempts:
                    sleep_fn(RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)])
                continue
            if 200 <= status < 300:
                try:
                    payload = _validate_response(body)
                    sent_id = payload["result"]["message_id"]
                    break
                except ValueError as exc:
                    last_detail = mask_secret(str(exc))
                    break  # 2xx 但回應異常：不重試（避免重複送出訊息）
            elif _is_permanent(status):
                last_detail = mask_secret(f"HTTP {status} 永久性錯誤: {body[:160]!r}")
                log.error("第 %d 則永久性失敗: %s", seg_no, last_detail)
                break
            elif status == 429:
                ra = _retry_after(body)
                last_detail = mask_secret(f"HTTP 429 限流（retry_after={ra}）")
                log.warning("第 %d 則限流: %s", seg_no, last_detail)
                if attempt < max_attempts:
                    sleep_fn(min(ra, 30) if ra else RETRY_DELAYS[min(attempt - 1, 2)])
                continue
            elif 500 <= status < 600:
                last_detail = mask_secret(f"HTTP {status} 暫時性伺服器錯誤")
                log.warning("第 %d 則第 %d 次暫時性失敗: %s", seg_no, attempt, last_detail)
                if attempt < max_attempts:
                    sleep_fn(RETRY_DELAYS[min(attempt - 1, 2)])
                continue
            else:
                last_detail = mask_secret(f"HTTP {status} 未預期狀態: {body[:160]!r}")
                log.error("第 %d 則未預期失敗: %s", seg_no, last_detail)
                break
        if sent_id is None:
            return Result(FAILED,
                          f"第 {seg_no}/{len(segments)} 則發送失敗（已達重試上限或永久錯誤）: {last_detail}",
                          None, seg_no - 1)
    return Result(SENT, f"共 {len(segments)} 則發送完成", sent_id, len(segments))


# ----------------------------------------------------------------- CLI ----

def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="MKLAB-STOCK Telegram 通知")
    parser.add_argument("--message-file", help="UTF-8 文字檔；未給則讀 stdin")
    parser.add_argument("--dry-run", action="store_true", help="只列印不發送")
    parser.add_argument("--strict", action="store_true",
                        help="FAILED 時 exit 1（僅測試 workflow 用；預設永遠 exit 0）")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.message_file:
        with open(args.message_file, encoding="utf-8") as fh:
            text = fh.read()
    else:
        text = sys.stdin.read()

    cfg = load_config()
    cfg.dry_run = args.dry_run
    result = send(text, config=cfg)

    print(f"TELEGRAM_RESULT={result.status}")
    print(f"TELEGRAM_DETAIL={result.detail}")
    if result.status == FAILED and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
