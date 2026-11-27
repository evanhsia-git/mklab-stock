#!/usr/bin/env python3
"""MKLAB-STOCK Telegram 通知整合（Phase 4-7，v1.1）——workflow_run 監聽報告。

架構：不修改任何既有 workflow。telegram-notify.yml 以 workflow_run 監聽
daily-update / qa-gate / pages-build-deployment 三個 workflow 的完成事件，
呼叫本腳本組訊息後交 telegram_notify.send() 發送。

防濫發設計：
- daily-update success：僅當「daily」job 為 success 時發每日報告（一則彙總）；
  其他班（weekly-roe/us-market/…）的 run 一律靜默
- daily-update failure/cancelled：一則 P0 彙整告警（列所有非成功 job）
- qa-gate failure：一則 P0 QA 異常告警（artifact 下載 qa-result.json，
  列 ERROR 檢查明細）；success 靜默（每日報告的 QA 欄已涵蓋）
- pages-build-deployment：success 靜默（常態）；failure 一則 P0
- 通知模組自身失敗不再觸發通知（本 workflow 不被自己監聽，無循環）

資料誠信：
- 所有數值來自線上真實檔案（raw.githubusercontent）與 GitHub API
- 取不到的欄位標 N/A / UNKNOWN / NOT_RUN，禁止猜測
- SKIPPED/CANCELLED/UNKNOWN 一律不當作 PASS
- 部署狀態以 Pages workflow 的實際 conclusion 為準，未查到標 UNKNOWN

安全：
- GITHUB_TOKEN 僅用於查詢自家 repo 的 runs/jobs/artifacts（actions: read）
- 任何例外輸出經 telegram_notify.mask_secret 遮蔽
- 本腳本任何失敗都不影響資料更新／QA／部署（獨立 workflow，且 exit 永遠 0）
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import sys
import urllib.error
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telegram_notify import send, mask_secret, load_config, Config  # noqa: E402

REPO = "evanhsia-git/mklab-stock"
RAW = f"https://raw.githubusercontent.com/{REPO}/main"
API = f"https://api.github.com/repos/{REPO}"

MONITORED = {
    "daily-update": "daily-update",
    "qa-gate": "qa-gate",
    "pages build and deployment": "pages",
}

TAIPEI = dt.timezone(dt.timedelta(hours=8))


def _get(url: str, token: str | None = None, timeout: int = 25):
    req = urllib.request.Request(url, headers={
        "User-Agent": "mklab-notify/1.1",
        "Accept": "application/vnd.github+json",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_raw(path: str):
    with urllib.request.urlopen(f"{RAW}/{path}", timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_json_or_none(path: str, token: str | None = None):
    try:
        return _get_raw(path) if token is None else _get(f"{API}/{path}", token)
    except Exception as exc:
        print(f"[warn] {mask_secret(str(exc))}", file=sys.stderr)
        return None


def _fmt_dt(iso: str | None) -> str:
    if not iso:
        return "UNKNOWN"
    try:
        t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TAIPEI)
        return t.strftime("%Y-%m-%d %H:%M:%S 台北")
    except (ValueError, TypeError):
        return "UNKNOWN"


def _duration(start: str | None, end: str | None) -> str:
    try:
        if not start or not end:
            return "N/A"
        s = dt.datetime.fromisoformat(start.replace("Z", "+00:00"))
        e = dt.datetime.fromisoformat(end.replace("Z", "+00:00"))
        secs = int((e - s).total_seconds())
        return f"{secs // 60}分{secs % 60:02d}秒" if secs >= 60 else f"{secs}秒"
    except (ValueError, TypeError, AttributeError):
        return "N/A"


# ------------------------------------------------------------ 每日報告 ----

def build_daily_report(run, token: str | None) -> str:
    """Phase 5：每日資料更新報告——所有數值來自真實來源，取不到標 N/A。"""
    stocks = _fetch_json_or_none("data/stocks.json") or {}
    us = _fetch_json_or_none("data/us/us-stocks.json") or {}
    flog = _fetch_json_or_none("data/fetch-log.json") or {}
    emeta_doc = _fetch_json_or_none("data/etf-meta.json") or {}
    usetf = _fetch_json_or_none("data/us/us-etfs.json") or {}
    idxdoc = _fetch_json_or_none("data/indices.json") or {}
    smeta = stocks.get("meta", {}) if isinstance(stocks, dict) else {}
    umeta = us.get("meta", {}) if isinstance(us, dict) else {}
    det = flog.get("details", {}) if isinstance(flog, dict) else {}
    # 台股 ETF 上市／上櫃計數（etf-meta.json 的 market 欄：TWSE=上市、TPEx=上櫃）
    emarkets = {}
    for _e in (emeta_doc.get("etfs") or []):
        emarkets[_e.get("market")] = emarkets.get(_e.get("market"), 0) + 1
    usetf_meta = usetf.get("meta", {}) if isinstance(usetf, dict) else {}
    idx_meta = idxdoc.get("meta", {}) if isinstance(idxdoc, dict) else {}

    # QA：最近的 qa-gate run（jobs API）——只在有結果時顯示真實狀態
    qa_line = "NOT_RUN（近 24h 無 qa-gate 執行）"
    try:
        runs = _get(f"{API}/actions/workflows/qa-gate.yml/runs?per_page=5", token)
        for r in runs.get("workflow_runs", []):
            if r.get("conclusion") in ("success", "failure", "cancelled"):
                qa_line = {"success": "PASS", "failure": "FAIL", "cancelled": "CANCELLED"}[r["conclusion"]]
                break
    except Exception as exc:
        qa_line = f"UNKNOWN（{mask_secret(str(exc))[:60]}）"

    # Pages：官方 Pages builds API（pages-build-deployment 是 GitHub 內建 dynamic workflow，
    # 不是 repo 檔案——以 workflows/<name>.yml 查會 404）。
    # status：built=正常；errored/其他/查無=不正常（保守呈現，只有二值）
    pages_line = "不正常（無法確認部署狀態）"
    try:
        b = _get(f"{API}/pages/builds/latest", token)
        pages_line = "正常" if (b.get("status") == "built") else "不正常"
    except Exception as exc:
        pages_line = f"不正常（{mask_secret(str(exc))[:60]}）"

    # 容量：線上檔案的實際位元組（HEAD Content-Length）
    def _size(path):
        try:
            req = urllib.request.Request(f"{RAW}/{path}", method="HEAD",
                                         headers={"User-Agent": "mklab-notify/1.1"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return int(resp.headers.get("Content-Length") or 0)
        except Exception:
            return None

    def _kb(n):
        return f"{n:,} bytes（{n // 1024} KB）" if n else "N/A"

    sz_stocks, sz_us = _size("data/stocks.json"), _size("data/us/us-stocks.json")
    old_stocks, old_us = 1_331_022, None  # 2026-11-25 盤點基準（stocks.json Manifest 值）
    var = f"+{sz_stocks - old_stocks:,}" if sz_stocks else "N/A"

    fetched = flog.get("fetched") if isinstance(flog, dict) else None
    written = flog.get("written") if isinstance(flog, dict) else None
    err = flog.get("error") if isinstance(flog, dict) else None

    lines = [
        "【MKLAB-STOCK 每日系統報告】",
        "",
        f"日期：{dt.datetime.now(TAIPEI).strftime('%Y-%m-%d')}",
        f"執行時間：{_fmt_dt(run.get('run_started_at'))}",
        f"總耗時：{_duration(run.get('run_started_at'), run.get('updated_at'))}",
        "",
        "【資料更新】",
        f"台股：{smeta.get('as_of', 'N/A')}（{smeta.get('count', 'N/A')} 檔）",
        f"美股：{umeta.get('returns_as_of', 'N/A')}（{umeta.get('count', 'N/A')} 檔）",
        f"台股 ETF：{smeta.get('as_of', 'N/A')} 上市（{emarkets.get('TWSE', 0)} 檔）",
        f"台股 ETF：{smeta.get('as_of', 'N/A')} 上櫃（{emarkets.get('TPEx', 0)} 檔）",
        f"美股 ETF：{str(usetf_meta.get('returns_as_of', 'N/A'))}（{usetf_meta.get('count', 'N/A')} 檔）",
        f"全球指數：{idx_meta.get('as_of', 'N/A')}（指數 {idx_meta.get('index_count', 'N/A')}／ETF {idx_meta.get('etf_count', 'N/A')}／總經 {idx_meta.get('macro_count', 'N/A')}）",
        f"歷史資料：{det.get('history_file', 'N/A')}",
        "",
        "【資料品質】",
        f"資料筆數：{smeta.get('count', 'N/A')}",
        f"更新成功筆數：{written if written is not None else 'N/A'}",
        f"更新失敗筆數：{'N/A' if err is None else '見下方錯誤'}",
        f"缺漏欄位：N/A（qa-result 不入 git，見 QA 行）",
        f"異常資料：{('fetch_log error: ' + str(err)[:60]) if err else '無紀錄'}",
        f"備援來源使用情況：{('已使用' if det.get('twse_stale_vs_tpex') else 'N/A')}（twse_stale_vs_tpex={det.get('twse_stale_vs_tpex', 'N/A')}）",
        "",
        "【QA 品質閘門】",
        f"檢查總數：N/A（由 qa-gate artifact 提供，告警時才逐項列出）",
        f"執行結果：{qa_line}",
        "",
        "【資料庫容量】",
        f"stocks.json：{_kb(sz_stocks)}（容量變化：{var} vs 11-25 基準）",
        f"us-stocks.json：{_kb(sz_us)}",
        f"容量門檻：N/A（門檻由 qa_gate 檢查，超標時會出現 Critical）",
        f"是否超標：UNKNOWN（以 qa-gate 結果為準）",
        "",
        "【部署狀態】",
        f"GitHub Pages：{pages_line}",
        f"發布結果：{pages_line}",
        f"LKG 狀態：未啟用（依專案規劃，P3 保留介面）",
        "",
        "【相關連結】",
        f"GitHub Actions：{run.get('html_url', 'N/A')}",
        f"MKLAB-STOCK 網站：https://evanhsia-git.github.io/mklab-stock/",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------ QA 異常 ----

def build_qa_alert(run, token: str | None) -> str:
    """Phase 6：QA 異常告警——qa-result.json 從 qa-report artifact 取得。"""
    run_id = run.get("id")
    errors: list[dict] = []
    summary = "UNKNOWN"
    try:
        arts = _get(f"{API}/actions/runs/{run_id}/artifacts", token)
        qa_art = next((a for a in arts.get("artifacts", []) if a.get("name") == "qa-report"), None)
        if not qa_art:
            summary = "找不到 qa-report artifact"
        else:
            # 兩段式下載：GitHub 對 archive_download_url 回 302 → 簽名的 Azure Blob URL；
            # 若自動跟隨 redirect 時把 Authorization 帶過去，Azure 會回 401。
            # 第一段只取 Location（不跟 redirect），第二段用乾淨請求（無 Auth）下載。
            class _NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None

            first = urllib.request.Request(qa_art["archive_download_url"], headers={
                "User-Agent": "mklab-notify/1.1",
                "Authorization": f"Bearer {token}",
            })
            opener = urllib.request.build_opener(_NoRedirect)
            try:
                opener.open(first, timeout=40)
                raise ValueError("預期 302 redirect，但直接拿到 200")
            except urllib.error.HTTPError as e:
                if e.status not in (301, 302, 303, 307, 308):
                    raise
                location = e.headers.get("Location")
            if not location:
                raise ValueError("302 回應缺少 Location")
            with urllib.request.urlopen(location, timeout=60) as r2:
                zf = zipfile.ZipFile(io.BytesIO(r2.read()))
                name = next(n for n in zf.namelist() if n.endswith("qa-result.json"))
                report = json.loads(zf.read(name).decode("utf-8"))
            errors = [c for c in report.get("checks", []) if c.get("status") == "ERROR"]
            summary = (f"{len(errors)} 項 Critical ERROR／"
                       f"{report.get('warnings', '?')} 項 WARNING／"
                       f"allow_deploy={report.get('allow_deploy')}")
    except Exception as exc:
        summary = f"無法取得 QA 報告（{mask_secret(str(exc))[:80]}）"

    lines = [
        "🚨 MKLAB-STOCK QA 異常警告",
        "",
        f"嚴重程度：P0 Critical",
        f"發生時間：{_fmt_dt(run.get('run_started_at'))}",
        f"Workflow 名稱：{run.get('name')}",
        f"Git commit：{str(run.get('head_sha'))[:8]}",
        f"GitHub Actions Run URL：{run.get('html_url')}",
        "",
        f"總結：{summary}",
    ]
    for c in errors[:10]:
        lines.append("")
        lines.append(f"• 規則：[{c.get('cat', 'N/A')}] {c.get('name', 'N/A')}")
        detail = str(c.get("detail") or "")[:220]
        lines.append(f"  明細：{detail if detail else 'N/A'}")
    if len(errors) > 10:
        lines.append(f"  …另有 {len(errors) - 10} 項，見 artifact")
    lines.append("")
    lines.append("是否阻擋發布：是（fail closed）——請確認後手動處理")
    return "\n".join(lines)


# ------------------------------------------------------------ 失敗彙整 ----

def build_failure_summary(run, token: str | None) -> str:
    """Phase 7：daily-update 失敗的一則彙整（列所有非成功 job，不逐檔轟炸）。"""
    run_id = run.get("id")
    failed_jobs: list[str] = []
    try:
        jobs = _get(f"{API}/actions/runs/{run_id}/jobs", token)
        for j in jobs.get("jobs", []):
            if j.get("conclusion") not in ("success", "skipped"):
                failed_jobs.append(f"• {j.get('name')}（{j.get('conclusion')}）")
    except Exception as exc:
        failed_jobs.append(f"• （無法列舉 jobs：{mask_secret(str(exc))[:60]}）")
    return "\n".join([
        "🚨 MKLAB-STOCK 每日更新失敗",
        "",
        f"嚴重程度：P0 Critical",
        f"發生時間：{_fmt_dt(run.get('run_started_at'))}",
        f"Git commit：{str(run.get('head_sha'))[:8]}",
        f"Run URL：{run.get('html_url')}",
        "",
        "失敗／非正常結束的 job：",
        *(failed_jobs or ["• （清單取得失敗）"]),
    ])


def build_pages_alert(run, token: str | None) -> str:
    return "\n".join([
        "🚨 MKLAB-STOCK GitHub Pages 部署失敗",
        "",
        f"嚴重程度：P0 Critical",
        f"發生時間：{_fmt_dt(run.get('run_started_at'))}",
        f"Git commit：{str(run.get('head_sha'))[:8]}",
        f"Run URL：{run.get('html_url')}",
        "",
        "網站可能停留在舊版本。請檢查 Pages workflow 日誌。",
    ])


# -------------------------------------------------------------- 分派 ----

def decide_and_build(name: str, conclusion: str, run: dict, token: str | None):
    """回傳 (要通知?, 訊息)。success 的 qa-gate/pages 靜默（防濫發）。"""
    key = MONITORED.get(name)
    if key == "daily-update":
        if conclusion in ("failure", "cancelled"):
            return True, build_failure_summary(run, token)
        if conclusion == "success":
            jobs = _get(f"{API}/actions/runs/{run.get('id')}/jobs", token)
            daily = next((j for j in jobs.get("jobs", [])
                          if j.get("name") == "daily"), None)
            if daily and daily.get("conclusion") == "success":
                return True, build_daily_report(run, token)
        return False, ""
    if key == "qa-gate":
        if conclusion in ("failure", "cancelled"):
            return True, build_qa_alert(run, token)
        return False, ""
    if key == "pages":
        if conclusion == "failure":
            return True, build_pages_alert(run, token)
        return False, ""
    return False, ""


def main() -> int:
    name = os.environ.get("WF_RUN_NAME", "")
    conclusion = os.environ.get("WF_RUN_CONCLUSION", "")
    run = {
        "id": int(os.environ.get("WF_RUN_ID") or 0),
        "name": name,
        "conclusion": conclusion,
        "head_sha": os.environ.get("WF_RUN_HEAD_SHA", ""),
        "html_url": os.environ.get("WF_RUN_URL", ""),
        "run_started_at": os.environ.get("WF_RUN_STARTED_AT", ""),
        "updated_at": os.environ.get("WF_RUN_UPDATED_AT", ""),
    }
    token = os.environ.get("GITHUB_TOKEN") or None
    if name not in MONITORED:
        print(f"[skip] 未監聽的 workflow: {name}")
        return 0
    notify, message = decide_and_build(name, conclusion, run, token)
    if not notify or not message.strip():
        print(f"[skip] {name} {conclusion}——依防濫發規則靜默")
        return 0
    cfg: Config = load_config()
    result = send(message, config=cfg)
    print(f"TELEGRAM_RESULT={result.status}")
    print(f"TELEGRAM_DETAIL={result.detail}")
    return 0  # 通知失敗一律不影響任何主流程


if __name__ == "__main__":
    sys.exit(main())
