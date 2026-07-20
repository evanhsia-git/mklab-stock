#!/usr/bin/env python3
"""
MKLAB Template Synchronizer — 模板同步器（零依賴）

角色定位
--------
本工具是「Template Synchronizer（模板同步器）」，不是「Website Generator（網站產生器）」。
根目錄 HTML（index.html、mklab-stock-*.html）為「唯一正式網站」，直接由 Agent 維護。
本工具只負責把 templates/ 的共用區塊同步進根目錄既有 HTML，不重新產生整頁。

同步項目
--------
  - Header : <header class="sticky-header">...</header>
  - Drawer : <aside class="drawer">...</aside> + <div class="drawer-mask">
  - Footer : <footer class="footer">...</footer>
  - Meta   : <head> 內的 stylesheet <link> 與核心 <script src>（vendor/、assets/js/）
             （保留各頁 title / description / base / icon / 頁面專屬 script 如 data/）

設計原則（MKLAB Framework v1.x）
------------------------------
  - 不得建立第二份頁面來源（無 pages/）
  - 不得重新生成整個網站
  - 保留向下相容：GitHub Pages / Fork First / Web Components / GrapesJS / 既有 Build 流程

用法
----
  python build/template_sync.py
"""

import os
import re
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "templates")

ROOT_HTMLS = sorted(glob.glob(os.path.join(ROOT, "*.html")))


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


# ---------------------------------------------------------------------------
# 各區塊同步函式（皆為就地替換，不動頁面專屬內容）
# ---------------------------------------------------------------------------

def sync_header(html, header):
    """替換 <header class="sticky-header">...</header>。"""
    pat = re.compile(r'<header class="sticky-header"[^>]*>.*?</header>', re.DOTALL)
    if pat.search(html):
        return pat.sub(header.strip(), html)
    return html


def sync_footer(html, footer):
    """替換 <footer class="footer">...</footer>。"""
    pat = re.compile(r'<footer class="footer"[^>]*>.*?</footer>', re.DOTALL)
    if pat.search(html):
        return pat.sub(footer.strip(), html)
    return html


def sync_drawer(html, drawer):
    """替換 <aside class="drawer">...</aside> + 後續 <div class="drawer-mask">。"""
    pat = re.compile(
        r'<aside class="drawer"[^>]*>.*?</aside>\s*'
        r'<div class="drawer-mask"[^>]*>.*?</div>',
        re.DOTALL,
    )
    if pat.search(html):
        return pat.sub(drawer.strip(), html)
    return html


def sync_meta(html, meta, base):
    """同步 <head> 內的 stylesheet <link> 與核心 <script src>（vendor/、assets/js/）。

    保留：<base>、<meta charset>、<meta viewport>、<title>、<meta description>、
          <link icon>、以及頁面專屬 script（如 data/twii_kdata.js）。
    """
    # 從 meta.html 取 stylesheet 行
    meta_links = re.findall(r'<link rel="stylesheet" href="assets/css/[^"]*">', meta)
    # 從 base.html 取核心 script 行（vendor/、assets/js/）
    meta_scripts = re.findall(
        r'<script src="(vendor/[^"]*|assets/js/[^"]*)"[^>]*></script>', base
    )

    def repl_link(m):
        href = m.group(1)
        for ml in meta_links:
            if href in ml:
                return ml
        return m.group(0)

    def repl_script(m):
        src = m.group(1)
        for ms in meta_scripts:
            if src in ms:
                return ms
        return m.group(0)

    html = re.sub(
        r'<link rel="stylesheet" href="(assets/css/[^"]*)"[^>]*>',
        repl_link,
        html,
    )
    html = re.sub(
        r'<script src="(vendor/[^"]*|assets/js/[^"]*)"[^>]*></script>',
        repl_script,
        html,
    )
    return html


def main():
    header = read(os.path.join(TEMPLATES, "header.html"))
    drawer = read(os.path.join(TEMPLATES, "drawer.html"))
    footer = read(os.path.join(TEMPLATES, "footer.html"))
    meta = read(os.path.join(TEMPLATES, "meta.html"))
    base = read(os.path.join(TEMPLATES, "base.html"))

    changed = 0
    for p in ROOT_HTMLS:
        html = read(p)
        new = sync_meta(
            sync_footer(sync_drawer(sync_header(html, header), drawer), footer),
            meta,
            base,
        )
        if new != html:
            write(p, new)
            changed += 1
            print(f"🔄 {os.path.basename(p)} 同步更新")
        else:
            print(f"✅ {os.path.basename(p)} 已是最新")

    print(f"\n完成：{changed} 個檔案更新，{len(ROOT_HTMLS) - changed} 個無變更。")


if __name__ == "__main__":
    main()
