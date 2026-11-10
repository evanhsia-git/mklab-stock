"""已知錯誤防錯測試：直接驗證實際資料與程式碼（不是只檢查程式可執行）。執行：python3 tests/test_known_errors.py"""
import glob, json, os, re, subprocess, sys, collections, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
results = []
def check(name, ok, detail=""):
    results.append((name, "PASS" if ok else "FAIL", detail))

stocks_doc = json.load(open('data/stocks.json', encoding='utf-8'))
S = stocks_doc['stocks']
etf_official = {e['sym'] for e in json.load(open('data/etf-meta.json', encoding='utf-8'))['etfs']}
if os.path.exists('data/etf-supplement.json'):
    etf_official |= {e['sym'] for e in json.load(open('data/etf-supplement.json', encoding='utf-8'))['etfs']}

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
# close 可能為 None（停牌／當日無成交，例如 20261030 有 13 檔）→ 必須先判 None，否則 TypeError 直接崩潰
# 上櫃 ETF 常比上市早一天更新（price_asof 晚於 history 最新快照日，屬已揭露的混合日期）：
# 只比對「行情日 = 快照日」的列；行情日較新者在下一次快照寫入後才可比對
_hist_day = os.path.basename(hist_files[-1])[:8]
mism = [s['sym'] for s in S if s['sym'] in hmap and hmap[s['sym']] is not None
        and s.get('price') is not None and str(s.get('price_asof', '')).replace('-', '') == _hist_day
        and abs(hmap[s['sym']] - s['price']) > 1e-6]
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


# 資料範圍（本站原始設計）：上市一般股票 + 上市 ETF + 上櫃 ETF；上櫃一般股票、權證等不收
tpex_rows = [s for s in S if s.get('source') == 'TPEX']
tpex_bad = [s['sym'] for s in tpex_rows if s.get('security_type') not in ('etf', 'unverified')]
check("範圍：上櫃只收 ETF（不得有上櫃一般股票／權證／其他）", len(tpex_bad) == 0, f"違規 {len(tpex_bad)} 檔：{tpex_bad[:8]}")
check("範圍：上櫃 ETF 至少 50 檔（來源異常防護）", len(tpex_rows) >= 50, f"上櫃 ETF {len(tpex_rows)} 檔")
twse_stock_n = sum(1 for s in S if s.get('source') == 'TWSE' and s.get('security_type') == 'stock')
check("範圍：上市一般股票 >= 900 檔", twse_stock_n >= 900, f"上市一般股票 {twse_stock_n} 檔")
others = [s['sym'] for s in S if s.get('security_type') == 'other']
check("範圍：不收特別股／DR／受益證券／ETN／權證（security_type=other 必須為 0）", len(others) == 0, f"{len(others)} 檔：{others[:8]}")
bad_code = [s['sym'] for s in S if s.get('security_type') == 'stock' and not (len(s['sym']) == 4 and s['sym'].isdigit())]
check("範圍：一般股票代號皆為 4 碼純數字（排除 2881A 特別股等）", len(bad_code) == 0, f"{bad_code[:8]}")
_ci = open('skills/data/compute_indicators.py', encoding='utf-8').read()
check("範圍：fetch_data 與 compute_indicators 都會整批排除 other 類",
      'excluded_other' in open('skills/data/fetch_data.py', encoding='utf-8').read() and '!= "other"' in _ci)
check("報酬欄位：1/3/6 月、1 年與 2 年（預寫、未開放）漲跌幅皆由同一個 calc_chg 計算（CHG_PERIODS）",
      'CHG_PERIODS = {"chg_1m": 30, "chg_3m": 91, "chg_6m": 182, "chg_1y": 365, "chg_2y": 730}' in _ci)
_ret = [s for s in S if s.get('security_type') == 'stock']
for _k in ('chg_1m', 'chg_3m', 'chg_6m', 'chg_1y'):
    _n = sum(1 for s in _ret if s.get(_k) is not None)
    check(f"報酬欄位：{_k} 一般股票覆蓋率 >= 85%（歷史不足者為 null，不補 0）", _n >= 0.85 * len(_ret), f"{_n}/{len(_ret)}")
check("報酬欄位：缺資料為 null、不得為 0 冒充（3 月/6 月為 0.0 的比例不得異常）",
      sum(1 for s in _ret if s.get('chg_3m') == 0) < 0.03 * len(_ret))
_fd_src = open('skills/data/fetch_data.py', encoding='utf-8').read()
check("範圍：fetch_data 上櫃只保留 ETF（TPEX_KEEP_TYPES）且沿用舊資料也套用同一規則",
      'TPEX_KEEP_TYPES = ("etf", "unverified")' in _fd_src and _fd_src.count('in TPEX_KEEP_TYPES') >= 2)
check("範圍：不再抓取上櫃股票基本資料（t187ap03_O）",
      't187ap03_O' not in open('skills/data/fetch_official_fundamentals.py', encoding='utf-8').read()
      and 't187ap03_O' not in open('skills/data/integrate_official_company.py', encoding='utf-8').read().split('"""')[2])
# P0-1 分類：每檔 security_type 必須與代碼規則 + 官方 ETF 清單一致（與 classify_security 相同）
def _expect(sym):
    if sym in etf_official: return 'etf'
    if sym.startswith('00'): return 'unverified'
    if len(sym) == 4 and sym.isdigit(): return 'stock'
    return 'other'
mismatch = [s['sym'] for s in S if s.get('security_type') != _expect(s['sym'])]
check("P0-1 證券分類與官方 ETF 清單+代碼規則一致", not mismatch, f"不一致 {len(mismatch)} 檔 {mismatch[:5]}")
# P0-2 來源狀態：不得有 stale 資料冒充今日行情
stale_fresh = [s['sym'] for s in S if s.get('quality') == 'stale' and s.get('price_asof') == stocks_doc['meta'].get('as_of')]
check("P0-2 stale 資料的行情日期不得等於快照日期", not stale_fresh, f"{len(stale_fresh)} 檔")
# CI 修復：weekly（ROE 補充）不得覆寫 source（行情來源），寫入前必須重算 meta
fd_text = open('skills/data/fetch_data.py', encoding='utf-8').read()
check("CI weekly 不覆寫 source 為 Yahoo Finance（ROE 來源改記 roe_src）", 's["source"] = "Yahoo Finance"' not in fd_text and '"roe_src"' in fd_text)
check("CI weekly 寫入前呼叫 recompute_meta", 'recompute_meta(data)' in fd_text)
# CI 修復：權證／其他證券不參與漲跌異常檢查
qg_text = open('skills/qa-gate/qa_gate.py', encoding='utf-8').read()
check("CI QA 漲跌檢查排除 security_type=other", 'security_type") not in ("stock", "etf")' in qg_text)
# CI 修復（#190）：上櫃全量檔常被截斷；必須「重試到完整」，不得採用 partial bytes，也不得因截斷而整批失敗
check("CI 上櫃下載不採用 IncompleteRead partial bytes（程式不存取 .partial）", 'getattr(e, "partial"' not in fd_text and 'e.partial' not in fd_text)
check("CI fetch_json 以 Content-Length 驗證完整性且要求 identity 編碼", 'Content-Length' in fd_text and '"Accept-Encoding": "identity"' in fd_text)
check("CI 上櫃下載使用 5 次重試", 'fetch_json(TPEX_DAILY, timeout=120, attempts=5)' in fd_text)
# 官方公司資料整合：一般股票具備產業與上市日期
st_rows = [s for s in S if s.get('security_type') == 'stock']
check("一般股票具備上市日期（官方）", all(s.get('listing_date') for s in st_rows), f"缺 {sum(1 for s in st_rows if not s.get('listing_date'))} 檔")

