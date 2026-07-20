#!/usr/bin/env python3
"""mklab-stock Development Helper — 開發輔助小工具（零依賴）。

功能：
  - 列出所有 Skill 與其腳本
  - 檢查 Skill 結構完整性（每個 skill 含 skill.md）
用法：
  python3 skills/development/helper.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILLS = os.path.join(ROOT, "skills")


def main():
    if not os.path.isdir(SKILLS):
        print("❌ skills/ 不存在")
        sys.exit(1)
    print("=== Skill 清單 ===")
    for name in sorted(os.listdir(SKILLS)):
        sdir = os.path.join(SKILLS, name)
        if not os.path.isdir(sdir):
            continue
        has_skill = os.path.exists(os.path.join(sdir, "skill.md"))
        py = [f for f in os.listdir(sdir) if f.endswith(".py")]
        print(f"  {name:14s} skill.md={'✓' if has_skill else '✗'}  py={py}")
    print("\n開發原則：優先建立 Skill，Minimal Changes，不過度工程化。")


if __name__ == "__main__":
    main()
