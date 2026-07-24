#!/usr/bin/env python3
"""
MKLAB Template Synchronizer - zero-dep, inplace-only for templates.
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

def sync_header(html, header):
    pat = re.compile(r'<header class="sticky-header"[^>]*>.*?</header>', re.DOTALL)
    return pat.sub(header.strip(), html) if pat.search(html) else html

def sync_footer(html, footer):
    pat = re.compile(r'<footer class="footer"[^>]*>.*?</footer>', re.DOTALL)
    return pat.sub(footer.strip(), html) if pat.search(html) else html

def sync_drawer(html, drawer):
    pat = re.compile(
        r'<aside class="drawer"[^>]*>.*?</aside>\s*<div class="drawer-mask"[^>]*>.*?</div>',
        re.DOTALL,
    )
    return pat.sub(drawer.strip(), html) if pat.search(html) else html

def sync_meta(html, base):
    """
    Sync <head> with proper CSS/JS from base.html.
    Preserves any existing head content but replaces with fresh base.html head.
    """
    # Extract head content from base.html
    head_match = re.search(r'<head>.*?</head>', base, re.DOTALL)
    if not head_match:
        return html
    
    new_head = head_match.group(0)
    
    # Replace head in target HTML
    head_match_target = re.search(r'<head>.*?</head>', html, re.DOTALL)
    if not head_match_target:
        return html
    
    return html[:head_match_target.start()] + new_head + html[head_match_target.end():]

def main():
    header = read(os.path.join(TEMPLATES, "header.html"))
    drawer = read(os.path.join(TEMPLATES, "drawer.html"))
    footer = read(os.path.join(TEMPLATES, "footer.html"))
    base = read(os.path.join(TEMPLATES, "base.html"))

    changed = 0
    for p in ROOT_HTMLS:
        html = read(p)
        new = sync_meta(
            sync_footer(sync_drawer(sync_header(html, header), drawer), footer),
            base
        )
        if new != html:
            write(p, new)
            changed += 1
            print(f"[UPDATE] {os.path.basename(p)}")
        else:
            print(f"[OK] {os.path.basename(p)}")

    print(f"\nDone: {changed} updated, {len(ROOT_HTMLS) - changed} unchanged.")

if __name__ == "__main__":
    main()