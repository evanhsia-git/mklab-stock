#!/usr/bin/env python3
"""mklab-stock Lint — 基礎結構/規範檢查（零依賴）。

檢查：
  - 禁止目錄（pages/config/components/src/tests/tools）不存在
  - 所有 Python 位於 skills/<name>/ 內（無散落 scripts/）
  - 根目錄 HTML 為唯一來源
退出碼：0=通過，1=違規
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FORBIDDEN_DIRS = ["pages", "config", "components", "src", "tests", "tools"]


def main():
    problems = []
    for d in FORBIDDEN_DIRS:
        if os.path.isdir(os.path.join(ROOT, d)):
            problems.append(f"禁止目錄存在: /{d}/")
    if os.path.isdir(os.path.join(ROOT, "scripts")):
        problems.append("禁止散落 scripts/：Python 應放 skills/<name>/")
    # 根目錄 HTML 為唯一來源：pages/ 已禁，這裡確認根有 7 個正式頁
    expected = ["index.html", "mklab-stock-screener.html", "mklab-stock-research.html",
                "mklab-stock-industry.html", "mklab-stock-watchlist.html",
                "mklab-stock-help.html", "mklab-stock-log.html"]
    for f in expected:
        if not os.path.exists(os.path.join(ROOT, f)):
            problems.append(f"缺少正式頁: {f}")

    if problems:
        print("❌ Lint 違規：")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("✅ Lint 通過（結構規範）")


if __name__ == "__main__":
    main()
