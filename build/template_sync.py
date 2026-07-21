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

def sync_meta(html, meta, base):
    """
    Sync <head> content with proper CSS/JS links from meta.html and base.html.
    Preserves <base>, <meta charset>, <meta viewport>, <meta description>, 
    <link icon>, and page-specific scripts like data/twii_kdata.js.
    """
    # Find head section
    head_match = re.search(r'<head>.*?</head>', html, re.DOTALL)
    if not head_match:
        return html
    
    head = head_match.group(0)
    head_start = head_match.start()
    head_end = head_match.end()
    
    # Extract all link and script tags from meta.html and base.html
    # meta.html has CSS links and icon link
    meta_links = re.findall(r'<link[^>]*>', meta)
    # base.html has script tags
    base_scripts = re.findall(r'<script[^>]*>.*?</script>', base, flags=re.DOTALL)
    
    # Remove all existing link and script tags from head
    head_clean = re.sub(r'<link[^>]*>', '', head)
    head_clean = re.sub(r'<script[^>]*>.*?</script>', '', head_clean, flags=re.DOTALL)
    
    # Remove malformed lines (bare paths)
    head_clean = re.sub(r'^(?:vendor|assets/js|data)/[^\n]*\n?', '', head_clean, flags=re.MULTILINE)
    
    # Rebuild head: preserve meta tags, add links and scripts
    # Insert links after <meta viewport>
    links_block = '\n'.join(meta_links)
    head_with_links = re.sub(
        r'(<meta name="viewport"[^>]*>)',
        r'\1' + links_block,
        head_clean,
        count=1
    )
    
    # Insert scripts before </head>
    scripts_block = '\n'.join(base_scripts)
    head_final = re.sub(
        r'\s*</head>',
        f'\n{scripts_block}\n</head>',
        head_with_links,
        count=1
    )
    
    return html[:head_start] + head_final + html[head_end:]

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
            meta, base
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