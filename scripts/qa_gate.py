#!/usr/bin/env python3
"""
mklab-stock QA Gate (Quality Gate)

扮演 MKLAB Quality Assurance Agent：在 Push / Deploy 前執行完整品質驗證。
任一 Critical 項目未通過 → 輸出 BLOCK DEPLOY，禁止部署。
"""
import os
import sys
import json
import glob
import re
import subprocess
import datetime
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Check:
    def __init__(self, cat, name, critical=True):
        self.cat = cat
        self.name = name
        self.critical = critical
        self.status = "PASS"
        self.detail = ""
        self.fix = ""
        self.loc = ""

    def error(self, detail, fix="", loc=""):
        self.status = "ERROR"
        self.detail = detail
        self.fix = fix
        self.loc = loc
        return self

    def warn(self, detail, fix="", loc=""):
        self.status = "WARNING"
        self.detail = detail
        self.fix = fix
        self.loc = loc
        return self

    def manual(self, detail="需瀏覽器/人工驗證"):
        self.status = "MANUAL"
        self.detail = detail
        return self

    def ok(self, detail=""):
        self.status = "PASS"
        self.detail = detail
        return self


def safe_float(v):
    if v in (None, "", "-"):
        return None
    try:
        f = float(v)
        if f != f:  # NaN
            return "NaN"
        if f in (float("inf"), float("-inf")):
            return "Inf"
        return f
    except (ValueError, TypeError):
        return "NaN"


