#!/usr/bin/env python3
"""
mklab-stock HTML 結構健康檢查

目的：在 push/CI 階段攔截「HTML 結構破壞導致網頁空白」的問題。
經典案例：watchlist 缺 </style> 關標籤 → parser 把整個 <body> 當成 CSS → 頁面空白。

檢查項目：
  1. <style> / </style> 配對（未關閉會吞掉 body）
  2. <head> / </head> 配對
  3. <body> / </body> 配對
  4. <script> / </script> 配對
  5. 解析後 <body> 必須有子元素（抓出「載入後空白」的實質失效）
  6. <style> 必須在 <body> 之前關閉（否則 body 被吞）
  7. 關鍵區塊存在（nav / utilbar / drawer / 至少一個 table 或 section）

用法：
  python3 scripts/check_html_health.py [檔案或目錄...]
  預設檢查 ../ 下的 *.html（不含 vendor/、node_modules/）
退出碼：0=全部健康，1=有失敗
"""
import os
import sys
import glob
from html.parser import HTMLParser

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class StructureChecker(HTMLParser):
    """追蹤標籤開關，並在解析結束時報告結構問題。"""
    VOID = {"area","base","br","col","embed","hr","img","input",
            "link","meta","param","source","track","wbr"}
    # SVG 內部標籤允許自閉合，但 HTMLParser 仍會收到 start/end，我們只追蹤外部結構

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []          # (tag, lineno)
        self.body_children = 0
        self.in_body = False
        self.style_open_lineno = None
        self.style_closed = True
        self.body_started = False
        self.errors = []
        self.warnings = []
        self.saw_nav = False
        self.saw_utilbar = False
        self.saw_drawer = False
        self.saw_table_or_section = False

    def handle_starttag(self, tag, attrs):
        if tag == "style":
            self.style_open_lineno = self.getpos()[0]
            self.style_closed = False
        if tag == "body":
            self.in_body = True
            self.body_started = True
            # style 必須已關閉
            if not self.style_closed:
                self.errors.append(
                    f"line {self.getpos()[0]}: <body> 出現在 <style> 未關閉之後"
                    f"（style 開於 line {self.style_open_lineno}）——body 會被當成 CSS 吞掉")
        if self.in_body and tag not in self.VOID:
            self.body_children += 1
        # 關鍵區塊標記
        if tag == "nav":
            self.saw_nav = True
        cls = dict(attrs).get("class") or ""
        if "utilbar" in cls:
            self.saw_utilbar = True
        if "drawer" in cls:
            self.saw_drawer = True
        if tag in ("table", "section"):
            self.saw_table_or_section = True
        # 非 void 且非自閉合 → 入棧
        if tag not in self.VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag == "style":
            self.style_closed = True
            # 從堆疊移除最後一個 style（若有）
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == "style":
                    del self.stack[i]
                    break
            return
        if tag == "body":
            self.in_body = False
        # 彈棧（寬鬆匹配：找最近的同名開標籤）
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i]
                break

    def report(self, fname):
        msgs = []
        base = os.path.basename(fname)
        is_help = base.endswith("-help.html") or base == "help.html"
        # 1-4: 未關閉標籤
        if self.stack:
            unclosed = [f"{t}(line {ln})" for t, ln in self.stack]
            msgs.append(f"未關閉標籤: {', '.join(unclosed)}")
        # 5: body 空白
        if self.body_started and self.body_children == 0:
            msgs.append("解析後 <body> 無子元素（網頁會空白）")
        # 6: style 未關閉
        if not self.style_closed:
            msgs.append(f"<style> 未關閉（開於 line {self.style_open_lineno}）")
        if is_help:
            # 說明頁：只檢結構，不強求 nav/utilbar/drawer
            return msgs
        # 7: 關鍵區塊
        if not self.saw_nav:
            msgs.append("缺少 <nav> 導航列")
        if not self.saw_utilbar:
            msgs.append("缺少 .utilbar 工具列")
        if not self.saw_drawer:
            msgs.append("缺少 .drawer 設定抽履")
        if not self.saw_table_or_section:
            msgs.append("缺少 table/section 主要內容區塊")
        return msgs


def check_file(path):
    with open(path, encoding="utf-8") as f:
        html = f.read()
    checker = StructureChecker()
    try:
        checker.feed(html)
    except Exception as e:
        return [f"解析異常: {e}"]
    return checker.report(path)


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else None
    if not targets:
        targets = glob.glob(os.path.join(ROOT, "*.html"))
        targets += glob.glob(os.path.join(ROOT, "Prototypes", "*.html"))
    targets = [t for t in targets if os.path.isfile(t)]
    if not targets:
        print("找不到要檢查的 HTML 檔")
        return 1

    failed = 0
    for t in sorted(targets):
        msgs = check_file(t)
        rel = os.path.relpath(t, ROOT)
        if msgs:
            failed += 1
            print(f"❌ {rel}")
            for m in msgs:
                print(f"   - {m}")
        else:
            print(f"✅ {rel}")
    print("")
    if failed:
        print(f"失敗 {failed} 個檔案")
        return 1
    print(f"全部 {len(targets)} 個檔案健康")
    return 0


if __name__ == "__main__":
    sys.exit(main())
