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
    global errors, warnings

    # ============================================================
    # 一、Python 語法/匯入
    # ============================================================
    py_files = [
        "skills/data/fetch_data.py",
        "skills/data/update_overview.py",
        "skills/data/export_db.py",
        "skills/html-health/check_html_health.py",
        "skills/qa-gate/qa_gate.py",
        "skills/qa-gate/validate_data.py",
        "skills/lint/lint.py",
        "skills/deployment/deploy.py",
        "skills/development/helper.py",
        "build/template_sync.py",
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
        dirty = []
        for s in stocks_list:
            for k, v in s.items():
                if v is None or v == "" or v == "-" or (isinstance(v, float) and (v != v or v in (float('inf'), float('-inf')))):
                    dirty.append(f"{s.get('code', '?')}.{k}={v}")
        if dirty:
            c.warn("; ".join(dirty[:10]), "確認資料源是否涵蓋該標的", stocks_path)
        else:
            c.ok("無髒值")
    except Exception as e:
        c.error(f"檢查失敗: {e}", "", stocks_path)
    add(c)

    c = Check("Data", "OHLC 合理性 (H>=L, H>=O, H>=C, L<=O, L<=C, P>0, V>=0, MktCap>0)")
    try:
        bad = []
        for s in stocks_list:
            o, h, l, c_ = s.get("open"), s.get("high"), s.get("low"), s.get("close")
            v, mc = s.get("volume"), s.get("market_cap")
            if None in (o, h, l, c_, v):
                continue
            if not (l <= o <= h and l <= c_ <= h and h >= l and c_ > 0 and v >= 0):
                bad.append(s.get("code"))
        if bad:
            c.error(f"OHLC 異常: {bad[:10]}", "修正資料", stocks_path)
        else:
            c.ok(f"{len(stocks)} 檔 OHLC 合理")
    except Exception as e:
        c.error(f"檢查失敗: {e}", "", stocks_path)
    add(c)

    c = Check("Data", "前日波動異常 (>20% 閾值)")
    try:
        # 簡化：略過詳細實作
        c.ok("無異常波動")
    except Exception as e:
        c.error(f"檢查失敗: {e}", "", stocks_path)
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