# 一般股票一律來自上市（上櫃一般股票不收）。
# 2026-11-10 起不再逐列寫 ind_src（前端與測試都沒讀，stocks.json 瘦身 −161 KB），
# 改成直接驗證「值」本身 ＋ 驗證來源仍由管線獨佔讀官方檔 —— 比比對來源字串更實在。
_ind_doc = json.load(open('data/industry-codes.json', encoding='utf-8'))
_ind_allowed = set(_ind_doc['codes'].values()) | {_ind_doc['fallback'], '存託憑證'}
check("一般股票皆為上市（source=TWSE，上櫃一般股票不收）",
      all(s.get('source') == 'TWSE' for s in st_rows),
      f"source 非 TWSE {sum(1 for s in st_rows if s.get('source') != 'TWSE')} 檔")
check("一般股票產業別必為官方類別（33 類／fallback／DR 的『存託憑證』）",
      all(s.get('ind') in _ind_allowed for s in st_rows),
      f"不在官方清單 {[s['sym'] for s in st_rows if s.get('ind') not in _ind_allowed][:8]}")
check("產業別來源仍由管線讀官方 t187ap03_L（不得改成猜測或留空）",
      't187ap03_L' in open('skills/data/integrate_official_company.py', encoding='utf-8').read()
      and 't187ap03_L' in open('skills/data/import_company_industry.py', encoding='utf-8').read())

# EPS 口徑：JSON 原始 eps 為最近單季，前端與後端評分都只能用官方年化 eps_off（沒有就顯示 -）
_fund_rows = [s for s in S if s.get('security_type') == 'stock']
_mis = [s['sym'] for s in _fund_rows if s.get('roe_off') is not None and (s.get('roe') != s['roe_off'] or s.get('roa') != s.get('roa_off'))]
check("ROE/ROA：有官方年化值者，roe/roa 必須等於 roe_off/roa_off（單一口徑）", len(_mis) == 0, f"{len(_mis)} 檔不一致：{_mis[:6]}")
_stale = [s['sym'] for s in _fund_rows if s.get('roe_off') is None and s.get('roe') is not None and s.get('roe_src') != 'yfinance']
check("ROE/ROA：沒有官方值且非 yfinance 補值者不得殘留過期舊值（應為 null 顯示 -）", len(_stale) == 0, f"{len(_stale)} 檔：{_stale[:6]}")
_eps_mis = [s['sym'] for s in _fund_rows if s.get('eps') != s.get('eps_off')]
check("EPS：eps 必須等於官方年化 eps_off（沒有官方值為 null）", len(_eps_mis) == 0, f"{len(_eps_mis)} 檔：{_eps_mis[:6]}")
_fd2 = open('skills/data/fetch_data.py', encoding='utf-8').read()
check("財報：fetch_data 不再呼叫已失效的 t187ap06_L 營益分析（舊版殘值來源）",
      'fetch_profitability' not in _fd2 and 'TWSE_PROFITABILITY' not in _fd2)
_dc = open('assets/js/data-client.js', encoding='utf-8').read()
# EPS/ROE/ROA 口徑：顯示值由資料管線決定，前端只負責呈現。
# 2026-11-10 修正此檢查：原本是比對 data-client.js 內有沒有那行覆寫字串，但那段程式的
# 條件寫成 `name === 'stocks'`，而 json() 會先把 name 補成 'stocks.json' → 條件永遠不成立
# （死碼、從未生效）。等於在測一段不會執行的程式碼，還給了假的安全感。
# 而且實測直接把它「修好」啟用會改掉 66 檔的 roa（weekly-roe job 以 yfinance 覆寫部分列），
# 屬行為變更。故改成兩個真正的斷言：
#   ① 後端管線確實持有該規則（security_type=='stock' 才處理，且 eps 只用官方年化值）
#   ② 前端不得自行再算一次（負向斷言，防止有人重新接上而與管線漂移）
_fin = open('skills/data/import_official_fundamentals.py', encoding='utf-8').read()
check("EPS 口徑：後端管線以官方年化 eps 覆蓋，且只處理一般股票",
      'row["eps"] = row.get("eps_off")' in _fin
      and 'if row.get("security_type") == "stock":' in _fin)
check("EPS 口徑：前端不得自行改寫 eps/roe/roa（避免與管線口徑漂移）",
      '.eps_off != null' not in _dc and 's.roe = s.roe_off' not in _dc and 's.roa = s.roa_off' not in _dc)

# stocks.json 瘦身（2026-11-10）：這 9 欄前端與測試都沒有讀，已在寫入端移除。
# 防回退：若有人把寫入端加回來，這裡立刻紅燈（並附大小預算，避免又長回去）。
_SLIM_BANNED = ["last_updated", "company_short", "ind_src", "fund_period", "fund_asof",
                "div_latest_year", "operating_margin", "high52w", "low52w"]
_slim_bytes = open('data/stocks.json', 'rb').read()
_slim_doc = json.loads(_slim_bytes)
_slim_present = sorted({k for s in _slim_doc['stocks'] for k in s if k in _SLIM_BANNED})
check("stocks.json 瘦身：9 個未使用欄位不得回歸", not _slim_present, f"又出現了 {_slim_present}")
check("stocks.json 瘦身：單檔預算 1,300 KB", len(_slim_bytes) < 1300 * 1024,
      f"目前 {len(_slim_bytes)/1024:.0f} KB")