class _HealthHTMLParser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}
    RAW_CONTENT_TAGS = {"script", "style", "pre", "code", "textarea"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.body_children = 0
        self.in_body = False
        self.style_open = None
        self.style_closed = True
        self.saw_nav = self.saw_utilbar = self.saw_drawer = self.saw_tbl = False
        self.errors = []
        self.raw_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.RAW_CONTENT_TAGS:
            self.raw_depth += 1
        if self.raw_depth > 0:
            return

        if tag == "style":
            self.style_open = self.getpos()[0]
            self.style_closed = False
        elif tag == "body":
            self.in_body = True
            if not self.style_closed:
                self.errors.append(f"line {self.getpos()[0]}: <body> 出現在 <style> 未關閉之後（style 開於 line {self.style_open}）")

        if self.in_body and tag not in self.VOID:
            self.body_children += 1

        cls = dict(attrs).get("class", "")
        if tag == "nav":
            self.saw_nav = True
        if "utilbar" in cls:
            self.saw_utilbar = True
        if "drawer" in cls:
            self.saw_drawer = True
        if tag in ("table", "section", "mklab-datatable", "mklab-kline"):
            self.saw_tbl = True

        if tag not in self.VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag in self.RAW_CONTENT_TAGS:
            self.raw_depth = max(0, self.raw_depth - 1)
            self._pop_stack(tag)
            return
        if self.raw_depth > 0:
            return

        if tag == "style":
            self.style_closed = True
            self._pop_stack("style")
            return
        if tag == "body":
            self.in_body = False

        self._pop_stack(tag)

    def _pop_stack(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i]
                break

    def report(self, fname):
        msgs = list(self.errors)
        base = os.path.basename(fname)
        is_help = base.endswith("-help.html") or base == "help.html"

        if self.stack:
            truly_unclosed = [(t, ln) for t, ln in self.stack if t not in {"html", "body", "div"}]
            if truly_unclosed:
                msgs.append("未關閉標籤: " + ", ".join(f"{t}(line {ln})" for t, ln in truly_unclosed))
        if not self.style_closed:
            msgs.append(f"<style> 未關閉（開於 line {self.style_open}）")
        if not self.in_body and self.body_children == 0 and self.stack:
            msgs.append("解析後 <body> 無子元素（網頁會空白）")

        if not is_help:
            if not self.saw_nav:
                msgs.append("缺少 <nav> 導航列")
            if not self.saw_utilbar:
                msgs.append("缺少 .utilbar 工具列")
            if not self.saw_drawer:
                msgs.append("缺少 .drawer 設定抽屜")
            if not self.saw_tbl:
                msgs.append("缺少 table/section 主要內容區塊")
        return msgs


def check_py_syntax(pf):
    name = os.path.basename(pf)
    r = subprocess.run([sys.executable, "-m", "py_compile", pf],
                       capture_output=True, text=True)
    c = Check("Python", f"syntax: {name}")
    if r.returncode != 0:
        c.error(r.stderr.strip().splitlines()[-1], "修正語法錯誤", pf)
    else:
        c.ok()
    return c


def check_js_block(hf, idx, code, has_node):
    c = Check("JS", f"syntax: {os.path.basename(hf)}#{idx}")
    if not has_node:
        return None
    tmp = f"/tmp/_js_{os.path.basename(hf)}_{idx}.js"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(code)
        r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
        return c.ok() if r.returncode == 0 else c.error(r.stderr.strip().splitlines()[-1], "修正 JS 語法", hf)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def run():
    checks = []

    # 讀取並快取所有的 HTML 內容（只做一次，減少 I/O）
    html_files = glob.glob(os.path.join(ROOT, "*.html"))
    html_cache = {}
    for hf in html_files:
        try:
            with open(hf, encoding="utf-8") as f:
                html_cache[hf] = f.read()
        except Exception as e:
            checks.append(Check("HTML", f"讀取: {os.path.basename(hf)}").error(f"檔案讀取異常: {e}", "修復檔案權限或內容", hf))

    # ============================================================
    # 一、Python 驗證 (並行處理)
    # ============================================================
    py_files = glob.glob(os.path.join(ROOT, "scripts", "*.py"))
    with ThreadPoolExecutor() as executor:
        checks.extend(executor.map(check_py_syntax, py_files))

    # Python Linter (只跑第一個可用的)
    for tool in (["ruff", "check"], ["flake8"], ["black", "--check"]):
        exe = tool[0]
        if subprocess.run(["which", exe], capture_output=True).returncode == 0:
            r = subprocess.run([exe] + tool[1:] + py_files, capture_output=True, text=True)
            c = Check("Python", f"lint: {exe}", critical=False)
            if r.returncode != 0:
                c.warn(f"{exe} 回報問題:\n" + r.stdout.strip()[:800],
                       f"執行 {' '.join(tool)} 修正", ROOT + "/scripts")
            else:
                c.ok()
            checks.append(c)
            break

    # Python Import 快速檢查 (排除外部函式庫拼寫)
    for pf in py_files:
        c = Check("Python", f"import-ok: {os.path.basename(pf)}")
        try:
            with open(pf, encoding="utf-8") as f:
                bad = [line.strip() for line in f
                       if (line.strip().startswith("import ") or line.strip().startswith("from "))
                       and ".." in line]
            if bad:
                c.warn("疑似有相對引用的錯誤 import: " + ", ".join(bad), "修正相對 import", pf)
            else:
                c.ok()
        except Exception:
            c.ok()
        checks.append(c)

    # ============================================================
    # 二、股票資料與 Schema 驗證
    # ============================================================
    stocks_path = os.path.join(ROOT, "data", "stocks.json")
    if os.path.exists(stocks_path):
        try:
            with open(stocks_path, encoding="utf-8") as f:
                d = json.load(f)
            ss = d.get("stocks", [])

            # 代號唯一性
            c = Check("Data", "股票代號唯一")
            syms = [s.get("sym") for s in ss if s.get("sym")]
            if len(syms) != len(set(syms)):
                dups = {x for x in syms if syms.count(x) > 1}
                c.error(f"重複代號: {list(dups)[:10]}", "去重或修正資料源", stocks_path)
            else:
                c.ok(f"{len(syms)} 檔唯一")
            checks.append(c)

            # 髒值掃描（高效過濾）
            REQUIRED = {"sym", "name", "price", "open", "high", "low", "volume", "chg"}
            OHLC = {"open", "high", "low", "price", "volume"}
            etf_pattern = re.compile(r"\d{4,5}[A-Z]")

            dirty_err, dirty_warn = [], []
            for s in ss[:200]:  # 抽樣 200 檔
                sym = s.get("sym", "?")
                ohlc_null = sum(1 for k in OHLC if s.get(k) is None)
                is_etf = bool(etf_pattern.fullmatch(str(sym)))

                for k, v in s.items():
                    if k in REQUIRED and v is None:
                        if k == 'chg' and (str(sym).endswith('K') or s.get('price') is None):
                            dirty_warn.append(f"{sym}.chg=null(TDR/海外股資料源未涵蓋)")
                        elif k in OHLC and (is_etf or ohlc_null == len(OHLC)):
                            dirty_warn.append(f"{sym}.{k}=null(ETF/資料源未涵蓋)")
                        else:
                            dirty_err.append(f"{sym}.{k}=null")
                    elif k == "ind" and v is None:
                        dirty_warn.append(f"{sym}.ind=null(無產業分類，ETF/海外股正常)")
                    elif k == "market_cap":
                        if v is None:
                            dirty_warn.append(f"{sym}.market_cap=null(雲端未涵蓋)")
                        elif isinstance(v, (int, float)) and (v != v or v < 0):
                            dirty_err.append(f"{sym}.market_cap=非法值")
                    elif isinstance(v, float) and v != v:
                        dirty_err.append(f"{sym}.{k}=NaN")
                    elif v in ("", "-") and k not in ("div", "pe", "pb", "eps", "roe", "alert"):
                        dirty_err.append(f"{sym}.{k}='{v}'")

            c_dirty = Check("Data", "無髒值 (NaN/null/undefined/Infinity/空字串/非法'-')")
            if dirty_err:
                c_dirty.error("; ".join(dirty_err[:15]), "清理來源資料", stocks_path)
            elif dirty_warn:
                c_dirty.warn("; ".join(sorted(set(dirty_warn))[:8]) + "（非阻擋）", "確認資料源", stocks_path)
            else:
                c_dirty.ok("抽樣 200 檔無髒值")
            checks.append(c_dirty)

            # OHLC 合理性驗證
            c_ohlc = Check("Data", "OHLC 合理性 (H>=L, H>=O, H>=C, L<=O, L<=C, P>0, V>=0, MktCap>0)")
            bad = []
            for s in ss:
                o = safe_float(s.get("open"))
                h = safe_float(s.get("high"))
                l = safe_float(s.get("low"))
                p = safe_float(s.get("price"))
                v = safe_float(s.get("volume"))
                mc = safe_float(s.get("market_cap"))

                # 跳過無法比較的值
                if any(isinstance(x, str) for x in (o, h, l, p)):
                    continue
                if any(x is None for x in (o, h, l, p)):
                    continue

                sym = s.get('sym')
                if h < l:
                    bad.append(f"{sym}:H<L")
                elif h < o:
                    bad.append(f"{sym}:H<O")
                elif h < p:
                    bad.append(f"{sym}:H<C")
                elif l > o:
                    bad.append(f"{sym}:L>O")
                elif l > p:
                    bad.append(f"{sym}:L>C")
                elif p <= 0:
                    bad.append(f"{sym}:P<=0")
                elif isinstance(v, (int, float)) and v < 0:
                    bad.append(f"{sym}:V<0")
                elif isinstance(mc, (int, float)) and mc <= 0:
                    bad.append(f"{sym}:MktCap<=0")
                if len(bad) >= 20:
                    break

            if bad:
                c_ohlc.error("; ".join(bad[:20]), "檢查收盤資料來源", stocks_path)
            else:
                c_ohlc.ok(f"{len(ss)} 檔 OHLC 合理")
            checks.append(c_ohlc)

            # 前一交易日異常波動與 chg 單位驗證
            c_vol = Check("Data", "前日波動異常 (>20% 閾值)", critical=False)
            c_unit = Check("Data", "chg 單位合理性 (|chg|<=50 應為漲跌%)", critical=False)
            big, unit_suspect = [], []
            for s in ss:
                chg = s.get("chg")
                if isinstance(chg, (int, float)):
                    if abs(chg) > 20:
                        big.append(s.get("sym"))
                    if abs(chg) > 50:
                        unit_suspect.append(s.get("sym"))

            checks.append(c_vol.warn(f"漲跌% 超過 20%: {big[:10]}", "人工確認是否為正常除權息", stocks_path) if big else c_vol.ok("無異常波動"))
            checks.append(c_unit.error(f"|chg|>50 疑似漲跌『元』: {unit_suspect[:10]}", "fetch_data.py 的 chg 必須是漲跌%", stocks_path) if unit_suspect else c_unit.ok("chg 單位合理"))

            # JSON Schema
            c_schema = Check("JSON", "stocks.json Schema")
            req_top = {"meta", "stocks"}
            req_stock = {"sym", "name", "price", "open", "high", "low", "volume", "market_cap", "ind", "chg"}
            miss_top = req_top - set(d.keys())
            missing = [s.get("sym", "?") for s in ss if not req_stock.issubset(s.keys())]
            if miss_top:
                c_schema.error(f"缺少頂層欄位: {miss_top}", "補齊 meta/stocks", stocks_path)
            elif missing:
                c_schema.error(f"缺少股票欄位: {missing[:10]}", "補齊必要欄位", stocks_path)
            else:
                c_schema.ok(f"schema 完整 ({len(ss)} 檔)")
            checks.append(c_schema)

        except Exception as e:
            checks.append(Check("Data", "stocks.json 載入及解析").error(f"解析錯誤: {e}", "修復 JSON 格式", stocks_path))
    else:
        checks.append(Check("Data", "stocks.json 存在").error("找不到 data/stocks.json", "執行 export_db.py", ROOT + "/data"))

    # Industry Schema
    ind_path = os.path.join(ROOT, "data", "industry.json")
    c_ind = Check("JSON", "industry.json Schema")
    if os.path.exists(ind_path):
        try:
            with open(ind_path, encoding="utf-8") as f:
                d = json.load(f)
            miss = {"meta", "industry"} - set(d.keys())
            checks.append(c_ind.error(f"缺少: {miss}", "補齊", ind_path) if miss else c_ind.ok(f"{len(d['industry'])} 個產業"))
        except Exception as e:
            checks.append(c_ind.error(f"讀取錯誤: {e}", "修復 JSON 格式", ind_path))
    else:
        checks.append(c_ind.warn("找不到 industry.json", "確認是否需要生成", ind_path))

    # ============================================================
    # 四、HTML / CSS 驗證 (全快取存取，無額外 I/O)
    # ============================================================
    html_fail = 0
    for hf, src in html_cache.items():
        _h = _HealthHTMLParser()
        try:
            _h.feed(src)
            msgs = _h.report(hf)
            if msgs:
                html_fail += 1
                checks.append(Check("HTML", f"結構: {os.path.basename(hf)}").error("; ".join(msgs), "修復 HTML 結構", hf))
        except Exception as e:
            html_fail += 1
            checks.append(Check("HTML", f"解析: {os.path.basename(hf)}").error(f"解析異常: {e}", "修復 HTML", hf))
    if html_fail == 0 and html_cache:
        checks.append(Check("HTML", "結構健康檢查").ok(f"全部 {len(html_cache)} 個 HTML 通過結構檢測"))

    # CSS 驗證
    c_css = Check("CSS", "統一 Theme 變數 (var(--bg) 等)")
    no_theme = [os.path.basename(hf) for hf, src in html_cache.items()
                if not ((":root" in src and "--bg" in src)
                        or ('rel="stylesheet"' in src and 'mklab-theme.css' in src))]
    checks.append(c_css.error(f"未定義 Theme 變數: {no_theme}", "引入 mklab-theme.css 或定義 :root", ", ".join(no_theme))
                if no_theme else c_css.ok("所有頁面皆有引入 Theme"))

    c_hard = Check("CSS", "禁止硬寫核心樣式 (違反 Design Token)", critical=False)
    inline_hard = []
    for hf, src in html_cache.items():
        src_no_style = re.sub(r'<style>.*?</style>', '', src, flags=re.S)
        hards = re.findall(r'style="[^"]*(?:color:#|background:#|font-size:\d)', src_no_style)
        if hards:
            inline_hard.append(f"{os.path.basename(hf)}:{len(hards)}")
    checks.append(c_hard.warn(f"行內硬寫樣式: {inline_hard[:8]}", "改用 CSS class", ", ".join(inline_hard))
                if inline_hard else c_hard.ok("無硬寫樣式"))

    # ============================================================
    # 六、JavaScript 語法 (並行驗證)
    # ============================================================
    has_node = subprocess.run(["which", "node"], capture_output=True).returncode == 0
    if has_node:
        js_tasks = []
        for hf, src in html_cache.items():
            blocks = re.findall(r"<script>(.*?)</script>", src, re.S)
            for idx, b in enumerate(blocks):
                if b.strip():
                    js_tasks.append((hf, idx, b))

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(check_js_block, hf, idx, b, has_node) for hf, idx, b in js_tasks]
            checks.extend([f.result() for f in futures if f.result() is not None])
    else:
        checks.append(Check("JS", "node --check 可用性", critical=False).warn("node 未安裝，跳過 JS 檢查"))

    # ============================================================
    # 七、九、十：Chart, Links & Visual 驗證
    # ============================================================
    for hf in html_cache:
        base = os.path.basename(hf)
        if "kline" in base.lower() or base == "index.html" or "research" in base:
            checks.append(Check("Chart", f"圖表渲染: {base}", critical=False).manual())

    # 超連結檢查 (直接利用 html_cache)
    c_links = Check("Links", "內部連結 HTTP 200 (本地)")
    broken = []
    for hf, src in html_cache.items():
        for m in re.findall(r'href="([^"]+)"', src):
            if m.startswith(("http", "#", "javascript")) or not m:
                if not m:
                    broken.append(f"{os.path.basename(hf)}: 空白 href")
                continue
            path = m.split("#")[0]
            if path.startswith("/mklab-stock/"):
                path = path[13:]
            elif path.startswith("/"):
                path = path[1:]
            if not os.path.exists(os.path.join(ROOT, path)):
                broken.append(f"{os.path.basename(hf)} -> {m} (404)")
    checks.append(c_links.error("; ".join(broken[:15]), "修正內部超連結路徑", "") if broken else c_links.ok("內部連結正常"))

    checks.append(Check("Visual", "視覺回歸比對", critical=False).manual())

    # ============================================================
    # 報告生成與輸出
    # ============================================================
    errors = sum(1 for c in checks if c.status == "ERROR")
    warnings = sum(1 for c in checks if c.status == "WARNING")
    block = errors > 0

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_lines = [
        f"# mklab-stock QA Gate 報告",
        f"**時間**: {now}  ",
        f"**Critical ERROR**: {errors}  | **WARNING**: {warnings}  ",
        f"**最終判定**: {'🔴 BLOCK DEPLOY' if block else '🟢 ALLOW DEPLOY'}",
        "",
        "| 類別 | 項目 | 狀態 | 說明 | 修正建議 | 位置 |",
        "|------|------|------|------|----------|------|",
    ]
    for c in checks:
        report_lines.append(f"| {c.cat} | {c.name} | {c.status} | {c.detail[:120]} | {c.fix[:80]} | {c.loc} |")

    report_lines.extend(["", "## 問題摘要"])
    for c in checks:
        if c.status in ("ERROR", "WARNING"):
            report_lines.append(f"- **[{c.status}] {c.cat}/{c.name}**: {c.detail}")
            if c.fix:
                report_lines.append(f"  - 建議: {c.fix} ({c.loc})")

    report_lines.extend([
        "",
        f"## 最終判定: {'BLOCK DEPLOY' if block else 'ALLOW DEPLOY'}",
        "",
        "> 除非所有 Critical 項目皆通過，否則一律 BLOCK DEPLOY。"
    ])

    report = "\n".join(report_lines)
    out_md = os.path.join(ROOT, "data", "qa-report.md")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(report)

    print(report)

    if "--json" in sys.argv:
        try:
            jp = sys.argv[sys.argv.index("--json") + 1]
            with open(jp, "w", encoding="utf-8") as f:
                json.dump({
                    "allow_deploy": not block, "errors": errors, "warnings": warnings,
                    "checks": [{"cat": c.cat, "name": c.name, "status": c.status, "detail": c.detail} for c in checks]
                }, f, ensure_ascii=False, indent=2)
        except IndexError:
            pass

    return 1 if block else 0


if __name__ == "__main__":
    sys.exit(run())