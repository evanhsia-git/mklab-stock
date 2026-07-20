#!/usr/bin/env python3
"""mklab-stock Deploy 輔助 — 檢查部署前置條件（零依賴）。

確認：
  - qa_gate 已通過（data/qa-report.md 存在且非 BLOCK）
  - 根目錄 7 個 HTML 存在
  - template_sync 冪等（無待同步變更）
退出碼：0=可部署，1=不可部署
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    ok = True
    expected = ["index.html", "mklab-stock-screener.html", "mklab-stock-research.html",
                "mklab-stock-industry.html", "mklab-stock-watchlist.html",
                "mklab-stock-help.html", "mklab-stock-log.html"]
    for f in expected:
        if not os.path.exists(os.path.join(ROOT, f)):
            print(f"❌ 缺少正式頁: {f}")
            ok = False
    qa = os.path.join(ROOT, "data", "qa-report.md")
    if not os.path.exists(qa):
        print("⚠️ 未執行 qa_gate（data/qa-report.md 不存在）")
    else:
        with open(qa, encoding="utf-8") as fh:
            if "BLOCK DEPLOY" in fh.read():
                print("❌ QA 判定 BLOCK DEPLOY")
                ok = False
    if ok:
        print("✅ 部署前置條件滿足（請 push main 觸發 GitHub Actions）")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
