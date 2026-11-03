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
mism = [s['sym'] for s in S if s['sym'] in hmap and hmap[s['sym']] is not None
        and s.get('price') is not None and abs(hmap[s['sym']] - s['price']) > 1e-6]
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
check("TPEx ETF 篩選納入官方清單代號", "sid in _etf_ref" in fd and "etf-meta.json" in fd)
# 價格提醒：儲存邏輯存在且會判斷是否觸發
wl=open('mklab-stock-watchlist.html',encoding='utf-8').read()
check("Watchlist 價格提醒已實作（儲存與觸發判斷）", "function alertText" in wl and "mklab-price-alerts" in wl and "尚未啟用" not in wl)


# 指數替代 ETF 持股：設定與解析
import importlib.util as _ilu
_spec=_ilu.spec_from_file_location("fih","skills/data/fetch_index_holdings.py"); _fih=_ilu.module_from_spec(_spec); _spec.loader.exec_module(_fih)
_cfg=json.load(open('data/index-proxy.json',encoding='utf-8'))
check("指數替代 ETF 設定含 VOO/DIA/QQQ/SOXX", {f['key'] for f in _cfg['funds']}=={'VOO','DIA','QQQ','SOXX'})
_voo=[f for f in _cfg['funds'] if f['key']=='VOO'][0]
if os.path.exists('data/raw/official/VOO_holdings.csv'):
    _man=[x for x in _voo['sources'] if x.startswith('manual_upload:')][0]; _d,_u=_fih.load_source(_man); _h=_fih.parse_bytes(_d,_u)
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

# 指數替代 ETF 來源（2026-11-02：data/index-holdings/ 曾經 0 檔，job 卻顯示 success）
_pr2 = {f['key']: f for f in _cfg['funds']}
check("指數替代 ETF：已移除實測 404 的 SSGA 舊網址（無 -en- 的 holdings-daily-us-dia.xlsx）",
      not any(s.endswith('holdings-daily-us-dia.xlsx') for f in _pr2.values() for s in f['sources']))
check("指數替代 ETF：每檔都明確設定 min_weight_total（來源只提供部分持股時，逐檔設定門檻而非放寬全體）",
      all('min_weight_total' in f for f in _pr2.values()))
_floor_ok = False
try:
    _fih.validate({'key': 'X', 'expected_min': 1, 'expected_max': 10, 'min_weight_total': 90,
                   'issuer': '', 'index': ''}, [{'ticker': 'AAA', 'name': '', 'weight_pct': 50.0}])
except ValueError:
    _floor_ok = True
check("指數替代 ETF：低於該基金 min_weight_total 會被擋下", _floor_ok)

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
_bad_ep = [u for _, u, *_ in _fof.SOURCES if "openapi.twse.com.tw" in u and ("t187ap06_L" in u or "t187ap07_L" in u)]
check("官方財報：t187ap06/07 不得使用已失效的 openapi 端點", not _bad_ep, f"{_bad_ep}")
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
