#!/usr/bin/env python3
"""QA verdict v2.0: validate report and fail closed.
Usage: python3 scripts/ci_qa_verdict.py [qa-result.json]
"""
import json
import math
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


def validate(report):
    if not isinstance(report, dict):
        raise ValueError("報告必須為 JSON object")
    if type(report.get("allow_deploy")) is not bool:
        raise ValueError("allow_deploy 必須為 boolean")
    for key in ("errors", "warnings"):
        if type(report.get(key)) is not int or report[key] < 0:
            raise ValueError(f"{key} 必須為非負整數")
    checks = report.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("checks 必須為非空 list")
    # 2026-11-25 驗收修正：qa_gate.py 的 Check.manual() 產生合法的 MANUAL status
    # （Chart/Console/視覺回歸等人工驗證項，不計入自動阻擋）——原版會把正式報告
    # 全數誤擋（實證：現有 qa-result.json → "未知 status: 'MANUAL'"）。
    counts = {"PASS": 0, "WARNING": 0, "ERROR": 0, "MANUAL": 0}
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
    except (OSError, ValueError, RecursionError) as exc:
        print(f"🔴 BLOCK：QA 報告無效 {path}: {exc}", file=sys.stderr)
        return 1
    allow = report["allow_deploy"]
    print(f"allow_deploy={allow} critical_errors={counts['ERROR']} warnings={counts['WARNING']}")
    for check in report["checks"]:
        if check["status"] == "ERROR":
            print(f"  ERROR  {check['cat']} / {check['name']}: {check['detail']}")
    if not allow:
        print("🔴 BLOCK：存在 Critical ERROR，禁止提交／發布")
        return 1
    print("🟢 ALLOW：QA 閘門通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
