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
from html.parser import HTMLParser

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

class StructureChecker(HTMLParser):
    """追蹤標籤開關，並在解析結束時報告結構問題。"""
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}
    RAW_CONTENT_TAGS = {"script", "style", "pre", "code", "textarea", "xmp"}
    
    # 關鍵區塊遮罩 (Bitmask)
    MASK_NAV = 1 << 0
    MASK_UTILBAR = 1 << 1
    MASK_DRAWER = 1 << 2
    MASK_CONTENT = 1 << 3
    MASK_ALL = MASK_NAV | MASK_UTILBAR | MASK_DRAWER | MASK_CONTENT

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []  # 儲存 (tag, lineno)
        self.body_children = 0
        self.in_body = False
        self.body_started = False
        self.style_open_lineno = None
        self.errors = []
        self.raw_depth = 0
        self.features = 0  # 關鍵區塊記錄

    def handle_starttag(self, tag, attrs):
        # 若在 raw content 內部，所有標籤只做棧追蹤不解析結構
        if self.raw_depth > 0:
            if tag in self.RAW_CONTENT_TAGS:
                if tag == "style":
                    self.style_open_lineno = self.getpos()[0]
                self.raw_depth += 1
                self.stack.append((tag, self.getpos()[0]))
            return

        # 進入 raw content 標籤
        if tag in self.RAW_CONTENT_TAGS:
            if tag == "style":
                self.style_open_lineno = self.getpos()[0]
            self.raw_depth += 1
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
        # 處理 raw content 標籤退出
        if tag in self.RAW_CONTENT_TAGS:
            self.raw_depth = max(0, self.raw_depth - 1)
            if tag == "style":
                self.style_open_lineno = None

        if self.raw_depth > 0 and tag not in self.RAW_CONTENT_TAGS:
            return

        if tag == "body":
            self.in_body = False

        # 彈棧優化：從最近的標籤匹配並清除
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i]
                break

    def report(self, fname):
        msgs = list(self.errors)
        base = os.path.basename(fname)
        is_help = base.endswith("-help.html") or base == "help.html"

        # 1-4: 檢查未關閉的關鍵結構標籤
        if self.stack:
            EXPECTED_ROOT_TAGS = {"html", "body", "div"}
            unclosed = [f"<{t}>(line {ln})" for t, ln in self.stack if t not in EXPECTED_ROOT_TAGS]
            if unclosed:
                msgs.append(f"未關閉標籤: {', '.join(unclosed)}")

        # 5: body 空白檢查
        if self.body_started and self.body_children == 0:
            msgs.append("解析後 <body> 無實質子元素（網頁可能空白）")

        # 6: style 未關閉檢查
        if self.style_open_lineno is not None:
            msgs.append(f"<style> 未關閉（開於 line {self.style_open_lineno}）")

        # 說明頁不檢查標準框架區塊
        if is_help:
            return msgs

        # 7: 關鍵區塊遮罩檢查
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