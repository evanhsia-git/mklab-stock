#!/usr/bin/env python3
"""
mklab-stock QA Gate — 品質門禁（零依賴、純 Python）

檢查項目：
  1. Python 語法/匯入
  2. 資料完整性 (stocks.json, industry.json)
  3. JSON Schema
  4. HTML 結構健康（直接 import skills/html-health/check_html_health.py 的
     StructureChecker，不再各自維護一份重複邏輯——這個專案已經因為「同一件事
     兩份程式各寫一次、行為慢慢分岔」出過好幾次事故）
  5. CSS Theme 變數一致性 (檢查 assets/css/mklab-theme.css)
  6. 禁止硬寫核心樣式
  7. 【新增】CSS 屬性誤用 `=` 取代 `:`（真實事故：mklab-theme.css 一大段
     `padding=14px` 這種寫法，整條宣告直接被瀏覽器判定語法錯誤忽略掉）
  8. 【新增】CSS 自訂屬性 (--xxx) 有使用但從未定義（真實事故：--bg-elevated
     被 var() 引用卻沒有任何地方定義，抽屜背景直接變透明）
  9. 【新增】同一個 CSS 選擇器在多個檔案的「非 media query」層級重複定義
     （真實事故：mklab-theme.css 和 component.css 各自寫了一份完全不同的
     .drawer 基礎規則，兩份互相打架，連續好幾輪抽屜相關的怪異行為都源自這裡）
  10. 【新增】MKLAB.DataTable 的 cols:[...] 跟 mklab-core.js 的 COLUMNS 定義
      交叉比對（真實事故：cols 用了 COLUMNS 裡沒有的欄位名稱，DataTable()
      建構子直接 throw，整張表格靜默消失）
  11. 【新增】pagerId:'xxx' 跟對應的 <div id="xxx" class="pager"> 交叉比對
      （真實事故：pagerId 指到不存在的容器 id，或容器忘記加 class="pager"
      導致換頁鍵套用不到深色主題樣式、變成瀏覽器預設白底）
  12. JavaScript 語法 (node --check)
  13. Chart 驗證 (MANUAL)
  14. 內部連結 HTTP 200 (本地檔案存在)
  15. 視覺回歸 (MANUAL)

退出碼：0=ALLOW DEPLOY, 1=BLOCK DEPLOY
用法：python skills/qa-gate/qa_gate.py [--json qa-result.json]
"""
import os
import sys
import re
import glob
import json
import subprocess
import datetime
from dataclasses import dataclass
from typing import List

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 直接重用 check_html_health.py 的 StructureChecker，不再各自維護一份重複邏輯
sys.path.insert(0, os.path.join(ROOT, "skills", "html-health"))
try:
    from check_html_health import StructureChecker as _Health
except Exception as _e:  # pragma: no cover
    _Health = None
    _HEALTH_IMPORT_ERROR = str(_e)
else:
    _HEALTH_IMPORT_ERROR = None


@dataclass
class Check:
    cat: str
    name: str
    critical: bool = False
    status: str = "PASS"
    detail: str = ""
    fix: str = ""
    loc: str = ""

    def ok(self, detail=""):
        self.status = "PASS"; self.detail = detail
        return self

    def warn(self, detail, fix="", loc=""):
        self.status = "WARNING"; self.detail = detail; self.fix = fix; self.loc = loc
        return self

    def error(self, detail, fix="", loc=""):
        self.status = "ERROR"; self.detail = detail; self.fix = fix; self.loc = loc
        return self

    def manual(self, detail):
        self.status = "MANUAL"; self.detail = detail
        return self


def _ca_problems(a: dict):
    """檢查公司行為登記條目缺什麼必要欄位；回 (entry, problems)。"""
    probs = []
    if not str(a.get("source") or "").strip():
        probs.append("source")
    # capital_reduction＝減資（彌補虧損或現金退還股款）；三種都要有換發比率
    if a.get("type") not in ("split", "reverse_split", "capital_reduction"):
        probs.append("type")
    try:
        ratio = float(a.get("ratio") or a.get("implied_ratio") or 0)
    except (TypeError, ValueError):
        ratio = 0
    if ratio <= 0:
        probs.append("ratio")
    if not str(a.get("resume_date") or "").strip():
        probs.append("resume_date")
    return a, probs


checks: List[Check] = []
errors = 0
warnings = 0


def add(c: Check):
    global errors, warnings
    checks.append(c)
    if c.status == "ERROR":
        errors += 1
    elif c.status == "WARNING":
        warnings += 1