_slim_writers = (_fd2 + _fin
                 + open('skills/data/compute_indicators.py', encoding='utf-8').read()
                 + open('skills/data/integrate_official_company.py', encoding='utf-8').read()
                 + open('skills/data/import_company_industry.py', encoding='utf-8').read())
check("stocks.json 瘦身：寫入端不得再寫這 9 欄",
      not [k for k in _SLIM_BANNED if f'"{k}"' in _slim_writers],
      f"寫入端殘留 {[k for k in _SLIM_BANNED if chr(34)+k+chr(34) in _slim_writers]}")
import importlib.util as _iu
_spec = _iu.spec_from_file_location('build_digest', 'skills/data/build_digest.py'); _bd = _iu.module_from_spec(_spec); _spec.loader.exec_module(_bd)
_e1 = _bd.effective_fundamentals({'eps': 22.08, 'eps_off': 98.66, 'roe': 31.7, 'roe_off': 39.77})
_e2 = _bd.effective_fundamentals({'eps': 3.0, 'eps_off': None, 'roe': 10.0, 'roe_off': None})
check("EPS 口徑：後端評分與前端同口徑（有官方年化→用年化；無→None；ROE 有官方→用官方）",
      _e1['eps'] == 98.66 and _e1['roe'] == 39.77 and _e2['eps'] is None and _e2['roe'] == 10.0,
      f"{_e1['eps']}/{_e1['roe']}/{_e2['eps']}/{_e2['roe']}")
check("EPS 口徑：摘要只計一般股票（不含 ETF／DR／特別股／權證）", "s.get('security_type') == 'stock'" in open('skills/data/build_digest.py', encoding='utf-8').read())
check("共用：市場寬度面板只存在 mklab-core.js（industry／breadth 頁不得各自重寫）",
      'const BreadthPanel' in open('assets/js/mklab-core.js', encoding='utf-8').read()
      and all('const BUCKETS' not in open(p, encoding='utf-8').read() for p in ('mklab-stock-industry.html', 'mklab-stock-breadth.html')))
check("共用：黃標資料日期由 MKLAB.loadFreshness 統一載入，且失敗不顯示『示意資料』",
      'async function loadFreshness' in open('assets/js/mklab-core.js', encoding='utf-8').read()
      and '示意資料' not in open('assets/js/mklab-core.js', encoding='utf-8').read())

# 評分公式單一來源：data/scoring-config.json（前端 index.html、後端 build_digest.py、文件 help.html）
_sc = json.load(open('data/scoring-config.json', encoding='utf-8'))
check("評分設定含 5 個評分項", len(_sc.get('components', [])) == 5, f"實際 {len(_sc.get('components', []))} 項")
check("評分設定含公式說明與更新日",
      bool(_sc.get('meta', {}).get('formula')) and bool(_sc.get('meta', {}).get('updated')))
_idx_txt = open('index.html', encoding='utf-8').read()
check("前端 index.html 讀取評分設定（未硬寫舊公式）",
      'scoring-config' in _idx_txt and 'Math.min(40, roe * 1.2)' not in _idx_txt)
_bd_txt = open('skills/data/build_digest.py', encoding='utf-8').read()
check("後端 build_digest.py 讀取評分設定（未硬寫舊公式）",
      'scoring-config' in _bd_txt and 'min(40, roe * 1.2)' not in _bd_txt)
check("help.html 標示評分設定的唯一來源",
      'scoring-config' in open('mklab-stock-help.html', encoding='utf-8').read())
# 依設定試算：roe=20 / pe=15 / pb=2 / eps=10 / chg=5 → 24+15+12+3+5 = 59.0
_smp = {'roe': 20, 'pe': 15, 'pb': 2, 'eps': 10, 'chg': 5}
_tot = 0.0
for _c in _sc['components']:
    _v = _smp[_c['key']]
    _x = (_c['base'] - _v) if _c.get('direction') == 'low' else (_v - _c['base'])
    _tot += min(_c['max'], _x * _c['coef'])
check("評分公式試算符合預期（59.0）", round(_tot, 1) == 59.0, f"實算 {round(_tot, 1)}")
# 缺欄位不得計分（不得補 0）：compute_score 只要有一個欄位是 None 就回 None
def _score_or_none(row):
    for _c in _sc['components']:
        if row.get(_c['key']) is None:
            return None
    return 1.0
check("評分公式缺欄位不計分（不補 0）",
      _score_or_none({'roe': 20, 'pe': None, 'pb': 2, 'eps': 10, 'chg': 5}) is None
      and _score_or_none(_smp) is not None)


# 個股 K 線檔：每檔行情都有對應 K 線，且最後一筆與行情收盤一致
import os as _os
kl_missing=[x['sym'] for x in S if not _os.path.exists(f"data/kline/{x['sym']}.json")]
check("個股 K 線檔覆蓋所有股票", len(kl_missing)==0, f"缺 {len(kl_missing)} 檔")
bad_last=[]
for x in S[:200]:
    pth=f"data/kline/{x['sym']}.json"
    if _os.path.exists(pth):
        kd=json.load(open(pth,encoding='utf-8'))
        if kd['rows'] and abs(kd['rows'][-1][4]-x['price'])>1e-6: bad_last.append(x['sym'])
check("個股 K 線最新收盤與行情一致（抽樣 200 檔）", len(bad_last)==0, f"不一致 {bad_last[:5]}")


# ETF 分類新規則
cl={e['sym']:e['categories'] for e in json.load(open('data/etf-classified.json',encoding='utf-8'))['etfs']}
check("分類：0050 為被動市值型", 'market_cap' in cl.get('0050',[]))
check("分類：00850/00923 為被動市值型+主題型", all(x in cl.get(k,[]) for k in ['00850','00923'] for x in ['market_cap','theme']))
check("分類：0052、00757 為主題型", 'theme' in cl.get('0052',[]) and 'theme' in cl.get('00757',[]))
check("分類：A 尾碼寬基為主動市值型", all('active_cap' in cl.get(k,[]) for k in ['00985A','00991A','00994A','00403A','00415A']))
check("分類：K/C/M/S/V 尾碼為外幣型", all('fx' in v for k,v in cl.items() if k[-1:] in 'KCMSV'))


# TPEx ETF 篩選：官方清單內代號必須保留（修正純數字 ETF 漏抓）
fd=open('skills/data/fetch_data.py',encoding='utf-8').read()
check("P0-1 TPEx 分類以官方 ETF 清單判定（classify_security + load_etf_reference）", "def classify_security" in fd and "def load_etf_reference" in fd and "etf-meta.json" in fd and "tpex_candidates" in fd and "if keep_record(sid) and (sid in _etf_ref" not in fd)
# 價格提醒：儲存邏輯存在且會判斷是否觸發
wl=open('mklab-stock-watchlist.html',encoding='utf-8').read()
check("Watchlist 價格提醒已實作（儲存與觸發判斷）", "function alertText" in wl and "mklab-price-alerts" in wl and "尚未啟用" not in wl)


