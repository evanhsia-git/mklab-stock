#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_digest.py — 每日市場摘要 + RSS Feed 產生器

設計原則（遵循本專案架構憲法）：
  - 靜態優先：只讀既有的 data/stocks.json / data/indices.json / data/industry.json，
    不呼叫任何外部 API，不需要網路。
  - 零密鑰：完全不需要任何 API key 或第三方服務。
  - Fork First：純 Python stdlib（json / datetime / os / glob / xml escape），
    不需要 pip install 任何套件。
  - 低維護：RSS 每次執行都從 data/digest/*.json「重新完整產生」，而不是對舊的
    rss.xml 做增量修改，避免累積性的 XML 損毀風險；舊摘要只保留最近 30 篇。

用法：
  python skills/data/build_digest.py

輸出：
  data/digest/{YYYYMMDD}.json   結構化每日摘要（供未來查詢 / digest 頁使用）
  rss.xml                       repo 根目錄，GitHub Pages 直接可訂閱
"""
import json
import os
import glob
from datetime import datetime, timezone
from xml.sax.saxutils import escape as xml_escape

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(ROOT, 'data')
DIGEST_DIR = os.path.join(DATA_DIR, 'digest')
RSS_PATH = os.path.join(ROOT, 'rss.xml')
SITE_URL = 'https://evanhsia-git.github.io/mklab-stock/'
MAX_RSS_ITEMS = 30


def load_json(path):
    full = os.path.join(DATA_DIR, path)
    if not os.path.exists(full):
        print(f'[build_digest] 找不到 {path}，略過相關區塊')
        return None
    with open(full, encoding='utf-8') as f:
        return json.load(f)


# 綜合評分公式的唯一來源：data/scoring-config.json
# 前端 index.html 的 computeScore() 與 mklab-stock-help.html 的說明表都必須跟這份一致
# （由 tests/test_known_errors.py 的「評分設定單一來源」檢查把關）。
SCORE_CFG = json.load(open(os.path.join(DATA_DIR, 'scoring-config.json'), encoding='utf-8'))


def compute_score(s):
    """依 data/scoring-config.json 計算綜合評分；任一欄位缺漏則不計分。"""
    vals = {}
    for c in SCORE_CFG['components']:
        v = s.get(c['key'])
        if v is None:
            return None
        vals[c['key']] = v
    score = 0.0
    for c in SCORE_CFG['components']:
        v = vals[c['key']]
        x = (c['base'] - v) if c.get('direction') == 'low' else (v - c['base'])
        score += min(c['max'], x * c['coef'])
    if SCORE_CFG.get('min_zero', True):
        score = max(0.0, score)
    return round(score, SCORE_CFG.get('round_decimals', 1))


def build_digest():
    stocks_data = load_json('stocks.json')
    indices_data = load_json('indices.json')
    industry_data = load_json('industry.json')

    stocks = (stocks_data or {}).get('stocks', [])
    as_of = (stocks_data or {}).get('meta', {}).get('as_of') or datetime.now().strftime('%Y-%m-%d')

    # 漲幅 / 跌幅前 5 大（排除 ETF、排除缺漲跌資料）
    real_stocks = [s for s in stocks if not s.get('is_etf') and s.get('chg') is not None]
    top_gainers = sorted(real_stocks, key=lambda s: s['chg'], reverse=True)[:5]
    top_losers = sorted(real_stocks, key=lambda s: s['chg'])[:5]

    # 綜合評分 TOP10
    scored = []
    for s in real_stocks:
        sc = compute_score(s)
        if sc is not None and sc > 0:
            scored.append({**s, 'score': sc})
    top_score = sorted(scored, key=lambda s: s['score'], reverse=True)[:10]

    # 大盤摘要（indices.json 的 indices 陣列，找台股加權 ^TWII）
    market_summary = None
    if indices_data and isinstance(indices_data.get('indices'), list):
        twii = next((i for i in indices_data['indices'] if i.get('yf') == '^TWII'), None)
        if twii:
            market_summary = {
                'name': twii.get('name'),
                'close': twii.get('close'),
                'chg_pct': twii.get('chg_pct'),
            }

    # 產業表現前 3 / 後 3
    ind_top, ind_bottom = [], []
    if industry_data and isinstance(industry_data.get('industry'), list):
        inds = sorted(industry_data['industry'], key=lambda i: (i.get('chg') if i.get('chg') is not None else 0), reverse=True)
        ind_top = inds[:3]
        ind_bottom = inds[-3:][::-1]

    digest = {
        'date': as_of,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'market': market_summary,
        'top_gainers': [{'sym': s['sym'], 'name': s.get('name'), 'chg': s['chg']} for s in top_gainers],
        'top_losers': [{'sym': s['sym'], 'name': s.get('name'), 'chg': s['chg']} for s in top_losers],
        'top_score': [{'sym': s['sym'], 'name': s.get('name'), 'score': s['score']} for s in top_score],
        'industry_top': [{'nm': i['nm'], 'chg': i.get('chg')} for i in ind_top],
        'industry_bottom': [{'nm': i['nm'], 'chg': i.get('chg')} for i in ind_bottom],
    }
    return digest


def save_digest(digest):
    os.makedirs(DIGEST_DIR, exist_ok=True)
    fname = digest['date'].replace('-', '') + '.json'
    path = os.path.join(DIGEST_DIR, fname)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(digest, f, ensure_ascii=False, indent=2)
    print(f'[build_digest] 已寫入 {path}')
    return path


def digest_to_text(d):
    lines = []
    if d.get('market'):
        m = d['market']
        chg = m.get('chg_pct')
        arrow = '📈' if (chg or 0) >= 0 else '📉'
        lines.append(f"{arrow} {m.get('name','大盤')} {m.get('close','-')}（{'+' if (chg or 0) >= 0 else ''}{chg}%）")
    if d.get('top_gainers'):
        lines.append('漲幅前5：' + '、'.join(f"{s['sym']}{s.get('name','')} +{s['chg']}%" for s in d['top_gainers']))
    if d.get('top_losers'):
        lines.append('跌幅前5：' + '、'.join(f"{s['sym']}{s.get('name','')} {s['chg']}%" for s in d['top_losers']))
    if d.get('industry_top'):
        lines.append('產業領漲：' + '、'.join(f"{i['nm']} +{i.get('chg')}%" for i in d['industry_top']))
    if d.get('top_score'):
        lines.append('綜合評分TOP：' + '、'.join(f"{s['sym']}{s.get('name','')}({s['score']})" for s in d['top_score'][:5]))
    return '\n'.join(lines) if lines else '今日無足夠資料產生摘要。'


def build_rss():
    """從 data/digest/*.json 完整重新產生 rss.xml（保留最近 MAX_RSS_ITEMS 篇），避免增量編輯累積損毀風險"""
    files = sorted(glob.glob(os.path.join(DIGEST_DIR, '*.json')), reverse=True)
    files = [f for f in files if os.path.basename(f) != 'index.json'][:MAX_RSS_ITEMS]
    items = []
    for fp in files:
        with open(fp, encoding='utf-8') as f:
            d = json.load(f)
        title = f"mklab-stock 每日摘要 {d['date']}"
        desc = digest_to_text(d).replace('\n', ' / ')
        link = f"{SITE_URL}mklab-stock-digest.html?date={d['date'].replace('-', '')}"
        pub_date = datetime.fromisoformat(d['generated_at']).strftime('%a, %d %b %Y %H:%M:%S %z')
        items.append(f"""    <item>
      <title>{xml_escape(title)}</title>
      <link>{xml_escape(link)}</link>
      <guid isPermaLink="false">mklab-stock-digest-{d['date']}</guid>
      <pubDate>{pub_date}</pubDate>
      <description>{xml_escape(desc)}</description>
    </item>""")

    now_str = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S %z')
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>mklab-stock 每日市場摘要</title>
    <link>{xml_escape(SITE_URL)}</link>
    <description>台股每日收盤摘要：大盤、漲跌幅前5大、產業動態、綜合評分 TOP10（僅供研究參考，非投資建議）</description>
    <language>zh-tw</language>
    <lastBuildDate>{now_str}</lastBuildDate>
{chr(10).join(items)}
  </channel>
</rss>
"""
    with open(RSS_PATH, 'w', encoding='utf-8') as f:
        f.write(rss)
    print(f'[build_digest] 已寫入 {RSS_PATH}（{len(items)} 篇）')


def build_index():
    """靜態站無法列目錄，維護一個 index.json 讓前端知道有哪些摘要日期可讀；
    同時刪除超出保留範圍的舊檔案，避免 digest/ 資料夾隨時間無限增長（孤兒檔案永遠不會被前端讀到）。"""
    files = sorted(glob.glob(os.path.join(DIGEST_DIR, '*.json')))
    all_dates = sorted({os.path.basename(f)[:-5] for f in files if os.path.basename(f) != 'index.json'}, reverse=True)
    dates = all_dates[:60]
    dropped = set(all_dates) - set(dates)
    for d in dropped:
        try:
            os.remove(os.path.join(DIGEST_DIR, d + '.json'))
        except OSError:
            pass
    if dropped:
        print(f'[build_digest] 已清除 {len(dropped)} 個超出保留範圍（60 筆）的舊摘要檔案')
    index_path = os.path.join(DIGEST_DIR, 'index.json')
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump({'dates': dates}, f, ensure_ascii=False, indent=2)
    print(f'[build_digest] 已更新索引 {index_path}（{len(dates)} 筆）')


def main():
    digest = build_digest()
    save_digest(digest)
    build_index()
    build_rss()


if __name__ == '__main__':
    main()
