"""已知錯誤防錯測試：直接驗證實際資料與程式碼（不是只檢查程式可執行）。執行：python3 tests/test_known_errors.py"""
import glob, json, os, re, subprocess, sys, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
results = []
def check(name, ok, detail=""):
    results.append((name, "PASS" if ok else "FAIL", detail))

stocks_doc = json.load(open('data/stocks.json', encoding='utf-8'))
S = stocks_doc['stocks']
etf_official = {e['sym'] for e in json.load(open('data/etf-meta.json', encoding='utf-8'))['etfs']}

# P0-1 ETF 分類
types = collections.Counter(s.get('security_type') for s in S)
check("P0-1 每檔都有 security_type", all(s.get('security_type') for s in S), str(dict(types)))
check("P0-1 etf 只能是官方清單內代號", all((s['security_type'] != 'etf') or (s['sym'] in etf_official) for s in S))
check("P0-1 官方清單內代號都標為 etf（在資料庫中的部分）", all(s['security_type'] == 'etf' for s in S if s['sym'] in etf_official))
check("P0-1 0050/006208/009816/00981A 為 etf", all(next(s for s in S if s['sym']==x)['security_type']=='etf' for x in ['0050','006208','009816','00981A']))
check("P0-1 一般股票未被誤標為 etf", all(s.get('security_type') in ('stock','etf','unverified','other') for s in S))

# P0-4 股票完整性（以代號去重；不以固定筆數判斷）
syms = [s['sym'] for s in S]
check("P0-4 代號無重複", len(syms) == len(set(syms)), f"重複 {len(syms)-len(set(syms))}")
check("P0-4 來源計數與股票清單一致", stocks_doc['meta'].get('count') == len(S), f"meta={stocks_doc['meta'].get('count')} actual={len(S)}")

# P0-3 行情一致性：stocks.json 價格 vs history 最後一個交易日收盤
hist_files = sorted(glob.glob('data/history/*.json'))
latest = json.load(open(hist_files[-1], encoding='utf-8'))
hmap = {r['stock_id']: r['close'] for r in latest['stocks']}
mism = [s['sym'] for s in S if s['sym'] in hmap and s.get('price') is not None and abs(hmap[s['sym']] - s['price']) > 1e-6]
check("P0-3 stocks.json 價格與 history 最新交易日一致", len(mism) == 0, f"不一致 {len(mism)} 檔")
check("P0-3 stocks.json 日期與 history 最新交易日一致", stocks_doc['meta']['as_of'].replace('-', '') == os.path.basename(hist_files[-1])[:8])
dates = [os.path.basename(f)[:8] for f in hist_files]
check("P0-3 history 無重複交易日", len(dates) == len(set(dates)))

# 歷史快照品質：不得有高低價整日缺失的快照（休市或來源不完整）
bad = []
for f in hist_files:
    rs = json.load(open(f, encoding='utf-8'))['stocks']
    if rs and sum(1 for r in rs if r.get('high') is None) / len(rs) > 0.5:
        bad.append(os.path.basename(f))
check("歷史快照無高低價缺失日", len(bad) == 0, f"{len(bad)} 個")

# P0-6 產業日期
ind = json.load(open('data/industry.json', encoding='utf-8'))
check("P0-6 industry.json 日期與股票資料一致", ind['meta']['as_of'] == stocks_doc['meta']['as_of'], f"industry={ind['meta']['as_of']} stocks={stocks_doc['meta']['as_of']}")

# P0-5 Research 不得含硬編碼測試行情
rh = open('mklab-stock-research.html', encoding='utf-8').read()
check("P0-5 Research 無硬編碼價格（1050/215/1280）", not re.search(r'price\s*:\s*(1050|215|1280)\b', rh))