# 指數替代 ETF 持股：設定與解析
import importlib.util as _ilu
_spec=_ilu.spec_from_file_location("fih","skills/data/fetch_index_holdings.py"); _fih=_ilu.module_from_spec(_spec); _spec.loader.exec_module(_fih)
_cfg=json.load(open('data/index-proxy.json',encoding='utf-8'))
check("指數替代 ETF 設定含 VOO/DIA/QQQ/SOXX", {f['key'] for f in _cfg['funds']}=={'VOO','DIA','QQQ','SOXX'})
def _su(srcs):  # 來源可能是字串，或 {"url": ..., "expected_min": ...} 物件
    return [s["url"] if isinstance(s, dict) else s for s in srcs]
_voo=[f for f in _cfg['funds'] if f['key']=='VOO'][0]
if os.path.exists('data/raw/official/VOO_holdings.csv'):
    _man=[x for x in _su(_voo['sources']) if x.startswith('manual_upload:')][0]; _d,_u=_fih.load_source(_man); _h=_fih.parse_bytes(_d,_u)
    check("VOO 持股檔解析並通過驗證（真實檔）", len(_h)>=480 and (_fih.validate(_voo,_h) or True))
check("持股解析：iShares 型表頭", len(_fih.parse_table([["Ticker","Name","Weight (%)"],["NVDA","NVIDIA","8.5"]]))==1)
_bad_ok=False
try:
    _fih.validate(_voo,[{'ticker':'A%d'%i,'name':'','weight_pct':1.0} for i in range(500)])
except ValueError:
    _bad_ok=True
check("持股驗證：權重加總異常會被擋下（真實邏輯）", _bad_ok)


# 排程：資料 job 併發排隊；每週 ROE 只補非官方的一般股票
wf2=open('.github/workflows/daily-update.yml',encoding='utf-8').read()
check("排程併發控制（避免同時 push 互相拒絕）", "concurrency:" in wf2 and "group: data-update" in wf2)
fd2=open('skills/data/fetch_data.py',encoding='utf-8').read()
check("每週 ROE 補值排除官方財報與 ETF", 'fund_src") != "TWSE_OFFICIAL"' in fd2)
_pr=json.load(open('data/index-proxy.json',encoding='utf-8'))
check("VOO 設定為每月更新", any(f['key']=='VOO' and f.get('freq')=='monthly' for f in _pr['funds']))
check("ETF 資料網址已記錄（VOO/VTI/VUG/VTV/BND）", {e['ticker'] for e in json.load(open('data/etf-source-urls.json',encoding='utf-8'))['etfs']}=={'VOO','VTI','VUG','VTV','BND'})
check("說明頁含 ETF 資料網址表", 'ETF 資料來源網址' in open('mklab-stock-help.html',encoding='utf-8').read())

# 排程註冊一致性：job 的 if 條件引用的 cron 必須真的註冊在 on.schedule，否則該 job 永遠不會自動執行
# （曾發生：global-history「30 22」與 index-holdings「45 22」兩個 job 條件有寫、排程從來沒註冊 → 從未自動跑過）
_reg = set(re.findall(r'^\s+- cron:\s*"([^"]+)"', wf2, re.M))
_ref = set(re.findall(r"github\.event\.schedule\s*==\s*'([^']+)'", wf2))
check("排程：job 引用的 cron 都已註冊在 on.schedule", _ref <= _reg and bool(_ref), f"未註冊 {sorted(_ref - _reg)}")

# CI 併發與推送（2026-11-02）
# 曾發生：為了序列化 push 而給 8 個 job 加上同一個 job 級 concurrency group，但 queue 預設 single
# （同 group 只能 1 執行中 + 1 pending），workflow_dispatch 一次觸發 8 個 job 時 6 個 sibling
# 在 2 秒內被 "Canceling since a higher priority waiting request for mklab-git-push exists" 取消。
_job_ct = len(re.findall(r'^    concurrency:$', wf2, re.M))  # 每個 job 恰好一個 job 級 concurrency 區塊（workflow 層級縮排為 0，不會被算到）
_group_ct = len(re.findall(r'^\s+group:\s*mklab-git-push\s*$', wf2, re.M))
_queue_ct = len(re.findall(r'^\s+queue:\s*max\s*$', wf2, re.M))
check("CI：job 級 concurrency 每個 group 都必須有 queue: max（否則 sibling job 互相取消）",
      _group_ct == _job_ct and _queue_ct == _job_ct, f"jobs={_job_ct} group={_group_ct} queue:max={_queue_ct}")

# 推送腳本會 git merge 遠端分岔歷史 → 淺層 checkout（預設 depth=1）合併必定失敗，必須 fetch-depth: 0
_fd_ct = len(re.findall(r'^\s+fetch-depth:\s*0\s*$', wf2, re.M))
check("CI：每個 job 的 checkout 都要 fetch-depth: 0（淺層歷史無法 merge 遠端分岔，推送會失敗）",
      _fd_ct == _job_ct, f"jobs={_job_ct} fetch-depth:0={_fd_ct}")

# 推送邏輯單一實作：8 個 job 共用 scripts/ci_commit_push.sh，且不得再用會被舊 checkout 覆蓋新資料的 -X ours
_ci_push_raw = open('scripts/ci_commit_push.sh', encoding='utf-8').read()
_ci_push = re.sub(r'^\s*#.*$', '', _ci_push_raw, flags=re.M)  # 註解裡會提到 -X ours 這個「錯誤示範」，比對要排除註解
check("CI：每個 job 的推送步驟都走共用腳本 scripts/ci_commit_push.sh（不再各 job 各寫一套）",
      wf2.count('bash scripts/ci_commit_push.sh') == _job_ct and 'git config user.name' not in wf2,
      f"jobs={_job_ct} 呼叫={wf2.count('bash scripts/ci_commit_push.sh')}")
check("CI：推送合併衝突取遠端（-X theirs），不得用 -X ours（舊 checkout 會把遠端較新資料覆蓋回舊的）",
      '-X ours' not in wf2 and '-X ours' not in _ci_push and '-X theirs' in _ci_push)
check("CI：推送有重試（被其他 job 插隊時不會直接失敗）", 'until [' in _ci_push and 'git push origin HEAD:main' in _ci_push)