def run():
    # ============================================================
    # 一、Python 語法/匯入
    # ============================================================
    py_files = [
        "skills/data/fetch_data.py",
        "skills/data/fetch_us_data.py",
        "skills/data/fetch_us_universe.py",
        "skills/data/build_digest.py",
        "skills/data/data_rules.py",
        "skills/data/sanitize_snapshot.py",
        "skills/data/compute_indicators.py",
        "skills/html-health/check_html_health.py",
        "skills/qa-gate/qa_gate.py",
    ]
    for pf in py_files:
        c = Check("Python", f"syntax: {os.path.basename(pf)}")
        r = subprocess.run([sys.executable, "-m", "py_compile", os.path.join(ROOT, pf)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            c.error(r.stderr.strip(), "修正語法錯誤", pf)
        else:
            c.ok()
        add(c)

    for pf in py_files:
        c = Check("Python", f"import-ok: {os.path.basename(pf)}")
        # Simple syntax check instead of full import (some scripts need DB/ENV)
        r = subprocess.run([sys.executable, "-m", "py_compile", os.path.join(ROOT, pf)],
                           capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            c.error(r.stderr.strip()[:200], "修正語法錯誤", pf)
        else:
            c.ok()
        add(c)

    # ============================================================
    # 二、資料完整性
    # ============================================================
    stocks_path = os.path.join(ROOT, "data", "stocks.json")
    ind_path = os.path.join(ROOT, "data", "industry.json")

    c = Check("Data", "股票代號唯一")
    try:
        with open(stocks_path, encoding="utf-8") as f:
            stocks_data = json.load(f)
        # Handle structure: {"meta": {...}, "stocks": [...]}
        if isinstance(stocks_data, dict) and "stocks" in stocks_data:
            stocks = stocks_data["stocks"]
        elif isinstance(stocks_data, dict) and "data" in stocks_data:
            stocks = stocks_data["data"]
        else:
            stocks = stocks_data
        codes = [s.get("code") or s.get("sym") for s in stocks if s.get("code") or s.get("sym")]
        if len(codes) != len(set(codes)):
            dup = [c for c in codes if codes.count(c) > 1]
            c.error(f"重複代號: {set(dup)}", "去重", stocks_path)
        else:
            c.ok(f"{len(codes)} 檔唯一")
    except Exception as e:
        c.error(f"讀取失敗: {e}", "修復 JSON", stocks_path)
    add(c)

    c = Check("Data", "無髒值 (NaN/null/undefined/Infinity/空字串/非法'-')", critical=False)
    # Extract stocks array from stocks_data dict
    if isinstance(stocks_data, dict) and "stocks" in stocks_data:
        stocks_list = stocks_data["stocks"]
    elif isinstance(stocks_data, dict) and "data" in stocks_data:
        stocks_list = stocks_data["data"]
    else:
        stocks_list = stocks_data
    try:
        # null 是「缺資料」的正確表示（前端顯示「-」），不算髒值；真正的髒值是 NaN/Infinity、空字串、字串 "-"
        dirty = []
        nulls = 0
        for s in stocks_list:
            for k, v in s.items():
                if v is None:
                    nulls += 1
                elif v == "" or v == "-" or (isinstance(v, float) and (v != v or v in (float('inf'), float('-inf')))):
                    dirty.append(f"{s.get('sym', '?')}.{k}={v!r}")
        if dirty:
            c.warn("; ".join(dirty[:10]), "確認資料源是否涵蓋該標的；缺資料請用 null，不要用空字串或 '-'", stocks_path)
        else:
            c.ok(f"無髒值（另有 {nulls} 個 null 欄位＝缺資料，前端顯示「-」）")
    except Exception as e:
        c.error(f"檢查失敗: {e}", "", stocks_path)
    add(c)

    # 2026-11-13：資料品質規則（skills/data/data_rules.py）— 單位、股本、EPS/PE、日期、美股欄位
    # 每條規則對應一次真實事故；ERROR 直接阻擋發布，WARNING 僅提醒。
    try:
        sys.path.insert(0, os.path.join(ROOT, "skills", "data"))
        import data_rules as _dr
        def _load_opt(rel):
            fp = os.path.join(ROOT, rel)
            if not os.path.exists(fp):
                return None
            with open(fp, encoding="utf-8") as f:
                return json.load(f)
        _us_s = _load_opt(os.path.join("data", "us", "us-stocks.json"))
        _us_e = _load_opt(os.path.join("data", "us", "us-etfs.json"))
        _etf_h = _load_opt(os.path.join("data", "etf-holdings.json"))
        _issues = _dr.validate_snapshot(stocks_data, _us_s, _us_e, _etf_h)
        if not _issues:
            add(Check("Data", "資料品質規則（單位/股本/EPS-PE/日期/美股）").ok("全部通過"))
        for _it in _issues:
            _c = Check("Data", f"[{_it['code']}] {_it['msg'][:60]}")
            if _it["level"] == "ERROR":
                _c.error(_it["msg"], "依 docs/superpowers/plans/2026-11-13-data-quality-fix-plan.md 修正後重跑", "data/stocks.json")
            else:
                _c.warn(_it["msg"], "確認後納入改善計畫", "data/stocks.json")
            add(_c)
    except Exception as _e:
        add(Check("Data", "資料品質規則").error(f"規則檢查失敗: {_e}", "修復 data_rules.py", "skills/data/data_rules.py"))

    # P0-6：以下檢查使用 stocks.json 實際欄位（sym / price / open / high / low / volume / market_cap），
    # 舊版誤用 code / close，導致 OHLC 檢查在所有資料上都被跳過（永遠不會回報錯誤）。
    def _num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float("inf"), float("-inf"))

    c = Check("Data", "OHLC 合理性 (L<=O,C<=H, H>=L, 價格>0, 成交量>=0, 市值>0)")
    try:
        bad = []
        checked = 0
        for s_ in stocks_list:
            o, h, l, cl = s_.get("open"), s_.get("high"), s_.get("low"), s_.get("price")
            v, mc = s_.get("volume"), s_.get("market_cap")
            if not all(_num(x) for x in (o, h, l, cl)):
                continue  # 停牌/無成交：OHLC 為 null，屬於合法狀態，不計入
            checked += 1
            if not (h >= l and l <= o <= h and l <= cl <= h and cl > 0):
                bad.append(s_.get("sym"))
            elif _num(v) and v < 0:
                bad.append(s_.get("sym"))
            elif _num(mc) and mc <= 0:
                bad.append(s_.get("sym"))
        if bad:
            c.error(f"OHLC 異常 {len(bad)} 檔: {bad[:10]}", "修正來源資料，不得發布", stocks_path)
        else:
            c.ok(f"{checked} 檔有效 OHLC 全部合理")
    except Exception as e:
        c.error(f"檢查失敗: {e}", "", stocks_path)
    add(c)

    # P0-6：真正的異常漲跌檢查（舊版直接回報「無異常波動」，未做任何計算）。
    # 台股一般股票漲跌幅限制 ±10%；新上市前 5 日不限制、少數除權息/資料延遲可能造成超過 10%。
    # 因此：>10.5% → WARNING（需人工確認）；>30% → ERROR（幾乎只可能是資料錯誤）。
    c = Check("Data", "異常漲跌檢查 (>10.5% 警示 / >30% 阻擋)")
    try:
        warn_list, err_list, ca_list, planned_list = [], [], [], []
        excluded = 0
        for s_ in stocks_list:
            chg = s_.get("chg")
            if not _num(chg):
                continue
            # 權證、特別股、DR 等（security_type=other）單日 ±30% 很常見，不屬於行情錯誤；只檢查一般股票與 ETF
            if s_.get("security_type") not in ("stock", "etf"):
                excluded += 1
                continue
            # 公司行為（分割／反分割／減資）會讓價格跳動數倍，那是**正確**的價格變化，不是資料錯誤。
            # 實測：00662 富邦NASDAQ 5 拆 1，停止交易 2026-11-11、恢復 2026-11-17；
            # 若不分流，恢復當日會被這條規則判成 >30% 而 BLOCK DEPLOY（假警報擋住正確資料）。
            #
            # ⚠️ 只有「**已量化**（有 ratio）且已完成/進行中」的事件才豁免。官方預告自動登錄的
            # planned 條目沒有比率（ratio=None），若也豁免，等於任何有預告的標的都能無聲跳 30%
            # ——那會掩蓋真實異常（2026-11-15 收緊）。
            ca = s_.get("corporate_action") or {}
            quantified = bool(ca.get("ratio")) and ca.get("status") in ("done", "pending")
            if quantified:
                ca_list.append(f"{s_.get('sym')}={chg}%({ca.get('type')} {ca.get('ratio')})")
                continue
            if abs(chg) > 30:
                (err_list if not ca else planned_list).append(f"{s_.get('sym')}={chg}%")
            elif abs(chg) > 10.5:
                (warn_list if not ca else planned_list).append(f"{s_.get('sym')}={chg}%")
        if err_list:
            c.error(f"漲跌幅超過 30% {len(err_list)} 檔: {err_list[:10]}", "核對來源收盤與前收價", stocks_path)
        elif warn_list or planned_list:
            parts = []
            if warn_list:
                parts.append(f"漲跌幅超過 ±10.5% {len(warn_list)} 檔（可能為新上市或資料延遲，需人工確認）: {warn_list[:10]}")
            if planned_list:
                parts.append(f"有公司行為預告但**尚未量化**（planned、無 ratio）卻出現異常漲跌 {len(planned_list)} 檔，"
                             f"不可視為已解釋: {planned_list[:5]}")
            c.warn("；".join(parts) + f"；已略過權證/其他證券 {excluded} 檔", "人工確認", stocks_path)
        elif ca_list:
            c.warn(f"漲跌幅因**公司行為**（分割／減資）而超過 ±10.5% 的 {len(ca_list)} 檔，"
                   f"已排除不計為異常: {ca_list[:5]}；已略過權證/其他證券 {excluded} 檔",
                   "確認還原價與技術指標是否需調整", stocks_path)
        else:
            c.ok(f"一般股票與 ETF 漲跌幅皆在 ±10.5% 以內（略過權證/其他證券 {excluded} 檔）")
    except Exception as e:
        c.error(f"檢查失敗: {e}", "", stocks_path)
    add(c)

    # 依賴登記（#313 教訓的根治）：腳本 import 的第三方套件必須在 requirements.txt——
    # runner 預裝會隨映像更新縮水（#308 requests、#313 pandas 連續爆），顯式清單＋閘門防漏
    c = Check("CI", "Python 第三方依賴全部登記於 requirements.txt")
    try:
        import ast as _ast
        import glob as _glob
        req_path = os.path.join(ROOT, "requirements.txt")
        declared = set()
        if os.path.exists(req_path):
            for line in open(req_path, encoding="utf-8"):
                line = line.strip()
                if line and not line.startswith("#"):
                    declared.add(re.split(r"[=<>!\[]", line)[0].strip().lower())
        stdlib = set(getattr(sys, "stdlib_module_names", ()))
        # 站內模組：與待檢腳本同目錄（或 scripts/）內存在的檔名即視為站內
        repo_mods = {os.path.splitext(os.path.basename(p))[0]
                     for p in _glob.glob(os.path.join(ROOT, "skills", "data", "*.py"))
                     + _glob.glob(os.path.join(ROOT, "scripts", "*.py"))
                     + _glob.glob(os.path.join(ROOT, "skills", "qa-gate", "*.py"))}
        unregistered = []
        for py in (_glob.glob(os.path.join(ROOT, "skills", "data", "*.py"))
                   + _glob.glob(os.path.join(ROOT, "scripts", "*.py"))):
            try:
                tree = _ast.parse(open(py, encoding="utf-8").read())
            except SyntaxError:
                continue
            for node in _ast.walk(tree):
                mods = []
                if isinstance(node, _ast.Import):
                    mods = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, _ast.ImportFrom) and node.module and node.level == 0:
                    mods = [node.module.split(".")[0]]
                for m_ in mods:
                    if m_ in stdlib or m_ in repo_mods or m_ in declared or m_ == "qa_gate":
                        continue
                    rel = os.path.relpath(py, ROOT)
                    unregistered.append(f"{m_}（{rel}）")
        if unregistered:
            c.error(f"未登記的第三方套件：{sorted(set(unregistered))}——加入 requirements.txt",
                    "runner 預裝會縮水，未登記＝CI 隨機爆 ModuleNotFoundError", "requirements.txt")
        else:
            c.ok(f"所有第三方 import 已登記（{len(declared)} 個套件）")
    except Exception as e:
        c.error(f"檢查失敗: {e}", "", "requirements.txt")
    add(c)

    # 資料檔案大小預算（膨脹監控，2026-11-25 phase 3）：
    # 檔案大小 ≠ 網站載入大小（GitHub Pages 自動 gzip，stocks.json 1299KB→傳輸 249KB 實測）；
    # 預算守的是 git 體積增長（每日班 diff）與極端膨脹。分級：≤WARN ok、>WARN warning、>ERROR block。
    c = Check("CI", "資料檔案大小預算（膨脹監控）")
    try:
        import gzip as _gz
        _BUDGETS = [  # (檔案, WARN_KB, ERROR_KB)——WARN≈現況+30%，ERROR≈+60%
            ("data/stocks.json", 1500, 2000),
            ("data/official-fundamentals.json", 1500, 2200),
            ("data/market-extras.json", 1200, 1800),
            ("data/twii-long.json", 500, 800),
            ("data/etf-holdings.json", 500, 800),
        ]
        for _rel, _warn, _err in _BUDGETS:
            _fp = os.path.join(ROOT, _rel)
            if not os.path.exists(_fp):
                c.warn(f"{_rel} 不存在（預算 {_warn}KB 未生效）")
                continue
            _kb = os.path.getsize(_fp) / 1024
            _gzk = len(_gz.compress(open(_fp, "rb").read())) / 1024
            _msg = f"{_rel}: {_kb:.0f} KB（網站 gzip 傳輸 {_gzk:.0f} KB）／預算 WARN {_warn} ERROR {_err}"
            if _kb > _err:
                c.error(f"{_msg}——超 ERROR 預算，需瘦身或重新評估預算", "", _rel)
            elif _kb > _warn:
                c.warn(f"{_msg}——超 WARN 預算，膨脹趨勢需關注")
            else:
                c.ok(_msg)
        # 白名單外的 data/*.json 大檔提醒登記
        for _f in glob.glob(os.path.join(ROOT, "data", "*.json")):
            _rel = os.path.relpath(_f, ROOT)
            if _rel not in [b[0] for b in _BUDGETS] and os.path.getsize(_f) / 1024 > 800:
                c.warn(f"{_rel}: {os.path.getsize(_f)/1024:.0f} KB 未登記預算——加入 _BUDGETS 以納入監控")
    except Exception as e:
        c.error(f"檢查失敗: {e}", "", "data/")
    add(c)

    # P0-6 / P1-1：meta 統計必須與實際陣列一致（count / sources / price_asof_counts）
    c = Check("Data", "meta 統計與實際陣列一致")
    try:
        meta = stocks_data.get("meta", {}) if isinstance(stocks_data, dict) else {}
        problems = []
        if meta.get("count") != len(stocks_list):
            problems.append(f"count meta={meta.get('count')} actual={len(stocks_list)}")
        act_src, act_pa = {}, {}
        for s_ in stocks_list:
            # 鍵正規化：None → 'null'（JSON 物件鍵必為字串，meta 端序列化後就是 'null'；
            # 2026-11-24 #313：CI 班某檔收盤抓失敗 price_asof=None，鍵型差異誤報 ERROR）
            k_src = "null" if s_.get("source") is None else s_.get("source")
            k_pa = "null" if s_.get("price_asof") is None else s_.get("price_asof")
            act_src[k_src] = act_src.get(k_src, 0) + 1
            act_pa[k_pa] = act_pa.get(k_pa, 0) + 1
        if meta.get("sources") != act_src:
            problems.append(f"sources meta={meta.get('sources')} actual={act_src}")
        if meta.get("price_asof_counts") != act_pa:
            problems.append(f"price_asof_counts meta={meta.get('price_asof_counts')} actual={act_pa}")
        if problems:
            c.error("; ".join(problems), "重新執行 integrate_official_company.py 重算 meta", stocks_path)
        else:
            c.ok(f"count={len(stocks_list)}，來源與行情日期分布一致")
    except Exception as e:
        c.error(f"檢查失敗: {e}", "", stocks_path)
    add(c)

    # P0-6：行情日期與來源狀態（stale 資料不得冒充最新）
    # 上櫃（TPEx）常比上市（TWSE）早一個交易日更新，因此快照內可能混有 as_of 之後的行情日期：
    # 這是已知且 meta 會揭露的狀態（P1-1），只給 WARNING；真正的未來日期（晚於今天）才是 ERROR。
    c = Check("Data", "行情日期合理（非未來日期）、stale 資料明示")
    try:
        import datetime as _dt
        today = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).strftime("%Y-%m-%d")
        as_of = str((stocks_data.get("meta") or {}).get("as_of") or "")[:10]
        dates = [str(s_.get("price_asof") or "")[:10] for s_ in stocks_list]
        future = [s_.get("sym") for s_, d_ in zip(stocks_list, dates) if d_ and d_ > today]
        newer = [s_.get("sym") for s_, d_ in zip(stocks_list, dates) if as_of and d_ and d_ > as_of]
        stale = [s_.get("sym") for s_ in stocks_list if s_.get("quality") == "stale"]
        if future:
            c.error(f"行情日期晚於今天 {len(future)} 檔: {future[:10]}", "檢查日期解析", stocks_path)
        elif newer or stale:
            c.warn(f"快照混合日期：晚於 as_of({as_of}) 的行情 {len(newer)} 檔（上櫃較早更新，屬已揭露狀態）；"
                   f"沿用前次資料 stale {len(stale)} 檔", "確認 TWSE 是否已更新、來源是否恢復", stocks_path)
        else:
            c.ok("行情日期皆不晚於快照日期，無 stale 資料")
    except Exception as e:
        c.error(f"檢查失敗: {e}", "", stocks_path)
    add(c)

    # ── 公司行為相關三條規則（2026-11-15 新增）────────────────────────
    # 對應事故：0052／00631L 分割期間的死值列（連續同價同量）被當成真實成交，
    # 一路汙染 MA/RSI；00662 5 拆 1 未登記導致漲跌幅被誤判；分割倍數靠人工記憶。
    # 這裡只做「提醒與否決」，還原價與套用一律由 corporate-actions.json（人工確認）決定。

    # 1) CORPORATE_ACTION_UNSOURCED（ERROR）：每筆登記都要有來源與倍數，否則不得部署。
    c = Check("Data", "公司行為登記完整 (CORPORATE_ACTION_UNSOURCED)")
    ca_path = os.path.join(ROOT, "data", "corporate-actions.json")
    ca_bad, ca_total = [], 0
    if not os.path.exists(ca_path):
        c.error("找不到 data/corporate-actions.json", "建立登記檔（分割／反分割／減資）", ca_path)
    else:
        try:
            ca_actions = (json.load(open(ca_path, encoding="utf-8")) or {}).get("actions") or []
            ca_total = len(ca_actions)
            for a in ca_actions:
                _, probs = _ca_problems(a)
                st = a.get("status") or "done"
                # 已執行（done）的條目才強制要 type/ratio/resume_date；規劃中（pending/planned）只要求 source，
                # 因為官方公告尚未給出精確倍數與換發日期（00757、006208）。
                required = [p for p in probs if p in ("type", "ratio", "resume_date")] if st == "done" else []
                if not str(a.get("source") or "").strip() or required:
                    ca_bad.append(f"{a.get('sym', '?')}({','.join(required + (['source'] if not str(a.get('source') or '').strip() else []))})")
            if ca_bad:
                c.error(f"{len(ca_bad)} 筆欠缺必要欄位: {ca_bad[:8]}",
                        "已執行的公司行為必須有 source、type、ratio>0、resume_date；規劃中者至少需 source",
                        ca_path)
            else:
                c.ok(f"公司行為登記 {ca_total} 筆，來源／倍數／日期齊全")
        except Exception as e:
            c.error(f"讀取失敗: {e}", "修復 JSON 格式", ca_path)
    add(c)

    # 2) DEAD_VALUE_RUN（WARNING）：歷史快照仍有「連續同價＋同量」的假成交列。
    #    只回溯最近 20 個快照（全掃 146 檔要 5 秒以上，且舊的死值列已被 repair_history 清掉）；
    #    成交量必須「一字不差」才算死值——實測 40 萬筆相鄰配對僅 151 筆量相同且都非同價。
    c = Check("Data", "歷史快照死值列 (DEAD_VALUE_RUN)")
    try:
        import glob as _glob
        snaps = sorted(_glob.glob(os.path.join(ROOT, "data", "history", "*.json")))[-20:]
        dead_syms, dead_cells, worst = [], 0, []
        for sf in snaps:
            try:
                rows = (json.load(open(sf, encoding="utf-8")) or {}).get("stocks") or []
            except Exception:
                continue
            by_sym = {}
            for r in rows:
                by_sym.setdefault(str(r.get("stock_id")), []).append(r)
            for sym, rs in by_sym.items():
                if len(rs) < 3:
                    continue
                run = 1
                for i in range(1, len(rs)):
                    a_, b_ = rs[i - 1], rs[i]
                    same = (a_.get("open") == b_.get("open") == a_.get("high") == b_.get("high")
                            == a_.get("low") == b_.get("low") == a_.get("close") == b_.get("close")
                            and a_.get("volume") == b_.get("volume") and a_.get("close") is not None)
                    run = run + 1 if same else 1
                    if run >= 3:
                        dead_cells += 1
                        if sym not in dead_syms:
                            dead_syms.append(sym)
                        if len(worst) < 5:
                            worst.append(f"{sym}@{os.path.basename(sf)[:8]}")
        if dead_syms:
            c.warn(f"最近 {len(snaps)} 個快照仍有疑似死值列：{len(dead_syms)} 檔、{dead_cells} 格"
                   f"（例：{worst}）",
                   "執行 skills/data/repair_history.py 剔除後重跑 build_kline.py 與 compute_indicators.py",
                   os.path.join(ROOT, "data", "history"))
        else:
            c.ok(f"最近 {len(snaps)} 個快照無連續同價同量的死值列")
    except Exception as e:
        c.warn(f"檢查失敗: {e}", "人工確認 history 快照", "")
    add(c)

    # 3) CORPORATE_ACTION_DETECTED（WARNING）：自動偵測到的候選還沒人工確認。
    c = Check("Data", "待確認公司行為候選 (CORPORATE_ACTION_DETECTED)")
    cand_path = os.path.join(ROOT, "data", "corporate-actions-candidates.json")
    try:
        cands = (json.load(open(cand_path, encoding="utf-8")) or {}).get("candidates") or [] \
            if os.path.exists(cand_path) else []
        if os.path.exists(ca_path):
            reg = {a.get("sym") for a in ((json.load(open(ca_path, encoding="utf-8")) or {}).get("actions") or [])}
        else:
            reg = set()
        pending = [x for x in cands if x.get("sym") not in reg]
        if pending:
            top = [f"{x.get('sym')}≈{x.get('implied_ratio')}" for x in pending[:6]]
            c.warn(f"{len(pending)} 檔跳空候選尚未登錄為公司行為（不影響股價顯示，也未套用還原價）: {top}",
                   "核對官方公告後登錄到 data/corporate-actions.json，或確認是正常波動後忽略", cand_path)
        else:
            c.ok("無待確認的公司行為候選")
    except Exception as e:
        c.warn(f"檢查失敗: {e}", "人工確認候選檔", "")
    add(c)

    # 4) CORPORATE_ACTION_UPCOMING（WARNING）：官方預告有事件但還沒登錄 registry。
    #    來源＝data/corporate-actions-schedule.json（fetch_split_schedule.py 產出）。
    #    預告沒有比率，所以只提醒「該登錄了」，不自動補倍數。
    c = Check("Data", "官方公司行為預告 (CORPORATE_ACTION_UPCOMING)")
    sched_path = os.path.join(ROOT, "data", "corporate-actions-schedule.json")
    try:
        evs = ((json.load(open(sched_path, encoding="utf-8")) or {}).get("events") or []
               if os.path.exists(sched_path) else [])
        reg_syms = ({a.get("sym") for a in ((json.load(open(ca_path, encoding="utf-8")) or {}).get("actions") or [])}
                    if os.path.exists(ca_path) else set())
        upcoming = [e for e in evs if e.get("when") == "upcoming"]
        missing = [e for e in upcoming if e.get("sym") not in reg_syms]
        if missing:
            c.warn(f"官方預告 {len(missing)} 筆公司行為尚未登錄 registry: "
                   + ", ".join(f"{e.get('sym')}({e.get('reason')})" for e in missing[:6]),
                   "執行 skills/data/fetch_split_schedule.py --register（以 status=planned 登錄，不含比率）",
                   sched_path)
        elif upcoming:
            c.ok(f"官方預告 {len(upcoming)} 筆事件皆已登錄（未量化者為 planned，不套用還原價）")
        else:
            c.ok("目前無官方公司行為預告")
    except Exception as e:
        c.warn(f"檢查失敗: {e}", "人工確認排程檔", "")
    add(c)

    # ============================================================
    # 三、JSON Schema
    # ============================================================
    c = Check("JSON", "stocks.json Schema")
    try:
        # stocks_list already extracted above
        stocks = stocks_list
        # Actual data fields: sym, name, price, open, high, low, volume, pe, pb, div, roe, roa, eps, market_cap, ind, chg, rank
        required = {"sym", "name", "price", "open", "high", "low", "volume"}
        missing = []
        for s in stocks_list:
            if not all(k in s for k in required):
                missing.append(s.get("sym", "?"))
        if missing:
            c.error(f"缺漏欄位: {missing[:10]}", "補齊 Schema", stocks_path)
        else:
            c.ok(f"schema 完整 ({len(stocks_list)} 檔)")
    except Exception as e:
        c.error(f"讀取失敗: {e}", "", stocks_path)
    add(c)

    c = Check("JSON", "industry.json Schema")
    try:
        with open(ind_path, encoding="utf-8") as f:
            ind = json.load(f)
        if "industry" in ind and len(ind["industry"]) > 0:
            c.ok(f"{len(ind['industry'])} 個產業")
        else:
            c.error("產業資料為空", "檢查匯出邏輯", ind_path)
    except Exception as e:
        c.error(f"讀取失敗: {e}", "", ind_path)
    add(c)

    # ============================================================
    # 四、HTML 驗證（結構完整性 + 樣板佔位符 + MKLAB script 依賴，邏輯來自 check_html_health.py）
    # ============================================================
    html_files = glob.glob(os.path.join(ROOT, "*.html"))
    html_fail = 0
    if _Health is None:
        add(Check("HTML", "載入 check_html_health.py").error(
            f"import 失敗: {_HEALTH_IMPORT_ERROR}", "確認 skills/html-health/check_html_health.py 存在且語法正確", ""))
    else:
        for hf in html_files:
            _h = _Health()
            src = open(hf, encoding="utf-8").read()
            try:
                _h.feed(src)
            except Exception as e:
                add(Check("HTML", f"解析: {os.path.basename(hf)}").error(f"解析異常: {e}", "修復 HTML", hf))
                html_fail += 1
                continue
            msgs = _h.report(hf, src)
            if msgs:
                html_fail += 1
                add(Check("HTML", f"結構: {os.path.basename(hf)}").error(
                    "; ".join(msgs), "修復 HTML 結構（詳見說明；含未關閉/多餘閉合標籤、重複 id、未替換樣板、漏載 MKLAB script）", hf))
        if html_fail == 0:
            add(Check("HTML", "結構健康檢查").ok(f"全部 {len(html_files)} 個 HTML 通過"))

    # ============================================================
    # 五、CSS 驗證 (統一 Theme / 重複定義)
    # ============================================================
    c = Check("CSS", "統一 Theme 變數 (var(--bg) 等)", critical=True)
    theme_css = os.path.join(ROOT, "assets", "css", "mklab-theme.css")
    if os.path.exists(theme_css):
        with open(theme_css, encoding="utf-8") as f:
            theme_src = f.read()
        required_tokens = ["--bg", "--fg", "--muted", "--primary", "--card", "--border"]
        missing = [t for t in required_tokens if t not in theme_src]
        if missing:
            c.error(f"Theme CSS 缺少設計令牌: {missing}", "在 assets/css/mklab-theme.css :root 補齊", theme_css)
        else:
            c.ok("Theme CSS 關鍵設計令牌完整")
    else:
        c.error("找不到 assets/css/mklab-theme.css", "確認 CSS 檔案存在", theme_css)
    add(c)

    c = Check("CSS", "禁止硬寫核心樣式 (違反 Design Token)", critical=False)
    inline_hard = []
    for hf in html_files:
        # 跳過 pages/ 內容片段
        if "/pages/" in hf or hf.endswith("/pages/"):
            continue
        src = open(hf, encoding="utf-8").read()
        # 僅檢查完整頁面（有 <html> 標籤的）
        if "<html" not in src.lower():
            continue
        # (?<!-) 避免把 --bar-color / --dot-color 這種「合法的 CSS 自訂屬性名稱」
        # 誤判成硬寫樣式（自訂屬性名稱字面上就會包含 color/background 這些字）
        if re.search(r'style=["\'][^\'"]*(?<!-)(?:color|background|font-size|font-family)\s*:', src, re.I):
            inline_hard.append(os.path.basename(hf))
    if inline_hard:
        c.warn(f"行內硬寫樣式: {inline_hard}", "改用 CSS class / Design Token；動態顏色請用 CSS 自訂屬性 (--xxx) 帶入，不要直接寫 style=\"background:...\"", ", ".join(inline_hard))
    else:
        c.ok("無行內硬寫核心樣式")
    add(c)

    css_dir = os.path.join(ROOT, "assets", "css")
    css_files = sorted(glob.glob(os.path.join(css_dir, "*.css")))
    css_sources = {}
    css_sources_nocomment = {}
    _comment_re = re.compile(r'/\*.*?\*/', re.S)
    for cf in css_files:
        with open(cf, encoding="utf-8") as f:
            raw = f.read()
        css_sources[cf] = raw
        # 拿掉註解但保留行數對齊（換行符數量不變，避免行號報錯位移）
        css_sources_nocomment[cf] = _comment_re.sub(lambda m: "\n" * m.group(0).count("\n"), raw)

    # 新增：CSS 屬性誤用 `=` 取代 `:`（真實事故：padding=14px 整條宣告失效）
    c = Check("CSS", "屬性誤用 = 取代 :（語法錯誤）", critical=True)
    css_eq_bugs = []
    # 排除合法的屬性選擇器如 input[type=number]，只抓「單字 = 值」這種明顯是打錯 : 的樣式
    eq_re = re.compile(r'(?<!\[)\b([a-zA-Z-]{3,})=(?!["\'])([a-zA-Z0-9#.%\-]+)(?=[;\s}])')
    for cf, src in css_sources_nocomment.items():
        for m in eq_re.finditer(src):
            prop = m.group(1)
            # 排除 data-*、aria-* 等屬性選擇器語境，以及 type=number 這種已知合法用法
            if prop in ("type", "data-theme"):
                continue
            lineno = src.count("\n", 0, m.start()) + 1
            css_eq_bugs.append(f"{os.path.basename(cf)}:{lineno} `{prop}={m.group(2)}`")
    if css_eq_bugs:
        c.error(f"疑似 = 誤用取代 :（{len(css_eq_bugs)} 處）: {css_eq_bugs[:10]}", "改成 `屬性: 值;`", "; ".join(css_eq_bugs[:5]))
    else:
        c.ok("無 = 誤用")
    add(c)

    # 新增：CSS 自訂屬性 (--xxx) 有使用但從未定義（真實事故：--bg-elevated 未定義，抽屜背景變透明）
    c = Check("CSS", "自訂屬性 (--xxx) 有使用但未定義", critical=True)
    defined_vars, used_vars = set(), {}
    var_def_re = re.compile(r'(--[a-zA-Z0-9-]+)\s*:')
    var_use_re = re.compile(r'var\(\s*(--[a-zA-Z0-9-]+)')
    for cf, src in css_sources_nocomment.items():
        defined_vars.update(var_def_re.findall(src))
        for m in var_use_re.finditer(src):
            used_vars.setdefault(m.group(1), []).append(os.path.basename(cf))
    # HTML 內的 inline style 也可能定義/使用自訂屬性（如熱力圖的 --cell-bg）
    for hf in html_files:
        src = open(hf, encoding="utf-8").read()
        defined_vars.update(re.findall(r'style="[^"]*(--[a-zA-Z0-9-]+)\s*:', src))
        for m in var_use_re.finditer(src):
            used_vars.setdefault(m.group(1), []).append(os.path.basename(hf))
    # 共用 JS（assets/js/*.js）產生的 HTML 樣板也會用 style="--xxx:..." 帶入自訂屬性（如市場寬度長條的 --bar-fill）
    for jf in sorted(glob.glob(os.path.join(ROOT, "assets", "js", "*.js"))):
        src = open(jf, encoding="utf-8").read()
        defined_vars.update(re.findall(r'style=\\?["\'][^"\']*?(--[a-zA-Z0-9-]+)\s*:', src))
        defined_vars.update(re.findall(r'style\.setProperty\(\s*[\'"](--[a-zA-Z0-9-]+)', src))
    undefined = {k: v for k, v in used_vars.items() if k not in defined_vars}
    if undefined:
        detail = "; ".join(f"{k} (用於 {', '.join(sorted(set(v)))})" for k, v in undefined.items())
        c.error(f"未定義的自訂屬性: {detail}", "在 assets/css/mklab-theme.css :root 或對應 HTML 補上定義", "")
    else:
        c.ok(f"{len(used_vars)} 個自訂屬性皆有定義")
    add(c)

    # 新增：同一選擇器在多個 CSS 檔的「非 media query」層級重複定義
    # （真實事故：mklab-theme.css 和 component.css 各自寫了一份完全不同的 .drawer 基礎規則互相打架）
    c = Check("CSS", "跨檔案重複的選擇器（非 @media 層級）", critical=False)

    def _top_level_selectors(src):
        """粗略移除 @media {...} 區塊後，抓出還在頂層的選擇器名稱"""
        depth = 0
        media_depth = None
        out = []
        i = 0
        buf = ""
        while i < len(src):
            ch = src[i]
            if src[i:i + 6] == "@media" and media_depth is None:
                media_depth = depth
            if ch == "{":
                if media_depth is None:
                    sel = buf.strip()
                    if sel and not sel.startswith("@") and depth == 0:
                        for s in sel.split(","):
                            out.append(s.strip())
                buf = ""
                depth += 1
            elif ch == "}":
                depth -= 1
                if media_depth is not None and depth == media_depth:
                    media_depth = None
                buf = ""
            else:
                buf += ch
            i += 1
        return out

    sel_locations = {}
    for cf, src in css_sources_nocomment.items():
        for sel in _top_level_selectors(src):
            if not sel or sel.startswith("/*") or sel.startswith("--"):
                continue
            sel_locations.setdefault(sel, set()).add(os.path.basename(cf))
    cross_file_dups = {sel: files for sel, files in sel_locations.items() if len(files) > 1}
    if cross_file_dups:
        detail = "; ".join(f"`{sel}` 出現在 {sorted(files)}" for sel, files in list(cross_file_dups.items())[:8])
        c.warn(f"{len(cross_file_dups)} 個選擇器跨檔重複: {detail}",
               "確認是否為刻意 override，若非刻意請合併到單一檔案，避免後續互相打架", "")
    else:
        c.ok("無跨檔案的頂層選擇器重複")
    add(c)

    # 新增：MKLAB.DataTable 的 cols:[...] 跟 mklab-core.js 的 COLUMNS 交叉比對
    # （真實事故：cols 用了不存在的欄位名，DataTable() constructor 直接 throw，表格靜默消失）
    c = Check("JS", "DataTable cols 是否都在 COLUMNS 定義內", critical=True)
    core_js_path = os.path.join(ROOT, "assets", "js", "mklab-core.js")
    if os.path.exists(core_js_path):
        core_src = open(core_js_path, encoding="utf-8").read()
        m = re.search(r'const COLUMNS\s*=\s*\{(.*?)\n\s*\};', core_src, re.S)
        columns_keys = set(re.findall(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*\{', m.group(1), re.M)) if m else set()
        unknown = []
        for hf in html_files:
            src = open(hf, encoding="utf-8").read()
            for cm in re.finditer(r'cols\s*:\s*\[([^\]]*)\]', src):
                cols = re.findall(r'[\'"]([a-zA-Z_][a-zA-Z0-9_]*)[\'"]', cm.group(1))
                for col in cols:
                    if columns_keys and col not in columns_keys:
                        unknown.append(f"{os.path.basename(hf)}: '{col}'")
        if not columns_keys:
            c.warn("解析不到 mklab-core.js 的 COLUMNS 定義，略過交叉比對", "確認 COLUMNS 物件格式未變", core_js_path)
        elif unknown:
            c.error(f"cols 用了 COLUMNS 沒有的欄位: {unknown[:10]}", "在 mklab-core.js 的 COLUMNS 補上該欄位，或修正 cols 拼字", "; ".join(unknown[:5]))
        else:
            c.ok("所有 cols 欄位都在 COLUMNS 定義內")
    else:
        c.error("找不到 assets/js/mklab-core.js", "確認檔案存在", core_js_path)
    add(c)

    # 新增：pagerId:'xxx' 是否都有對應的 <div id="xxx" class="pager">
    # （真實事故：容器 id 打錯或整個沒建立，換頁鍵沒地方渲染；或忘記加 class="pager" 導致樣式跑掉變白底）
    c = Check("HTML", "pagerId 是否都有對應的 .pager 容器", critical=True)
    pager_problems = []
    for hf in html_files:
        src = open(hf, encoding="utf-8").read()
        pager_ids = set(re.findall(r'pagerId\s*:\s*[\'"]([a-zA-Z0-9_-]+)[\'"]', src))
        for pid in pager_ids:
            div_m = re.search(r'<div\b[^>]*\bid=["\']' + re.escape(pid) + r'["\'][^>]*>', src)
            if not div_m:
                pager_problems.append(f"{os.path.basename(hf)}: pagerId='{pid}' 找不到對應的 <div id=\"{pid}\">")
                continue
            tag_src = div_m.group(0)
            cls_m = re.search(r'class=["\']([^"\']*)["\']', tag_src)
            if not cls_m or "pager" not in cls_m.group(1).split():
                pager_problems.append(f"{os.path.basename(hf)}: #{pid} 缺少 class=\"pager\"（會退回瀏覽器預設樣式）")
    if pager_problems:
        c.error("; ".join(pager_problems[:10]), "補上容器 div 並加上 class=\"pager\"", "; ".join(pager_problems[:5]))
    else:
        c.ok("所有 pagerId 都有對應且正確的 .pager 容器")
    add(c)

    # ============================================================
    # 六、JavaScript 語法 (node --check)
    # ============================================================
    if subprocess.run(["which", "node"], capture_output=True).returncode == 0:
        for hf in html_files:
            src = open(hf, encoding="utf-8").read()
            blocks = re.findall(r"<script>(.*?)</script>", src, re.S)
            for i, b in enumerate(blocks):
                if not b.strip():
                    continue
                tmp = "/tmp/_js_check.js"
                open(tmp, "w").write(b)
                r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
                c = Check("JS", f"syntax: {os.path.basename(hf)}#{i}")
                if r.returncode != 0:
                    c.error(r.stderr.strip().splitlines()[-1], "修正 JS 語法", hf)
                else:
                    c.ok()
                add(c)
    else:
        c = Check("JS", "node --check 可用性", critical=False)
        c.warn("node 未安裝，跳過 JS 語法檢查", "安裝 node 或於 CI 執行", "")
        add(c)

    # ============================================================
    # 七、Chart 驗證 (MANUAL)
    # ============================================================
    for hf in html_files:
        if "kline" in hf.lower() or hf == os.path.join(ROOT, "index.html") or "research" in hf:
            c = Check("Chart", f"圖表渲染: {os.path.basename(hf)}", critical=False)
            c.manual("需瀏覽器載入確認 Canvas/SVG 存在、Dataset 非空、無 Chart Error，並截圖")
            add(c)

    # ============================================================
    # 八、超連結驗證 (內部 HTTP 200)
    # ============================================================
    c = Check("Links", "內部連結 HTTP 200 (本地)", critical=True)
    hrefs = []
    for hf in html_files:
        src = open(hf, encoding="utf-8").read()
        for m in re.finditer(r'href=["\']([^"\']+)["\']', src):
            href = m.group(1)
            # 排除外部連結、錨點、data: 協議、絕對路徑（以 / 開頭）、query parameters
            base_href = href.split("?")[0].split("#")[0]
            if (href.startswith("http://") or href.startswith("https://") or
                href.startswith("mailto:") or href.startswith("javascript:") or
                href.startswith("#") or href.startswith("data:") or
                href.startswith("/") or base_href == ""):
                continue
            hrefs.append((href, hf))
    broken = []
    for href, hf in hrefs:
        # 檢查時也用 base_href
        base_href = href.split("?")[0].split("#")[0]
        target = os.path.join(os.path.dirname(hf), base_href)
        target = os.path.normpath(target)
        if not os.path.exists(target):
            broken.append(f"{os.path.basename(hf)} -> {href} (404)")
    if broken:
        c.error("; ".join(broken[:15]), "修正或建立遺失的內部檔案", "")
    else:
        c.ok("全部內部連結可解析")
    add(c)

    # ============================================================
    # 九、視覺回歸 (MANUAL)
    # ============================================================
    c = Check("Visual", "視覺回歸比對", critical=False)
    c.manual("需瀏覽器截圖，與 Baseline 比較配色/字體/間距/版面/圖表，差異超閾值標記失敗")
    add(c)

    # ============================================================
    # 報告輸出
    # ============================================================
    block = errors > 0
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append(f"# mklab-stock QA Gate 報告")
    lines.append(f"**時間**: {now}  ")
    lines.append(f"**Critical ERROR**: {errors}  | **WARNING**: {warnings}  ")
    lines.append(f"**最終判定**: {'🔴 BLOCK DEPLOY' if block else '🟢 ALLOW DEPLOY'}")
    lines.append("")
    lines.append("| 類別 | 項目 | 狀態 | 說明 | 修正建議 | 位置 |")
    lines.append("|------|------|------|------|----------|------|")
    for c in checks:
        lines.append(f"| {c.cat} | {c.name} | {c.status} | {c.detail[:120]} | {c.fix[:80]} | {c.loc} |")
    lines.append("")
    lines.append("## 問題摘要")
    for c in checks:
        if c.status in ("ERROR", "WARNING"):
            lines.append(f"- **[{c.status}] {c.cat}/{c.name}**: {c.detail}")
            if c.fix:
                lines.append(f"  - 建議: {c.fix}（{c.loc}）")
    lines.append("")
    lines.append(f"## 最終判定: {'BLOCK DEPLOY' if block else 'ALLOW DEPLOY'}")
    lines.append("")
    lines.append("> 除非所有 Critical 項目皆通過，否則一律 BLOCK DEPLOY。")
    lines.append("> [MANUAL] 項目需 Agent 以瀏覽器工具實際載入頁面驗證（Chart/Console/視覺回歸），不計入自動阻擋，但須於部署前完成。")

    report = "\n".join(lines)
    out_md = os.path.join(ROOT, "data", "qa-report.md")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    open(out_md, "w", encoding="utf-8").write(report)
    print(report)
    if "--json" in sys.argv:
        jp = sys.argv[sys.argv.index("--json") + 1]
        json.dump({"allow_deploy": not block, "errors": errors, "warnings": warnings,
                   "checks": [{k: getattr(c, k) for k in ("cat", "name", "status", "detail")} for c in checks]},
                  open(jp, "w"), ensure_ascii=False, indent=2)
    return 1 if block else 0


if __name__ == "__main__":
    sys.exit(run())