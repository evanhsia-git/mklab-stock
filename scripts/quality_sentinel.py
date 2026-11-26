#!/usr/bin/env python3
"""品質哨兵 v1.0（2026-11-25）——P0 新鮮度監控＋P1 自癒分級＋P2 依賴健康度。

背景：2026-11-21~25 資料停更 6 天才被發現（QA 擋下後當天無重跑機會、
GitHub cron 延遲 10.8h）。本哨兵與 CI 路徑完全獨立（本機 cron），
任何一端出事都能叫人。

# 輸出契約（Hermes cronjob no_agent / watchdog 模式，job 7ad116fa5fe3，每日 22:00 台北）：
# - stdout 空＝一切正常（不發任何訊息，避免噪音）
# - 有輸出＝異常告警（逐字發送 Telegram）
# ⚠️ cronjob 從 ~/.hermes/scripts/quality_sentinel.py 執行「真實複本」（symlink 會被
#    traversal 防護拒絕）——本檔（repo）是主檔，任何改動後必須同步該副本。

安全邊界：
- 自癒只跑既有且冪等的每日管線＋完整 QA 閘門；QA exit 0 才允許推送
- 動到資料語意的修復（ROE 殘留等）一律不自動做——QA 擋下時僅分類告警
"""
import datetime as dt
import gzip
import io
import json
import subprocess
import sys
import urllib.request

REPO = "/root/mklab-stock"
ONLINE_URL = "https://evanhsia-git.github.io/mklab-stock/data/stocks.json"
PY = sys.executable  # 哨兵必須以 /root/venvs/quant/bin/python3 執行（排程腳本慣例）


def online_asof():
    req = urllib.request.Request(ONLINE_URL, headers={"Accept-Encoding": "gzip", "User-Agent": "mklab-sentinel/1.0"})
    with urllib.request.urlopen(req, timeout=40) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    return json.loads(io.BytesIO(raw).read().decode("utf-8"))["meta"]["as_of"][:10]


def workday_gap(asof_str, today=None):
    """as_of 之後到今天為止的工作日數（剔除週六日；國定假日保守多算→寧可誤報）。
    例：as_of=週五、今天=下週三 → gap=3（11-20 型事故會在停更滿 2 個交易日後告警）。"""
    today = today or dt.date.today()
    a = dt.date.fromisoformat(asof_str)
    return sum(1 for i in range(1, (today - a).days + 1)
               if (a + dt.timedelta(days=i)).weekday() < 5)


def selfheal():
    """P1：重現每日管線（行情主體，不含 15 天制的持股班）→完整 QA 閘門→過了才推。"""
    steps = [
        ["skills/data/fetch_data.py", "daily"],
        ["skills/data/sanitize_snapshot.py"],
        ["skills/data/repair_history.py"],
        ["skills/data/detect_corporate_actions.py"],
        ["skills/data/compute_indicators.py"],
        ["skills/data/integrate_official_company.py"],
        ["skills/data/build_kline.py"],
        ["skills/data/compute_industry.py"],
        ["skills/data/build_digest.py"],
    ]
    for cmd, *args in steps:
        r = subprocess.run([PY, cmd, *args], cwd=REPO, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            return (f"🛑 自癒中止：{cmd} 失敗（exit {r.returncode}）——需人工檢查\n"
                    f"最後輸出：{(r.stdout or r.stderr).strip().splitlines()[-1][:160]}")
    gate = subprocess.run(["python3", "skills/qa-gate/qa_gate.py", "--gate"], cwd=REPO,
                          capture_output=True, text=True, timeout=900)
    if gate.returncode != 0:
        errs = [l for l in (gate.stdout or "").splitlines()
                if "ERROR" in l or "FAIL" in l][:6]
        return ("🔴 自癒被 QA 閘門擋下——資料語意問題不自動修，需授權：\n"
                + "\n".join(errs))
    push = subprocess.run(
        ["bash", "scripts/ci_commit_push.sh", f"data: 哨兵自癒 {dt.date.today()}", "data/", "rss.xml"],
        cwd=REPO, capture_output=True, text=True, timeout=600)
    if push.returncode != 0:
        return f"🛑 自癒推送失敗（QA 已過）: {(push.stderr or push.stdout).strip().splitlines()[-1][:200]}"
    return None  # 靜默＝自癒成功


def health_summary():
    """P2：當下資料源健康度——fetch_data 錯誤＋持股 stale 檔（實測 schema：
    fetch-log.json 為單次物件；etf-holdings.json 的 holdings[sym].stale）。
    已知限制（摩根家用 IP 限定 3 檔）不視為新問題，僅列數量供對照。"""
    parts = []
    try:
        log = json.load(open(f"{REPO}/data/fetch-log.json", encoding="utf-8"))
        if log.get("success") is False and log.get("error"):
            parts.append(f"fetch_data: {str(log['error'])[:80]}")
    except Exception:
        pass
    known_limit = 0
    new_stale = []
    try:
        h = json.load(open(f"{REPO}/data/etf-holdings.json", encoding="utf-8"))
        for sym, v in (h.get("holdings") or {}).items():
            if not (isinstance(v, dict) and v.get("stale")):
                continue
            # 已知限制：摩根 IP 限定 3 檔（00401A/00989A/00996A）
            if sym in ("00401A", "00989A", "00996A"):
                known_limit += 1
            else:
                new_stale.append(sym)
    except Exception:
        pass
    if new_stale:
        parts.append(f"新 stale 檔 {len(new_stale)}: {new_stale[:6]}")
    if parts:
        parts.append(f"已知限制 stale {known_limit} 檔（摩根 IP 限定，不告警）")
    return f"（{'; '.join(parts)}）" if parts else ""


def main():
    lines = []
    try:
        asof = online_asof()
    except Exception as exc:
        print(f"🔴 哨兵無法讀取線上 stocks.json（Pages 掛了或網路異常）: {exc}")
        return 1
    gap = workday_gap(asof)
    if gap < 3:
        # P2：資料源健康度只在正常時的週日快照輸出（每週一次，不日日吵）
        if dt.date.today().weekday() == 6:
            hs = health_summary()
            if hs:
                print(f"ℹ️ 每週健康度快照: as_of={asof} {hs}")
        return 0  # 靜默
    lines.append(f"🔴 資料新鮮度告警：線上 as_of={asof}，已 {gap} 個工作日未推進（今日 {dt.date.today()}）")
    # 根因分類：先看本機有沒有未推送的更新（有的話是推送問題，沒有是管線問題）
    git = subprocess.run(["git", "-C", REPO, "status", "--porcelain"], capture_output=True, text=True)
    dirty = len([l for l in git.stdout.splitlines() if l and not l.startswith("??")])
    if dirty > 5:
        lines.append(f"偵測到本機有 {dirty} 個已修改資料檔未推送——管線有產出但推送被擋，嘗試自癒（重跑 QA＋推送）…")
        heal = selfheal()
        if heal:
            lines.append(heal)
        else:
            return 0  # 自癒成功且已推送：靜默
    else:
        lines.append("本機無未推送變更——管線可能未跑或 GitHub cron 延遲，觸發自癴重跑每日管線…")
        heal = selfheal()
        if heal:
            lines.append(heal)
        else:
            return 0
    hs = health_summary()
    if hs:
        lines.append(f"資料源健康度: {hs}")
    lines.append("（哨兵 scripts/quality_sentinel.py｜本機 cron，與 CI 路徑獨立）")
    print("\n".join(lines))
    return 1


if __name__ == "__main__":
    sys.exit(main())