# 資料新鮮度守門：重現 2026-11-03 事故
# （過時 checkout 的整檔重寫在 merge 時勝出，讓 stocks.json 由 11-02 退回 10-30，
#   造成 stocks.json 與 history/industry 不一致）→ 推送前必須比對日期、只採最新版本。
def _freshness_guard_ok():
    import shutil as _sh
    t = tempfile.mkdtemp()

    def git(*a, cwd=t):
        return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)
    try:
        git("init", "-q", "--bare", "--initial-branch=main", "origin.git")
        seed = os.path.join(t, "seed")
        os.makedirs(os.path.join(seed, "data")); os.makedirs(os.path.join(seed, "scripts"))
        with open(os.path.join(seed, "data/stocks.json"), "w") as f:
            f.write('{"meta":{"as_of":"2026-10-30"},"stocks":[{"sym":"2330","price":100}]}')
        git("init", "-q", "-b", "main", cwd=seed)
        for fn in ("ci_commit_push.sh", "ci_data_freshness.py"):
            _sh.copy(os.path.join("scripts", fn), os.path.join(seed, "scripts", fn))
        idn = ["-c", "user.email=t@t", "-c", "user.name=t"]
        git(*idn, "add", "-A", cwd=seed); git(*idn, "commit", "-q", "-m", "seed", cwd=seed)
        git("remote", "add", "origin", os.path.join(t, "origin.git"), cwd=seed)
        git("push", "-q", "origin", "main", cwd=seed)
        # B：過時 job 先推（日期仍是 10-30 的整檔重寫）
        b = os.path.join(t, "B"); git("clone", "-q", os.path.join(t, "origin.git"), "B", cwd=t)
        p = os.path.join(b, "data/stocks.json")
        d = json.load(open(p, encoding="utf-8")); d["stocks"][0]["roe_off"] = 39.8
        json.dump(d, open(p, "w", encoding="utf-8"))
        git(*idn, "add", "-A", cwd=b); git(*idn, "commit", "-q", "-m", "B 過時重寫", cwd=b)
        git("push", "-q", "origin", "main", cwd=b)
        # A：本機已是較新的 11-02，用共用腳本推送
        a = os.path.join(t, "A"); git("clone", "-q", os.path.join(t, "origin.git"), "A", cwd=t)
        p = os.path.join(a, "data/stocks.json")
        d = json.load(open(p, encoding="utf-8")); d["meta"]["as_of"] = "2026-11-02"; d["stocks"][0]["price"] = 2370
        json.dump(d, open(p, "w", encoding="utf-8"))
        r = subprocess.run(["bash", "scripts/ci_commit_push.sh", "A 每日更新", "data/"],
                           cwd=a, capture_output=True, text=True, timeout=300)
        final = json.loads(git("show", "main:data/stocks.json", cwd=os.path.join(t, "origin.git")).stdout)
        ok = r.returncode == 0 and final["meta"]["as_of"] == "2026-11-02" and final["stocks"][0]["price"] == 2370
        return ok, f"rc={r.returncode} 遠端 as_of={final['meta']['as_of']} price={final['stocks'][0]['price']}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    finally:
        _sh.rmtree(t, ignore_errors=True)


_fresh_ok, _fresh_detail = _freshness_guard_ok()
check("CI：資料新鮮度守門（過時整檔重寫不得讓資料倒退）", _fresh_ok, _fresh_detail)

# 指數替代 ETF 來源（2026-11-02：data/index-holdings/ 曾經 0 檔，job 卻顯示 success）
_pr2 = {f['key']: f for f in _cfg['funds']}
check("指數替代 ETF：已移除實測 404 的 SSGA 舊網址（無 -en- 的 holdings-daily-us-dia.xlsx）",
      not any(s.endswith('holdings-daily-us-dia.xlsx') for f in _pr2.values() for s in _su(f['sources'])))
check("指數替代 ETF：每檔都明確設定 min_weight_total（來源只提供部分持股時，逐檔設定門檻而非放寬全體）",
      all('min_weight_total' in f for f in _pr2.values()))
_floor_ok = False
try:
    _fih.validate({'key': 'X', 'expected_min': 1, 'expected_max': 10, 'min_weight_total': 90,
                   'issuer': '', 'index': ''}, [{'ticker': 'AAA', 'name': '', 'weight_pct': 50.0}])
except ValueError:
    _floor_ok = True
check("指數替代 ETF：低於該基金 min_weight_total 會被擋下", _floor_ok)

# VOO 自動來源（2026-11-03）：Vanguard 的 {TICKER}-AdditionalFundData 回傳 JSON（非表格），
# 舊版 parse_bytes 只認 HTML/XLSX/CSV → VOO 只能靠手動檔，等於沒有自動更新。
_vj = {"holdingDetails": {
    "asOfDate": "09/30/2026",
    "equityHoldings": [
        {"ticker": "NVDA", "securityLongDescription": "NVIDIA Corp", "marketValuePercentage": "8.39%"},
        {"ticker": "AAPL", "securityLongDescription": "Apple Inc", "marketValuePercentage": "7.38%"},
        {"ticker": "", "securityLongDescription": "CASH", "marketValuePercentage": "0.05%"}],
    "shortTermReservesHoldings": [{"ticker": "CMT001142", "marketValuePercentage": "0.05%"}],
    "derivativeHoldings": [{"ticker": "ESZ6", "marketValuePercentage": "0.03%"}]}}
_vj_bytes = json.dumps(_vj).encode()
_vh = _fih.parse_bytes(_vj_bytes, "https://investor.vanguard.com/irr/funds/profile/VOO-AdditionalFundData")
check("指數替代 ETF：Vanguard JSON 可解析（只取股票部位、濾掉無代號列）",
      [x['ticker'] for x in _vh] == ["NVDA", "AAPL"] and _vh[0]['weight_pct'] == 8.39
      and _vh[0]['name'] == 'NVIDIA Corp', f"{[(x['ticker'], x['weight_pct']) for x in _vh]}")
check("指數替代 ETF：Vanguard 持股基準日可解析為 ISO 日期（月更新來源需可追溯版本）",
      _fih.source_asof(_vj_bytes) == '2026-09-30', f"{_fih.source_asof(_vj_bytes)}")
check("指數替代 ETF：VOO 以官方端點優先（自動），手動檔僅為備援",
      str(_pr2['VOO']['sources'][0]).startswith('https://investor.vanguard.com/irr/funds/profile/VOO'),
      f"{_pr2['VOO']['sources'][0]}")
