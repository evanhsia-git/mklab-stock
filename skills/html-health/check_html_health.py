#!/usr/bin/env python3
"""
mklab-stock HTML 結構健康檢查

目的：在 push/CI 階段攔截「HTML 結構破壞導致網頁空白 / 功能失效」的問題。
本檔案的每一項檢查，都是這個專案真實出過的事故，不是憑空假設：

  1. <style> / </style> 配對未關閉 → parser 把整個 <body> 當成 CSS → 頁面空白
  2. <head> / <body> / <script> 配對
  3. 解析後 <body> 必須有子元素（抓出「載入後空白」的實質失效）
  4. <style> 必須在 <body> 之前關閉（否則 body 被吞）
  5. 關鍵區塊存在（nav / utilbar / drawer / 至少一個 table 或 section 或 mklab-*）
  6. 【多餘的閉合標籤】例如 research.html 曾經多寫 3 個 </div>，把 <footer>
     擠出 <main> 的巢狀結構外。舊版邏輯遇到「找不到對應開標籤的 </div>」時
     會靜默忽略（迴圈跑完沒找到就直接放過），完全偵測不到——現在會立刻報錯。
  7. 【重複的 id】同一頁面出現兩個一樣的 id，會讓 document.getElementById()
     行為不可預期（拿到第一個、事件綁定對象錯亂等）。
  8. 【未替換的 {{PLACEHOLDER}}】曾經發生 <title>{{TITLE}}</title> 直接被
     部署上線，因為從沒有任何程式做過字串替換。
  9. 【MKLAB.* 依賴但漏載核心 script】曾經發生 6 個子頁面完全沒有
     <script src=".../mklab-core.js">，導致 MKLAB 是 undefined、整頁功能
     全部靜默失效。只要 inline script 用到 MKLAB.xxx，就必須先載入對應核心檔。

用法：
  python3 skills/html-health/check_html_health.py [檔案或目錄...]
  預設檢查 repo 根目錄下的 *.html（不含 vendor/、node_modules/）
退出碼：0=全部健康，1=有失敗
"""
import os
import re
import sys
import glob
from html.parser import HTMLParser

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# inline script 用到左邊的寫法，就必須載入右邊的 <script src="assets/js/...">
CORE_SCRIPT_DEPS = [
    (re.compile(r'\bMKLAB\.data\.'), 'assets/js/data-client.js'),
    (re.compile(r'\bMKLAB\.(DataTable|Drawer|Shell|Watch|Notes|Portfolio|initDrawer|setFreshness|cellPct)\b'), 'assets/js/mklab-core.js'),
    (re.compile(r'<mklab-kline\b', re.I), 'assets/js/mklab-wc.js'),
]

PLACEHOLDER_RE = re.compile(r'\{\{[A-Z0-9_]+\}\}')


class StructureChecker(HTMLParser):
    """追蹤標籤開關，並在解析結束時報告結構問題。"""
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}
    # 注意：mklab-kline 等自訂元素在本專案一律以 <mklab-kline>...</mklab-kline> 雙邊標籤使用，
    # 不是 void element，故意不放進 VOID，讓它們走正常的開合配對追蹤。

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
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
        self.saw_content = False
        self.code_stack = []
        self.pre_depth = 0
        self.seen_ids = {}
        self.extra_close = []

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        attrs_dict = dict(attrs)

        if tag_lower == "code":
            self.code_stack.append(self.getpos()[0])
            self.stack.append((tag, self.getpos()[0]))
            return
        if self.code_stack:
            return
        if tag_lower == "pre":
            self.pre_depth += 1
            self.stack.append((tag, self.getpos()[0]))
            return
        if self.pre_depth > 0:
            return

        _id = attrs_dict.get("id")
        if _id:
            self.seen_ids.setdefault(_id, []).append(self.getpos()[0])

        if tag_lower == "style":
            self.style_open_lineno = self.getpos()[0]
            self.style_closed = False
            self.stack.append((tag, self.getpos()[0]))
            return
        if tag_lower == "body":
            self.in_body = True
            self.body_started = True
            if not self.style_closed:
                self.errors.append(
                    f"line {self.getpos()[0]}: <body> 出現在 <style> 未關閉之後"
                    f"（style 開於 line {self.style_open_lineno}）——body 會被當成 CSS 吞掉")
        if self.in_body and tag_lower not in self.VOID:
            self.body_children += 1
        if tag_lower == "nav":
            self.saw_nav = True
        cls = attrs_dict.get("class") or ""
        if "utilbar" in cls:
            self.saw_utilbar = True
        if "drawer" in cls:
            self.saw_drawer = True
        if tag_lower in ("table", "section") or tag_lower.startswith("mklab-"):
            self.saw_content = True
        if tag_lower not in self.VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):
        tag_lower = tag.lower()

        if tag_lower == "code":
            if self.code_stack:
                self.code_stack.pop()
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == "code":
                    del self.stack[i]
                    break
            return
        if self.code_stack:
            return
        if tag_lower == "pre":
            if self.pre_depth > 0:
                self.pre_depth -= 1
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == "pre":
                    del self.stack[i]
                    break
            return
        if self.pre_depth > 0:
            return

        if tag_lower == "style":
            self.style_closed = True
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == "style":
                    del self.stack[i]
                    break
            return
        if tag_lower == "body":
            self.in_body = False

        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i]
                break
        else:
            self.extra_close.append((tag_lower, self.getpos()[0]))

    def report(self, fname, src=""):
        msgs = []
        base = os.path.basename(fname)
        is_help = base.endswith("-help.html") or base == "help.html"

        if self.stack:
            unclosed = [f"{t}(line {ln})" for t, ln in self.stack]
            msgs.append(f"未關閉標籤: {', '.join(unclosed)}")

        if self.extra_close:
            extra = [f"</{t}>(line {ln})" for t, ln in self.extra_close]
            msgs.append(f"多餘的閉合標籤（找不到對應開標籤，通常是巢狀結構被打亂）: {', '.join(extra)}")

        dups = {k: v for k, v in self.seen_ids.items() if len(v) > 1}
        if dups:
            detail = ", ".join(f"#{k}(line {','.join(map(str, v))})" for k, v in dups.items())
            msgs.append(f"重複的 id: {detail}")

        if self.body_started and self.body_children == 0:
            msgs.append("解析後 <body> 無子元素（網頁會空白）")

        if not self.style_closed:
            msgs.append(f"<style> 未關閉（開於 line {self.style_open_lineno}）")

        placeholders = sorted(set(PLACEHOLDER_RE.findall(src)))
        if placeholders:
            msgs.append(f"發現未替換的樣板佔位符: {', '.join(placeholders)}")

        loaded_scripts = set(re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', src))
        for pattern, required_src in CORE_SCRIPT_DEPS:
            if pattern.search(src) and not any(s.endswith(required_src) for s in loaded_scripts):
                msgs.append(f"用到 {pattern.pattern!r} 但沒有載入 <script src=\"{required_src}\">")

        if is_help:
            return msgs

        if not self.saw_nav:
            msgs.append("缺少 <nav> 導航列")
        if not self.saw_utilbar:
            msgs.append("缺少 .utilbar 工具列")
        if not self.saw_drawer:
            msgs.append("缺少 .drawer 設定抽屜")
        if not self.saw_content:
            msgs.append("缺少 table/section/mklab-* 主要內容區塊")
        return msgs


def check_file(path):
    with open(path, encoding="utf-8") as f:
        html = f.read()
    checker = StructureChecker()
    try:
        checker.feed(html)
    except Exception as e:
        return [f"解析異常: {e}"]
    return checker.report(path, html)


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