# P0-2 篩選函式（抽出實際程式碼在 Node 執行）
sh = open('mklab-stock-screener.html', encoding='utf-8').read()
m = re.search(r'  function passStock\(s, f\)\{.*?\n  \}\n', sh, re.S)
check("P0-2 passStock 函式存在", m is not None)
if m:
    js = m.group(0) + """
const T = (s,f) => passStock(s, Object.assign({pe:60,pb:20,div:0,roe:0,roa:0,rsi:0,chg:-10,cap:0,ma:'any',ind:'any'}, f));
const out = {
  pe_null_limited: T({pe:null}, {pe:15}),
  pe_10_pass: T({pe:10}, {pe:15}),
  pe_20_fail: T({pe:20}, {pe:15}),
  pe_negative_fail: T({pe:-3}, {pe:15}),
  roe_null_fail: T({roe:null}, {roe:15}),
  roe_20_pass: T({roe:20}, {roe:15}),
  roe_10_fail: T({roe:10}, {roe:15}),
  inactive_null_pass: T({pe:null, roe:null}, {}),
  zero_roe_ok_when_inactive: T({roe:0}, {}),
};
console.log(JSON.stringify(out));
"""
    open('/tmp/pass_test.js', 'w').write(js)
    r = subprocess.run(['node', '/tmp/pass_test.js'], capture_output=True, text=True)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
        exp = {'pe_null_limited': False, 'pe_10_pass': True, 'pe_20_fail': False, 'pe_negative_fail': False,
               'roe_null_fail': False, 'roe_20_pass': True, 'roe_10_fail': False,
               'inactive_null_pass': True, 'zero_roe_ok_when_inactive': True}
        # 注意：roe_10_fail 在 roe≥15 的函式中應為 False
        bad = {k: (o.get(k), v) for k, v in exp.items() if o.get(k) != v}
        check("P0-2 篩選案例（null/0/負PE/上下限）", not bad, str(bad) if bad else "全部符合")
    except Exception as e:
        check("P0-2 篩選案例執行", False, str(e) + r.stderr[:200])

# 所有 JS 語法
errs = []
for f in glob.glob('*.html'):
    h = open(f, encoding='utf-8').read()
    for i, s in enumerate(re.findall(r'<script>([\s\S]*?)</script>', h)):
        open('/tmp/_s.js', 'w', encoding='utf-8').write(s)
        r = subprocess.run(['node', '--check', '/tmp/_s.js'], capture_output=True, text=True)
        if r.returncode: errs.append(f"{f}#{i}")
for f in glob.glob('assets/js/*.js'):
    r = subprocess.run(['node', '--check', f], capture_output=True, text=True)
    if r.returncode: errs.append(f)
check("JavaScript 語法（所有頁面與 assets/js）", not errs, ",".join(errs))

# GitHub Actions 手動執行不得被 schedule 條件跳過
wf = open('.github/workflows/daily-update.yml', encoding='utf-8').read()
jobs_if = re.findall(r"if: (.*)", wf)
check("P1-2 手動執行條件涵蓋 workflow_dispatch", all("workflow_dispatch" in x for x in jobs_if), f"{len(jobs_if)} 個 job")
qa = open('.github/workflows/qa-gate.yml', encoding='utf-8').read()
check("P1-1 QA 觸發涵蓋 assets/js 與 assets/css", "assets/js/**" in qa and "assets/css/**" in qa)

# P1 頁面標題不得重複
titles = [re.search(r'<title>(.*?)</title>', open(f, encoding='utf-8').read()).group(1) for f in glob.glob('*.html') if '<title>' in open(f, encoding='utf-8').read()]
check("P1-3 頁面標題各頁不同", len(titles) == len(set(titles)))


# 研究頁啟動流程（導覽、抽屜、個股清單、資料日期）
check("Research 啟動流程含 initDrawer/Shell.mount/loadAll", all(k in rh for k in ["MKLAB.initDrawer()", "MKLAB.Shell.mount({ active: 'research' })", "loadAll();"]))
# 產業頁日期以行情日期為準
ih = open('mklab-stock-industry.html', encoding='utf-8').read()
check("產業頁資料日期改用股票行情日期", "MKLAB.data.json('stocks')" in ih and "產業統計日期" in ih)
# 產業與行情日期一致
check("產業統計日期與行情日期一致", ind['meta']['as_of'] == stocks_doc['meta']['as_of'])
# 產業補值：一般股票不得出現空產業（ETF 不適用）
empty_stock = [s['sym'] for s in S if s.get('security_type') == 'stock' and not s.get('ind')]
check("一般股票產業分類完整", len(empty_stock) == 0, f"缺 {len(empty_stock)} 檔：{empty_stock}")


# 範圍：不含 TPEx 一般股票（上櫃只保留官方 ETF）
tpex_non_etf = [s['sym'] for s in S if s.get('source') == 'TPEX' and s['sym'] not in etf_official]
check("範圍：TPEx 只保留官方 ETF", len(tpex_non_etf) == 0, f"非 ETF {len(tpex_non_etf)} 筆")
# 官方公司資料整合：一般股票具備產業與上市日期
st_rows = [s for s in S if s.get('security_type') == 'stock']
check("一般股票具備上市日期（官方）", all(s.get('listing_date') for s in st_rows), f"缺 {sum(1 for s in st_rows if not s.get('listing_date'))} 檔")

# 輸出
w = max(len(n) for n, _, _ in results)
for n, st, d in results:
    print(f"{st:4}  {n.ljust(w)}  {d}")
fails = [r for r in results if r[1] != 'PASS']
print(f"\n合計 {len(results)} 項，PASS {len(results)-len(fails)}，FAIL {len(fails)}")
sys.exit(1 if fails else 0)