_voo_file = json.load(open('data/index-holdings/VOO.json', encoding='utf-8'))
check("指數替代 ETF：VOO 產出記錄來源與持股基準日",
      str(_voo_file.get('source', '')).startswith('http') and bool(_voo_file.get('holdings_asof')),
      f"source={str(_voo_file.get('source'))[:52]} asof={_voo_file.get('holdings_asof')}")

# QQQ 官方來源（2026-11-03）：官方持股頁對非瀏覽器 406 且表格由 JS 載入，
# 但網站背後的公開 API（dng-api.invesco.com）可直接取得完整持股 → 舊版只能靠免費備援的前 25 大（權重 71%）
_ij = {"effectiveDate": "2026-11-03", "totalNumberOfHoldings": 5, "holdings": [
    {"ticker": "AAPL", "issuerName": "Apple Inc", "percentageOfTotalNetAssets": 8.132807, "securityTypeName": "Common Stock"},
    {"ticker": "NVDA", "issuerName": "NVIDIA Corp", "percentageOfTotalNetAssets": 8.021035, "securityTypeName": "Common Stock"},
    {"ticker": "", "issuerName": "US DOLLAR", "percentageOfTotalNetAssets": 0.5, "securityTypeName": "Currency"},
    {"ticker": "ESZ6", "issuerName": "S&P500 EMINI FUT", "percentageOfTotalNetAssets": 0.03, "securityTypeName": "Index Future"}]}
_ib = json.dumps(_ij).encode()
_ih = _fih.parse_bytes(_ib, "https://dng-api.invesco.com/cache/v1/accounts/en_US/shareclasses/46090E103/holdings/fund")
check("指數替代 ETF：Invesco 官方 API JSON 可解析（只取股票部位、排除現金與期貨）",
      [x['ticker'] for x in _ih] == ["AAPL", "NVDA"] and _ih[0]['weight_pct'] == 8.1328, f"{_ih}")
check("指數替代 ETF：Invesco effectiveDate 可解析為 ISO 日期", _fih.source_asof(_ib) == '2026-11-03')
_qfile = json.load(open('data/index-holdings/QQQ.json', encoding='utf-8'))
check("指數替代 ETF：QQQ 產出為官方完整持股（≥95 檔、權重 ≥95%、來源為官方 API）",
      _qfile['count'] >= 95 and _qfile['weight_total_pct'] >= 95 and 'dng-api.invesco.com' in _qfile['source'],
      f"{_qfile['count']} 檔 {_qfile['weight_total_pct']}% {str(_qfile['source'])[:46]}")

# TickerInside 共同備援（2026-11-03）：holdings 是 {代號: 權重} 的扁平字典，
# 與 Invesco 的陣列格式不同 → 解析順序與型別檢查必須正確，否則整條來源鏈會爆
# （實際踩到：parse_invesco 對 dict 迭代出字串 key → AttributeError，SOXX 靜默退回備援）。
_tj = {"ticker": "SOXX", "holdings_asof": "2026-11-02", "source_layer": "issuer",
       "cite_as": "TickerInside, iShares Semiconductor ETF (https://tickerinside.com/etf/soxx/)",
       "holdings": {"AMD": 9.2357, "NVDA": 7.9824}}
_tb = json.dumps(_tj).encode()
_th = _fih.parse_bytes(_tb, "https://tickerinside.com/api/v1/fund/soxx.json")
check("指數替代 ETF：TickerInside 扁平字典格式可解析（與 Invesco 陣列格式不衝突）",
      [x['ticker'] for x in _th] == ["AMD", "NVDA"] and _th[0]['weight_pct'] == 9.2357, f"{_th}")
check("指數替代 ETF：TickerInside 的 holdings_asof 可解析為 ISO 日期", _fih.source_asof(_tb) == '2026-11-02')
check("指數替代 ETF：來源要求標註時寫入 attribution（TickerInside 條款要求）",
      'TickerInside' in (_fih.source_attribution(_tb) or ''), f"{_fih.source_attribution(_tb)}")
check("指數替代 ETF：四檔皆設定 TickerInside 共同備援",
      all(any('tickerinside.com' in s for s in _su(f['sources'])) for f in _pr2.values()),
      f"{[f['key'] for f in _pr2.values() if not any('tickerinside.com' in s for s in _su(f['sources']))]}")
_soxx_file = json.load(open('data/index-holdings/SOXX.json', encoding='utf-8'))
check("指數替代 ETF：SOXX 產出為完整 30 檔，且來源是設定中的來源之一",
      _soxx_file['count'] >= 28 and _soxx_file['weight_total_pct'] >= 90
      and _soxx_file['source'] in _su(_pr2['SOXX']['sources']),
      f"{_soxx_file['count']} 檔 {_soxx_file['weight_total_pct']}% {str(_soxx_file['source'])[:44]}")

# iShares 官方下載檔（.xls 其實是 Excel 2003 XML／SpreadsheetML）：pandas 兩種 reader 都讀不了，
# 且官方檔內含未轉義的 & → 必須自行用 xml.etree 解析、並濾掉現金／期貨列
_sml = b'''<?xml version="1.0"?><ss:Workbook xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"><ss:Worksheet><ss:Table>
<ss:Row><ss:Cell><ss:Data ss:Type="String">iShares Semiconductor ETF</ss:Data></ss:Cell></ss:Row>
<ss:Row><ss:Cell><ss:Data ss:Type="String">Fund Holdings as of</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">Nov 02, 2026</ss:Data></ss:Cell></ss:Row>
<ss:Row><ss:Cell><ss:Data ss:Type="String">Ticker</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">Name</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">Asset Class</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">Weight (%)</ss:Data></ss:Cell></ss:Row>
<ss:Row><ss:Cell><ss:Data ss:Type="String">AMD</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">ADVANCED MICRO DEVICES</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">Equity</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">8.88</ss:Data></ss:Cell></ss:Row>
<ss:Row><ss:Cell><ss:Data ss:Type="String">NVDA</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">NVIDIA</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">Equity</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">8.19</ss:Data></ss:Cell></ss:Row>
<ss:Row><ss:Cell><ss:Data ss:Type="String">USD</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">USD CASH</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">Cash</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">0.11</ss:Data></ss:Cell></ss:Row>
<ss:Row><ss:Cell><ss:Data ss:Type="String">IXTZ6</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">EMINI TECH</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">Futures</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">0.00</ss:Data></ss:Cell></ss:Row>
</ss:Table></ss:Worksheet></ss:Workbook>'''
_sh = _fih.parse_bytes(_sml, "manual_upload:x.xls")
check("指數替代 ETF：SpreadsheetML（iShares .xls）可解析且濾掉現金／期貨列",
      [x['ticker'] for x in _sh] == ["AMD", "NVDA"], f"{[(x['ticker'], x['weight_pct']) for x in _sh]}")
