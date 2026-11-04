#!/usr/bin/env python3
"""讀取 qa_gate.py 的 JSON 結果；存在 Critical ERROR（allow_deploy=false）時以非 0 結束。

用法：python3 scripts/ci_qa_verdict.py qa-result.json
daily-update.yml（提交前）與 qa-gate.yml（PR/push）共用同一份判定，避免兩邊標準不一致。
"""
import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "qa-result.json"
try:
    r = json.load(open(path, encoding="utf-8"))
except Exception as e:
    print(f"🔴 無法讀取 QA 結果 {path}：{e}（視為未通過）")
    sys.exit(1)

allow = bool(r.get("allow_deploy", False))
errs = r.get("errors", 0)
warns = r.get("warnings", 0)
print(f"allow_deploy={allow} critical_errors={errs} warnings={warns}")
for c in r.get("checks", []):
    if c.get("status") == "ERROR":
        print(f"  ERROR  {c.get('cat')} / {c.get('name')}: {c.get('detail')}")
if not allow:
    print("🔴 BLOCK：存在 Critical ERROR，禁止提交／發布")
    sys.exit(1)
print("🟢 ALLOW：QA 閘門通過")
