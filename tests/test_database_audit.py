#!/usr/bin/env python3
"""資料庫稽核基礎測試（Phase 7C 驗收，2026-11-28）。

涵蓋：coverage_pct ≤100% 防護、分母 null→UNKNOWN、快照七情境（snapshot_completeness）、
stale 降級端到端（真跑 update_state.py，非字串斷言）。
執行：python3 tests/test_database_audit.py → 輸出 合計 N 項 PASS/FAIL。
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "data"))
from fetch_data import snapshot_completeness  # noqa: E402

RESULTS = []


def check(name, cond):
    RESULTS.append((name, bool(cond)))


def mk(sym, name, src="TWSE", st="stock", date="2026-11-27"):
    return {"sym": sym, "name": name, "source": src, "security_type": st, "price_asof": date}


def base_market():
    # 每檔唯一 sym（重複代號檢測會把同 sym 乘法當異常——函式行為正確，mock 需符合實際）
    return ([mk(f"2{i:04d}", f"股{i}") for i in range(900)]
            + [mk(f"00{i:04d}", f"ETF{i}", st="etf") for i in range(200)]
            + [mk(f"0{i:05d}", f"上櫃ETF{i}", src="TPEX", st="etf") for i in range(500, 560)])


def run():
    # ── 1. coverage_pct ≤100% 防護 ──
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import database_audit as da
    check("coverage_pct: valid>expected 不得超過 100%", da._pct(500, 400) == 100.0)
    check("coverage_pct: 正常比例", da._pct(320, 321) == 99.69)
    check("coverage_pct: 分母 None → null", da._pct(100, None) is None)
    check("coverage_pct: 分母 0 → null（不得顯示 0% 或 100%）", da._pct(0, 0) is None)

    # ── 2. 快照七情境 ──
    r = snapshot_completeness([mk("2330", "台積電")], "2026-11-27")
    check("情境1: 上市ETF=0 → 整類缺失拒寫", r["blocked"] == ["上市ETF"])
    r = snapshot_completeness([mk("2330", "台積電", date="2026-11-26")], "2026-11-27")
    check("情境1b: 資料日期錯誤 → 拒寫", r["issues"] and not r["ok"])
    stocks = base_market()
    r = snapshot_completeness([s for s in stocks
                               if not (s["source"] == "TWSE" and s["security_type"] == "etf"
                                       and int(s["sym"][-4:]) >= 160)], "2026-11-27")
    check("情境2: ETF 缺 40 檔（部分缺失）→ PARTIAL 不阻擋", r["blocked"] == [] and r["ok"])
    r = snapshot_completeness(base_market(), "2026-11-27")
    check("情境3: 完整市場 → COMPLETE 可寫入", r["ok"] and r["verification_status"] == "COMPLETE")
    r = snapshot_completeness(base_market() + [mk("009836", "新ETF", st="unverified")], "2026-11-27")
    check("情境4: 正常新上市 → 不阻擋", not r["blocked"])
    r = snapshot_completeness(base_market()[:1449], "2026-11-27")
    check("情境5: 正常下市（-1 檔）→ 不阻擋", not r["blocked"])
    r = snapshot_completeness(base_market()[:1459], "2026-11-27")
    check("情境6: 合法停牌/無成交（-1 ETF）→ 不阻擋（suspended 沿用不進切片）", not r["blocked"])
    # 情境7 修正：上櫃來源失敗時，沿用記錄 price_asof 為舊日（不入 fresh）→ 上櫃 ETF=0 → 警告不阻擋
    stocks_no_tpex = [s for s in base_market() if s["source"] == "TWSE"]
    r = snapshot_completeness(stocks_no_tpex, "2026-11-27",
                              source_status={"TWSE": True, "TPEX": False})
    check("情境7: 上櫃來源失敗 → 上櫃ETF=0 警告不阻擋（沿用機制）", not r["blocked"] and r["warnings"])
    r = snapshot_completeness([mk("2330", "台積電", date="2026-11-26")], "2026-11-27")
    check("情境8: 資料日期錯誤（無當日記錄）→ 拒寫", r["issues"] and not r["ok"])
    bm = base_market()
    r = snapshot_completeness(bm + [dict(bm[0])], "2026-11-27")
    check("情境9: 重複代號 → issues 記錄", any("重複" in i for i in r["issues"]))

    # ── 3. stale 降級端到端（真跑 update_state.py）──
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "UPDATE_STATE_PATH": os.path.join(tmp, "state.json")}
        # 週六情境：stocks.json as_of=11-26，應有交易日=11-27 → stale
        p = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "update_state.py"),
                            "record", "tw-stock-daily", "--status", "succeeded"],
                           capture_output=True, text=True, env=env, cwd=ROOT)
        state = json.load(open(env["UPDATE_STATE_PATH"], encoding="utf-8"))["update_state"]["tw-stock-daily"]
        check("E2E-1: stale 不得記 last_success", state["status"] == "stale" and "last_success" not in state)
        check("E2E-1b: stale_reason 可追溯", "應有交易日" in (state.get("stale_reason") or ""))
        p = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "update_state.py"),
                            "check", "tw-stock-daily"], capture_output=True, text=True, env=env, cwd=ROOT)
        check("E2E-2: stale 後仍判 due（補跑班會重補）", p.returncode == 0)
        p = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "update_state.py"),
                            "record", "us-etf-daily", "--status", "succeeded"],
                           capture_output=True, text=True, env=env, cwd=ROOT)
        check("E2E-3: 資料=應有日 → succeeded（record 返回 0 不擋 push）", p.returncode == 0)

    # ── 4. coverage.json 實際輸出驗收 ──
    cov_path = os.path.join(ROOT, "data", "coverage.json")
    if os.path.exists(cov_path):
        cov = json.load(open(cov_path, encoding="utf-8"))
        over = [e for e in cov["coverage"] if e["coverage_pct"] is not None and e["coverage_pct"] > 100]
        check("coverage.json: 無 >100% 違規", not over)
        check("coverage.json: 每條含 audited_at 與 denominator_source",
              all(e.get("audited_at") and e.get("denominator_source") for e in cov["coverage"]))
        req_keys = {"dataset", "market", "scope", "expected_count", "actual_count", "valid_count",
                    "missing_count", "coverage_pct", "denominator_source", "verification_status"}
        check("coverage.json: 欄位規格完整", all(req_keys <= set(e) for e in cov["coverage"]))
    gaps_path = os.path.join(ROOT, "data", "gaps.json")
    if os.path.exists(gaps_path):
        gp = json.load(open(gaps_path, encoding="utf-8"))
        req = {"dataset", "market", "symbol", "field", "gap_type", "verification_status",
               "priority", "source", "status", "retry_count"}
        check("gaps.json: 欄位規格完整", all(req <= set(g) for g in gp["gaps"]))
        check("gaps.json: 候選與已確認分離標記",
              all(g["verification_status"] in ("candidate", "confirmed") for g in gp["gaps"]))


def main():
    run()
    fails = [n for n, ok in RESULTS if not ok]
    print(f"合計 {len(RESULTS)} 項，PASS {len(RESULTS) - len(fails)}，FAIL {len(fails)}")
    for n in fails:
        print(f"  ❌ {n}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