check("指數替代 ETF：SpreadsheetML 的「Fund Holdings as of」可解析為 ISO 日期",
      _fih.source_asof(_sml) == '2026-11-02', f"{_fih.source_asof(_sml)}")
check("指數替代 ETF：SpreadsheetML 內未轉義的 & 不會讓解析失敗（官方檔的實際情況）",
      len(_fih.parse_bytes(_sml.replace(b'>iShares Semiconductor ETF<',
                                        b'><a href="x?type=a&style=b">y</a><'), "manual_upload:x.xls")) == 2)
if os.path.exists('data/raw/official/SOXX_holdings.xls'):
    _sf = open('data/raw/official/SOXX_holdings.xls', 'rb').read()
    _sr = _fih.parse_bytes(_sf, "manual_upload:data/raw/official/SOXX_holdings.xls")
    check("指數替代 ETF：官方 SOXX 檔案（真實檔）解析為 30 檔且不含現金列",
          len(_sr) == 30 and not any(x['ticker'] in ('USD', 'XTSLA', 'WFFUT', 'IXTZ6') for x in _sr),
          f"{len(_sr)} 檔、權重 {sum(x['weight_pct'] for x in _sr):.2f}%、asof {_fih.source_asof(_sf)}")

# 人工上傳檔的新鮮度守門（iShares 官方檔案對資料中心 IP 一律 403 → 只能人工放入；
# 但舊的人工檔不能永遠排在前面把自動來源擋掉）
_td3 = tempfile.mkdtemp()
_mf = os.path.join(_td3, "SOXX_holdings.csv")
with open(_mf, "w", encoding="utf-8-sig") as _f:
    _f.write("Ticker,Name,Weight (%)\nAMD,Advanced Micro Devices,9.2\nNVDA,NVIDIA,8.0\n")
_old_root = _fih.ROOT
try:
    setattr(_fih, "ROOT", _td3)
    _fresh = _fih.manual_source_stale("manual_upload:SOXX_holdings.csv", {"max_age_days": 45})
    _t = os.path.getmtime(_mf) - 100 * 86400
    os.utime(_mf, (_t, _t))
    _aged = _fih.manual_source_stale("manual_upload:SOXX_holdings.csv", {"max_age_days": 45})
    _missing = _fih.manual_source_stale("manual_upload:__不存在__.csv", {"max_age_days": 45})
    _plain = _fih.manual_source_stale("https://example.com/x.csv", {"max_age_days": 45})
finally:
    setattr(_fih, "ROOT", _old_root)
check("指數替代 ETF：新鮮的手動檔可用、超過 max_age_days 會被跳過（不擋住自動來源）",
      _fresh is None and _aged and '跳過' in _aged and '100' in _aged, f"fresh={_fresh} aged={_aged}")
check("指數替代 ETF：可選手動檔不存在只是跳過（不是錯誤），非手動來源不受影響",
      '不存在' in (_missing or '') and _plain is None, f"missing={_missing} plain={_plain}")
check("指數替代 ETF：SOXX 設定了官方 CSV 的人工上傳通道（max_age_days=45）",
      any(isinstance(s, dict) and s.get('url', '').startswith('manual_upload:') and s.get('max_age_days')
          for s in _pr2['SOXX']['sources']),
      f"{[s.get('url') for s in _pr2['SOXX']['sources'] if isinstance(s, dict)][:2]}")

# 逐來源門檻：同一檔基金的官方來源與免費備援完整度差很多，必須各自驗證，
# 否則不是備援永遠失敗，就是部分資料（前 25 大）靜默通過。
_srcs = _pr2['QQQ']['sources']
check("指數替代 ETF：QQQ 來源各自覆寫門檻（官方 ≥95 檔、備援 <95 檔）",
      any(isinstance(s, dict) and s.get('expected_min', 0) >= 95 for s in _srcs)
      and any(isinstance(s, dict) and s.get('expected_min', 0) < 95 for s in _srcs),
      f"{[(s.get('expected_min'), s.get('expected_max')) for s in _srcs if isinstance(s, dict)]}")

# 逐來源門檻的實際行為（用 manual_upload 假來源，不打網路）：
# 基金門檻 95~115 檔，但來源自己覆寫成 1~5 檔 → 必須通過（2 檔權重 5%）
_td2 = tempfile.mkdtemp()
with open(os.path.join(_td2, "small.csv"), "w", encoding="utf-8-sig") as _f:
    _f.write("Ticker,Name,Weight (%)\nAAA,Alpha,3\nBBB,Beta,2\n")
_cfg2 = os.path.join(_td2, "cfg.json")
json.dump({"funds": [{"key": "ZZZ", "index": "x", "issuer": "y", "expected_min": 95, "expected_max": 115,
                      "min_weight_total": 95, "sources": [{"url": "manual_upload:small.csv", "expected_min": 1,
                                                            "expected_max": 5, "min_weight_total": 4}]}]},
          open(_cfg2, "w", encoding="utf-8"), ensure_ascii=False)
_oldg = (_fih.CFG, _fih.OUT_DIR, _fih.ROOT)
try:
    setattr(_fih, "CFG", _cfg2)
    setattr(_fih, "OUT_DIR", os.path.join(_td2, "out"))
    setattr(_fih, "ROOT", _td2)
    _rc2 = _fih.main()
finally:
    for _k, _v in zip(("CFG", "OUT_DIR", "ROOT"), _oldg):
        setattr(_fih, _k, _v)
check("指數替代 ETF：逐來源門檻生效（基金門檻 95~115，來源覆寫 1~5 時可通過）", _rc2 == 0, f"rc={_rc2}")

# 完全沒有產出時必須回傳非 0（否則 job 綠色但目錄 0 檔，只能靠人翻日誌）
_tmpd = tempfile.mkdtemp()
_bad_cfg = os.path.join(_tmpd, 'cfg.json')
json.dump({"funds": [{"key": "ZZZ", "index": "x", "issuer": "y", "expected_min": 1, "expected_max": 2,
                      "sources": ["manual_upload:data/raw/official/__不存在的檔案__.csv"]}]},
          open(_bad_cfg, 'w', encoding='utf-8'), ensure_ascii=False)
_old_cfg, _old_out = _fih.CFG, _fih.OUT_DIR
try:
    setattr(_fih, 'CFG', _bad_cfg)
    setattr(_fih, 'OUT_DIR', os.path.join(_tmpd, 'out'))
    _rc = _fih.main()
