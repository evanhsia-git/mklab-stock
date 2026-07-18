#!/usr/bin/env python3
"""
MKLAB Template Framework — 純靜態頁面組裝器（零依賴）

讀取 templates/ + pages/ → 輸出根目錄完整 HTML
用法：python build/build_pages.py
"""
import os
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, 'templates')
PAGES = os.path.join(ROOT, 'pages')


def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def build():
    base = read(os.path.join(TEMPLATES, 'base.html'))
    meta = read(os.path.join(TEMPLATES, 'meta.html'))
    header = read(os.path.join(TEMPLATES, 'header.html'))
    drawer = read(os.path.join(TEMPLATES, 'drawer.html'))
    footer = read(os.path.join(TEMPLATES, 'footer.html'))

    # 預設值（page 可覆寫）
    default_title = 'mklab-stock'
    default_description = 'mklab-stock — 台股/美股/中股免費分析儀表板，提供產業動態、個股研究、技術指標與綜合評分。'

    pages = sorted(glob.glob(os.path.join(PAGES, '*.html')))
    if not pages:
        print('⚠️ pages/ 目錄下沒有 HTML 檔案')
        return

    for page in pages:
        name = os.path.basename(page)
        content = read(page)

        # 從 page 內容抽取 {{TITLE}} 標記（若有）
        import re
        m = re.search(r'\{\{TITLE\}\}(.+?)\{\{/TITLE\}\}', content, re.DOTALL)
        if m:
            page_title = m.group(1).strip()
            content = content.replace(m.group(0), '')  # 移除標記，只留內容
        else:
            page_title = default_title

        # 從 page 內容抽取 {{DESCRIPTION}} 標記（若有）
        m = re.search(r'\{\{DESCRIPTION\}\}(.+?)\{\{/DESCRIPTION\}\}', content, re.DOTALL)
        if m:
            page_description = m.group(1).strip()
            content = content.replace(m.group(0), '')
        else:
            page_description = default_description

        page_meta = (meta
                     .replace('{{TITLE}}', page_title)
                     .replace('{{DESCRIPTION}}', page_description))

        html = (base
                .replace('{{META}}', page_meta)
                .replace('{{HEADER}}', header)
                .replace('{{DRAWER}}', drawer)
                .replace('{{CONTENT}}', content)
                .replace('{{FOOTER}}', footer))

        out = os.path.join(ROOT, name)
        with open(out, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f'✅ {name} (title: {page_title})')


if __name__ == '__main__':
    build()