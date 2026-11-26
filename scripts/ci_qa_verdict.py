#!/usr/bin/env python3
"""QA verdict v2.0: validate report and fail closed.
Usage: python3 scripts/ci_qa_verdict.py [qa-result.json]
"""
import json
import math
import os
import sys


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"重複 JSON key: {key}")
        result[key] = value
    return result


def finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"非法數值: {value}")
    return number


def reject_constant(value):
    raise ValueError(f"非法 JSON 常數: {value}")


# 報告完整性契約（Data Protection v2.1）— 與 qa_gate.py 共用單一真相源
# qa_checks.json：verdict 的 required/門檻/總數全部來自設定檔（獨立可信來源），
# 報告自報的 required_checks 僅資訊性，且必須與設定檔一致（防縮減宣告）。
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_THIS_DIR, os.pardir, "skills", "qa-gate", "qa_checks.json"), encoding="utf-8") as _cf:
    _CONTRACT = json.load(_cf)
SCHEMA_VERSION = _CONTRACT["schema_version"]
EXPECTED_CHECKS_TOTAL = _CONTRACT["expected_checks_total"]
EXPECTED_CHECKS_FLOOR = _CONTRACT["expected_checks_min"]
REQUIRED_CHECKS = tuple(_CONTRACT["required_checks"])


# 2026-11-25 整合 ChatGPT v2.1：status 枚舉常數化（產生端 qa_gate.py 的四值對應）
STATUSES = ("PASS", "WARNING", "ERROR", "MANUAL")


def validate(report):
    if not isinstance(report, dict):
        raise ValueError("報告必須為 JSON object")
    if report.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"未知 schema_version: {report.get('schema_version')!r}（期望 {SCHEMA_VERSION}）")
    if report.get("scan_completed") is not True:
        raise ValueError("scan_completed 必須為 true（掃描未完整完成）")
    if type(report.get("allow_deploy")) is not bool:
        raise ValueError("allow_deploy 必須為 boolean")
    for key in ("errors", "warnings", "expected_checks"):
        if type(report.get(key)) is not int or report[key] < 0:
            raise ValueError(f"{key} 必須為非負整數")
    if report["expected_checks"] < EXPECTED_CHECKS_FLOOR:
        raise ValueError(f"檢查數量 {report['expected_checks']} 低於門檻 {EXPECTED_CHECKS_FLOOR}")
    checks = report.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("checks 必須為非空 list")
    if report["expected_checks"] != len(checks):
        raise ValueError(f"expected_checks({report['expected_checks']}) != len(checks)({len(checks)})")
    # 2026-11-26：與 qa_gate 同步範圍化——條件式項（TWSE_T_MINUS_1/US_RETURNS_MISSING/
    # 品質規則動態名）讓執行數合法浮動，只驗下限（防漏跑 fail closed），上限不設
    _slack = _CONTRACT.get("conditional_check_slack", 3)
    if len(checks) < EXPECTED_CHECKS_TOTAL - _slack:
        raise ValueError(
            f"檢查總數 {len(checks)} < 契約下限 {EXPECTED_CHECKS_TOTAL - _slack}（漏跑）")
    names = [c.get("name") if isinstance(c, dict) else None for c in checks]
    if len(names) != len(set(names)):
        raise ValueError("存在重複檢查名稱（湊數）")
    missing = [n for n in REQUIRED_CHECKS if n not in names]
    if missing:
        raise ValueError(f"必要檢查漏跑（契約真值比對）: {missing}")
    reported_required = report.get("required_checks")
    if sorted(reported_required or []) != sorted(REQUIRED_CHECKS):
        raise ValueError("報告自報 required_checks 與契約設定檔不一致（不得縮減）")
    # 2026-11-25 驗收修正：qa_gate.py 的 Check.manual() 產生合法的 MANUAL status
    # （Chart/Console/視覺回歸等人工驗證項，不計入自動阻擋）——原版會把正式報告
    # 全數誤擋（實證：現有 qa-result.json → "未知 status: 'MANUAL'"）。
    counts = {status: 0 for status in STATUSES}
    for i, check in enumerate(checks):
        if not isinstance(check, dict):
            raise ValueError(f"checks[{i}] 必須為 object")
        status = check.get("status")
        if not isinstance(status, str) or status not in counts:
            raise ValueError(f"checks[{i}] 未知 status: {status!r}")
        for key in ("cat", "name"):
            if not isinstance(check.get(key), str) or not check[key].strip():
                raise ValueError(f"checks[{i}].{key} 必須為非空字串")
        if "detail" not in check:
            raise ValueError(f"checks[{i}] 缺少 detail")
        counts[status] += 1
    for key, status in (("errors", "ERROR"), ("warnings", "WARNING")):
        if report[key] != counts[status]:
            raise ValueError(f"{key} 統計不一致: {report[key]} != {counts[status]}")
    if report["allow_deploy"] != (counts["ERROR"] == 0):
        raise ValueError("allow_deploy 與 ERROR 統計不一致")
    return counts


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 1:
        print("Usage: ci_qa_verdict.py [qa-result.json]", file=sys.stderr)
        return 1
    path = args[0] if args else "qa-result.json"
    try:
        with open(path, encoding="utf-8") as stream:
            report = json.load(stream, object_pairs_hook=unique_object,
                               parse_constant=reject_constant, parse_float=finite_float)
        counts = validate(report)
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        print(f"🔴 BLOCK：QA 報告無效 {path}: {exc}", file=sys.stderr)
        return 1
    allow = report["allow_deploy"]
    # 2026-11-25 整合 ChatGPT v2.1 的呈現強化：WARNING 逐項列出＋MANUAL 計數提示
    print(f"allow_deploy={allow} critical_errors={counts['ERROR']} "
          f"warnings={counts['WARNING']} manual={counts['MANUAL']}")
    for check in report["checks"]:
        if check["status"] == "ERROR":
            print(f"  ERROR   {check['cat']} / {check['name']}: {check['detail']}")
    for check in report["checks"]:
        if check["status"] == "WARNING":
            print(f"  WARNING {check['cat']} / {check['name']}: {check['detail']}")
    if counts["MANUAL"]:
        print(f"  NOTE    {counts['MANUAL']} 項需人工驗證（不阻擋自動發布）")
    if not allow:
        print("🔴 BLOCK：存在 Critical ERROR，禁止提交／發布")
        return 1
    print("🟢 ALLOW：QA 閘門通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
