#!/usr/bin/env python3
"""
mklab-stock HTML 結構健康檢查

目的：在 push/CI 階段攔截「HTML 結構破壞導致網頁空白」的問題。
用法：python3 scripts/check_html_health.py [檔案或目錄...]
退出碼：0=全部健康，1=有失敗
"""
import os
import sys
import glob
import re
from html.parser import HTMLParser

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class StructureChecker(HTMLParser):
    """追蹤標籤開關，並在解析結束時報告結構問題。"""
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}
    RAW_CONTENT_TAGS = {"script", "style", "textarea", "xmp", "plaintext", "listing", "template", "noscript"}

    MASK_NAV = 1 << 0
    MASK_UTILBAR = 1 << 1
    MASK_DRAWER = 1 << 2
    MASK_CONTENT = 1 << 3
    MASK_ALL = MASK_NAV | MASK_UTILBAR | MASK_DRAWER | MASK_CONTENT

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.body_children = 0
        self.in_body = False
        self.body_started = False
        self.style_open_lineno = None
        self.errors = []
        self.raw_depth = 0
        self.code_depth = 0
        self.features = 0

    def handle_starttag(self, tag, attrs):
        if self.code_depth > 0:
            if tag in {"code", "pre"}:
                self.code_depth += 1
                if tag not in self.VOID:
                    self.stack.append((tag, self.getpos()[0]))
            return

        if self.raw_depth > 0:
            if tag in self.RAW_CONTENT_TAGS:
                if tag == "style":
                    self.style_open_lineno = self.getpos()[0]
                self.raw_depth += 1
                self.stack.append((tag, self.getpos()[0]))
            return

        if tag in self.RAW_CONTENT_TAGS:
            if tag == "style":
                self.style_open_lineno = self.getpos()[0]
            self.raw_depth += 1
            self.stack.append((tag, self.getpos()[0]))
            return

        if tag in {"code", "pre"}:
            self.code_depth += 1
            if tag not in self.VOID:
                self.stack.append((tag, self.getpos()[0]))
            return

        if tag == "body":
            self.in_body = True
            self.body_started = True
            if self.style_open_lineno is not None:
                self.errors.append(
                    f"line {self.getpos()[0]}: <body> 出現在未關閉的 <style> 之後 "
                    f"(style 開於 line {self.style_open_lineno})，body 內容會被當作 CSS 解析。"
                )

        if self.in_body and tag not in self.VOID:
            self.body_children += 1

        if tag == "nav":
            self.features |= self.MASK_NAV
        elif tag in {"table", "section", "mklab-datatable", "mklab-kline"}:
            self.features |= self.MASK_CONTENT

        for attr, value in attrs:
            if attr == "class" and value:
                if "utilbar" in value:
                    self.features |= self.MASK_UTILBAR
                if "drawer" in value:
                    self.features |= self.MASK_DRAWER

        if tag not in self.VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):
        if self.code_depth > 0:
            if tag in {"code", "pre"}:
                self.code_depth = max(0, self.code_depth - 1)
                if tag not in self.VOID:
                    for i in range(len(self.stack) - 1, -1, -1):
                        if self.stack[i][0] == tag:
                            del self.stack[i]
                            break
            return

        if self.raw_depth > 0:
            if tag in self.RAW_CONTENT_TAGS:
                self.raw_depth = max(0, self.raw_depth - 1)
                if tag == "style":
                    self.style_open_lineno = None
                for i in range(len(self.stack) - 1, -1, -1):
                    if self.stack[i][0] == tag:
                        del self.stack[i]
                        break
            return

        if tag in self.RAW_CONTENT_TAGS:
            if tag == "style":
                self.style_open_lineno = None
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i]
                    break
            return

        if tag == "body":
            self.in_body = False

        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i]
                break

    def report(self, fname):
        msgs = list(self.errors)
        base = os.path.basename(fname)
        is_help = base.endswith("-help.html") or base == "help.html"

        if self.stack:
            EXPECTED_ROOT_TAGS = {"html", "body", "div"}
            unclosed = [f"<{t}>(line {ln})" for t, ln in self.stack if t not in EXPECTED_ROOT_TAGS]
            if unclosed:
                msgs.append(f"未關閉標籤: {', '.join(unclosed)}")

        if self.body_started and self.body_children == 0:
            msgs.append("解析後 <body> 無實質子元素（網頁可能空白）")

        if self.style_open_lineno is not None:
            msgs.append(f"<style> 未關閉（開於 line {self.style_open_lineno}）")

        if is_help:
            return msgs

        if (self.features & self.MASK_ALL) != self.MASK_ALL:
            if not (self.features & self.MASK_NAV):
                msgs.append("缺少 <nav> 導航列")
            if not (self.features & self.MASK_UTILBAR):
                msgs.append("缺少 .utilbar 工具列")
            if not (self.features & self.MASK_DRAWER):
                msgs.append("缺少 .drawer 設定抽屜")
            if not (self.features & self.MASK_CONTENT):
                msgs.append("缺少主要內容區塊 (table/section/WC 元件)")

        return msgs


def check_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            html = f.read()

        # Preprocess: escape RAW_CONTENT_TAGS inside <code> and <pre> so HTMLParser
        # doesn't enter "raw text mode" and swallow all subsequent tags.
        # 關鍵修復：將 <style> 等標籤轉為 HTML 實體 &lt;style&gt;，而非自我替換
        def escape_in_code_pre(match):
            tag_name = match.group(1)
            content = match.group(2)
            if tag_name in ("code", "pre"):
                # 將 code/pre 內的 RAW 標籤轉為 HTML 實體，避免 HTMLParser 誤判為真實標籤
                for tag in ("style", "script", "textarea", "xmp", "plaintext", "listing", "template", "noscript"):
                    content = content.replace(f"<{tag}>", f"&lt;{tag}&gt;")
                    content = content.replace(f"</{tag}>", f"&lt;/{tag}&gt;")
            return f"<{tag_name}>{content}</{tag_name}>"

        html = re.sub(r'<(code|pre)>(.*?)</\1>', escape_in_code_pre, html, flags=re.DOTALL)

        checker = StructureChecker()
        checker.feed(html)
        return checker.report(path)
    except Exception as e:
        return [f"檔案讀取或解析異常: {e}"]


def main():
    targets = sys.argv[1:]
    if not targets:
        targets = glob.glob(os.path.join(ROOT, "*.html")) + glob.glob(os.path.join(ROOT, "Prototypes", "*.html"))

    targets = [t for t in targets if os.path.isfile(t)]
    if not targets:
        print("❌ 找不到要檢查的 HTML 檔案")
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

    print(f"\n檢查完畢：{'有檔案失敗' if failed else '全部健康'} ({len(targets) - failed}/{len(targets)} 通過)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())