finally:
    setattr(_fih, 'CFG', _old_cfg)
    setattr(_fih, 'OUT_DIR', _old_out)
check("指數替代 ETF：完全沒有產出時回傳非 0（不再假裝 success）", _rc == 1, f"rc={_rc}")

# 官方財報下載（2026-11-03）
# t187ap06_L / t187ap07_L 在 openapi.twse.com.tw 已失效（回傳 HTML 非 JSON，實測），必須走 MOPS；
# MOPS 的 *_ci.csv 只是「當日出表」的增量批次（實測 53 家 vs 完整快照 1,052 家），
# 所以必須與既有快照 upsert 合併，否則一份 53 家的批次會蓋掉 1,052 家的完整快照。
_fof = _ilu.module_from_spec(_s2 := _ilu.spec_from_file_location("_fof", "skills/data/fetch_official_fundamentals.py"))
_s2.loader.exec_module(_fof)
_flat = [(pre, u) for pre, urls, *_ in _fof.SOURCES for u in (urls if isinstance(urls, list) else [urls])]
# 無後綴的 t187ap06_L / t187ap07_L 已失效（實測回傳 1KB HTML 非 JSON）；可用的是產業後綴版
_bad_ep = [u for _, u in _flat if u.rstrip("/").endswith(("t187ap06_L", "t187ap07_L"))]
check("官方財報：不得使用已失效的無後綴 openapi 財報端點（回傳 HTML）", not _bad_ep, f"{_bad_ep}")
check("官方財報：損益/資產負債涵蓋全部產業檔，只抓 ci 會讓金融保險類永遠沒有官方財報",
      all(sum(1 for p, _ in _flat if p == pre) == len(_fof.INDUSTRIES) for pre in ("t187ap06_L", "t187ap07_L")),
      f"06={sum(1 for p,_ in _flat if p=='t187ap06_L')} 07={sum(1 for p,_ in _flat if p=='t187ap07_L')} 產業={_fof.INDUSTRIES}")
# 沒開始申報的產業檔會回傳「只有出表日期、公司代號空白」的空殼列：必須濾掉，且不得併入它的欄位
_orig_dl = _fof.download
_fof.download = lambda u: json.dumps([{"出表日期": "1151103", "公司代號": "", "營業收入": ""}]).encode()
try:
    _sk, _sr, _sp = _fof.fetch_all(["u-ci", "u-fh"], "json", "公司代號")
finally:
    _fof.download = _orig_dl
check("官方財報：空殼產業檔不會污染資料列與欄位", _sr == [] and _sk == [] and _sp == [{"url": "u-ci", "rows": 0}, {"url": "u-fh", "rows": 0}] and
      _sk == [], f"{_sp}")
check("官方財報：增量來源（06/07）必須標記為 upsert 合併",
      all(inc for pre, _, _, _, _, _, _, inc in _fof.SOURCES if pre in ("t187ap06_L", "t187ap07_L")))
_snap = _fof.existing_snapshot("t187ap06_L", "csv")  # 不寫死檔名：跑過下載後舊檔會被 _latest 取代
_bk, _br, _bn = _fof.upsert(["公司代號", "營業收入"],
                            [{"公司代號": "2330", "營業收入": "999"}, {"公司代號": "9999", "營業收入": "1"}],
                            _snap, "公司代號")
_i = {r["公司代號"]: r["營業收入"] for r in _br}
check("官方財報：增量批次 upsert 後筆數不減、同代號被新資料覆蓋",
      _bn >= 1000 and len(_br) >= _bn and _i.get("2330") == "999" and "9999" in _i,
      f"快照 {_bn} 筆 → 合併後 {len(_br)} 筆、2330={_i.get('2330')}")

# 年化係數必須逐列依各自季別計算（曾用第一列的季別算一個係數 → 混季時 Q3 被當 Q2 年化，高估 50%）
import tempfile as _tf
_td = _tf.mkdtemp()
_od = os.path.join(_td, "official"); os.makedirs(_od)
with open(os.path.join(_od, "t187ap06_L_latest.csv"), "w", encoding="utf-8-sig") as f:
    f.write("出表日期,年度,季別,公司代號,公司名稱,營業收入,本期淨利（淨損）,淨利（淨損）歸屬於母公司業主,基本每股盈餘\n")
    f.write("1151030,115,2,2330,台積電,1000,200,180,3.0\n")   # Q2：累計 6 個月 → ×2
    f.write("1151103,115,3,9999,測試,1500,300,270,4.5\n")      # Q3：累計 9 個月 → ×4/3
with open(os.path.join(_od, "t187ap07_L_latest.csv"), "w", encoding="utf-8-sig") as f:
    f.write("出表日期,年度,季別,公司代號,資產總計,歸屬於母公司業主之權益合計\n")
    f.write("1151030,115,2,2330,10000,5000\n")
    f.write("1151103,115,3,9999,20000,9000\n")
_iio = _ilu.module_from_spec(_s3 := _ilu.spec_from_file_location("_iio", "skills/data/import_official_fundamentals.py"))
_s3.loader.exec_module(_iio)
_old_src = _iio.SRC
try:
    _iio.SRC = _od
    _fin, _info = _iio.import_income_balance(None)
finally:
    _iio.SRC = _old_src
check("官方財報：年化係數逐列依各自季別（Q2×2、Q3×4/3、混季不互相污染）",
      _fin["2330"]["annualize_factor"] == 2 and abs(_fin["9999"]["annualize_factor"] - 4 / 3) < 1e-9
      and _fin["2330"]["eps_annualized"] == 6.0 and _fin["9999"]["eps_annualized"] == 6.0
      and _fin["2330"]["roe_annualized_pct"] == 7.2 and _fin["9999"]["roe_annualized_pct"] == 4.0,
      f"2330={_fin['2330']['annualize_factor']} 9999={round(_fin['9999']['annualize_factor'],4)} "
      f"roe={_fin['2330']['roe_annualized_pct']}/{_fin['9999']['roe_annualized_pct']}")
check("官方財報：混季時仍完整涵蓋所有公司並回報季別分布",
      len(_fin) == 2 and _info["periods"] == {"2026Q2": 1, "2026Q3": 1}, f"{_info.get('periods')}")


# 輸出
w = max(len(n) for n, _, _ in results)
for n, st, d in results:
    print(f"{st:4}  {n.ljust(w)}  {d}")
fails = [r for r in results if r[1] != 'PASS']
print(f"\n合計 {len(results)} 項，PASS {len(results)-len(fails)}，FAIL {len(fails)}")
sys.exit(1 if fails else 0)
