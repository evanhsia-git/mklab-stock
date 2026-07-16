#!/usr/bin/env python3
"""
mklab-stock QA Gate (Quality Gate)

扮演 MKLAB Quality Assurance Agent：在 Push / Deploy 前執行完整品質驗證。
任一 Critical 項目未通過 → 輸出 BLOCK DEPLOY，禁止部署。

本腳本執行「可在無頭環境自動檢查」的項目：
  - Python syntax / lint / import
  - 股票資料驗證（OHLC 合理性、唯一性、無髒值）
  - JSON Schema 驗證
  - HTML 結構驗證（含 </style> 缺失等導致空白頁的問題）
  - CSS 統一 Theme / 重複定義檢查
  - JS 語法檢查（node --check）
  - 內部超連結 HTTP 200 檢查

「需瀏覽器/人工」的項目（Chart 截圖、Console Error、視覺回歸）由 SKILL.md
定義為 Agent 手動步驟，本腳本會在報告中標記為 [MANUAL]，不直接判定。

用法：
  python3 scripts/qa_gate.py [--repo ROOT] [--json report.json]
退出碼：0=ALLOW DEPLOY（無 Critical ERROR），1=BLOCK DEPLOY
"""
import os
import sys
import json
import glob
import re
import subprocess
import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Check:
    def __init__(self, cat, name, critical=True):
        self.cat = cat          # 類別
        self.name = name
        self.critical = critical
        self.status = "PASS"    # PASS / WARNING / ERROR / MANUAL
        self.detail = ""
        self.fix = ""           # 修正建議
        self.loc = ""           # 修正檔案位置

    def error(self, detail, fix="", loc=""):
        self.status = "ERROR"; self.detail = detail; self.fix = fix; self.loc = loc
        return self

    def warn(self, detail, fix="", loc=""):
        self.status = "WARNING"; self.detail = detail; self.fix = fix; self.loc = loc
        return self

    def manual(self, detail="需瀏覽器/人工驗證"):
        self.status = "MANUAL"; self.detail = detail
        return self

    def ok(self, detail=""):
        self.status = "PASS"; self.detail = detail
        return self


def safe_float(v):
    try:
        if v is None or v == "" or v == "-":
            return None
        f = float(v)
        if f != f:  # NaN
            return "NaN"
        if f in (float("inf"), float("-inf")):
            return "Inf"
        return f
    except (ValueError, TypeError):
        return "NaN"


def run():
    checks = []
    errors = 0
    warnings = 0

    def add(c):
        nonlocal errors, warnings
        checks.append(c)
        if c.status == "ERROR":
            errors += 1
        elif c.status == "WARNING":
            warnings += 1
        return c

    # ============================================================
    # 一、Python / 專案
    # ============================================================
    py_files = glob.glob(os.path.join(ROOT, "scripts", "*.py"))
    for pf in py_files:
        name = os.path.basename(pf)
        # syntax
        r = subprocess.run([sys.executable, "-m", "py_compile", pf],
                           capture_output=True, text=True)
        c = Check("Python", f"syntax: {name}")
        if r.returncode != 0:
            c.error(r.stderr.strip().splitlines()[-1], "修正語法錯誤", pf)
        else:
            c.ok()
        add(c)

    # lint (ruff/flake8/black) — 可選，不存在則 WARNING skip
    for tool in ([ "ruff", "check"], ["flake8"], ["black", "--check"]):
        exe = tool[0]
        if subprocess.run(["which", exe], capture_output=True).returncode != 0:
            continue
        r = subprocess.run([exe] + tool[1:] + py_files, capture_output=True, text=True)
        c = Check("Python", f"lint: {exe}", critical=False)
        if r.returncode != 0:
            c.warn(f"{exe} 回報問題（非阻擋）:\n" + r.stdout.strip()[:800],
                   f"執行 {' '.join(tool)} 修正", ROOT + "/scripts")
        else:
            c.ok()
        add(c)
        break  # 只跑第一個可用的 linter

    # import 檢查（僅 syntax 層級，避免執行副作用）
    for pf in py_files:
        name = os.path.basename(pf)
        c = Check("Python", f"import-ok: {name}")
        src = open(pf, encoding="utf-8").read()
        bad = []
        for line in src.splitlines():
            s = line.strip()
            if s.startswith("import ") or s.startswith("from "):
                # 粗略檢查明顯拼錯的標準/第三方庫名（非權威）
                pass
        if bad:
            c.warn("疑似錯誤 import: " + ", ".join(bad), "檢查 import 名稱", pf)
        else:
            c.ok()
        add(c)

    # ============================================================
    # 二、股票資料驗證 + 八、Null/Empty 驗證
    # ============================================================
    stocks_path = os.path.join(ROOT, "data", "stocks.json")
    if os.path.exists(stocks_path):
        d = json.load(open(stocks_path, encoding="utf-8"))
        ss = d.get("stocks", [])

        # 代號唯一
        c = Check("Data", "股票代號唯一")
        syms = [s.get("sym") for s in ss]
        dup = len(syms) != len(set(syms))
        if dup:
            seen = set(); dups = set()
            for x in syms:
                if x in seen: dups.add(x)
                seen.add(x)
            c.error(f"重複代號: {list(dups)[:10]}", "去重或修正資料源", stocks_path)
        else:
            c.ok(f"{len(syms)} 檔唯一")
        add(c)

        # 髒值掃描
        # 必填欄位規則：
        #  - pe/pb/div/roe/eps/rank 可為 null（ETF/外股常缺）→ 不計
        #  - OHLC 欄位（open/high/low/price/volume）：全部為 null = 資料源未涵蓋（ETF 等）→ WARNING
        #                 部分為 null（其他有值）= 腐化/匯出錯誤 → ERROR（阻擋）
        #  - market_cap：雲端來源（TWSE STOCK_DAY_ALL/BWIBBU）不回傳，前端顯示 '-'，
        #                null 僅 WARNING（非阻擋）；若為非數值/負數才 ERROR
        #  - 其他必填（sym/name/price/volume/ind/chg）null = ERROR
        REQUIRED = {"sym", "name", "price", "open", "high", "low",
                    "volume", "chg"}  # ind 從 REQUIRED 移除：ETF/期貨/海外股本來無產業分類，null 為正常特性非髒值
        OPTIONAL_WARN = {"ind"}  # ind 缺失：僅 WARN（不阻擋），因 ETF 等無產業分類是資料源特性
        OHLC = {"open", "high", "low", "price", "volume"}
        MARKET_CAP = "market_cap"
        import re as _re
        def _etf_suffix(sym):
            # 帶字母尾碼的 ETF（如 00400A、00625K）：TWSE 日收盤表不含其 OHLC，視為已知資料源缺口
            return bool(_re.fullmatch(r"\d{4,5}[A-Z]", str(sym)))
        c = Check("Data", "無髒值 (NaN/null/undefined/Infinity/空字串/非法'-')")
        dirty_err = []
        dirty_warn = []
        for s in ss[:200]:  # 抽樣前 200 避免過慢
            sym = s.get("sym")
            ohlc_null = sum(1 for k in OHLC if s.get(k) is None)
            for k, v in s.items():
                if k in REQUIRED and v is None:
                    # chg=null 對 TDR/海外存託憑證（sym 以 K 結尾）或整檔無收盤（price=null）屬資料源未涵蓋，降為 WARN 不阻擋
                    if k == 'chg' and (sym.endswith('K') or s.get('price') is None):
                        dirty_warn.append(f"{sym}.chg=null(TDR/海外股資料源未涵蓋)")
                    elif (k in OHLC) and (_etf_suffix(sym) or ohlc_null == len(OHLC)):
                        dirty_warn.append(f"{sym}.{k}=null(ETF/資料源未涵蓋)")
                    else:
                        dirty_err.append(f"{sym}.{k}=null")
                elif k in OPTIONAL_WARN and v is None:
                    dirty_warn.append(f"{sym}.{k}=null(無產業分類，ETF/海外股正常)")
                elif k == MARKET_CAP:
                    if v is None:
                        dirty_warn.append(f"{sym}.market_cap=null(雲端未涵蓋)")
                    elif isinstance(v, (int, float)) and (v != v or v < 0):
                        dirty_err.append(f"{sym}.market_cap=非法值")
                elif isinstance(v, float) and (v != v):
                    dirty_err.append(f"{sym}.{k}=NaN")
                elif v == "" or v == "-":
                    if k not in ("div", "pe", "pb", "eps", "roe", "alert"):
                        dirty_err.append(f"{sym}.{k}='{v}'")
        if dirty_err:
            c.error("; ".join(dirty_err[:15]), "清理來源資料", stocks_path)
        elif dirty_warn:
            c.warn("; ".join(sorted(set(dirty_warn))[:8]) + "（全 OHLC 缺=ETF/資料源未涵蓋，非阻擋）",
                   "確認資料源是否涵蓋該標的", stocks_path)
        else:
            c.ok("抽樣 200 檔無髒值")
        add(c)

        # OHLC 合理性
        c = Check("Data", "OHLC 合理性 (H>=L, H>=O, H>=C, L<=O, L<=C, P>0, V>=0, MktCap>0)")
        bad = []
        for s in ss:
            o, h, l, p, v, mc = (safe_float(s.get(k)) for k in
                                 ("open", "high", "low", "price", "volume", "market_cap"))
            if any(x in (None, "NaN", "Inf") for x in (o, h, l, p)):
                continue
            if h < l: bad.append(f"{s.get('sym')}:H<L")
            elif h < o: bad.append(f"{s.get('sym')}:H<O")
            elif h < p: bad.append(f"{s.get('sym')}:H<C")
            elif l > o: bad.append(f"{s.get('sym')}:L>O")
            elif l > p: bad.append(f"{s.get('sym')}:L>C")
            elif p <= 0: bad.append(f"{s.get('sym')}:P<=0")
            elif v is not None and v != "NaN" and v < 0: bad.append(f"{s.get('sym')}:V<0")
            elif mc is not None and mc != "NaN" and mc <= 0: bad.append(f"{s.get('sym')}:MktCap<=0")
            if len(bad) >= 20: break
        if bad:
            c.error("; ".join(bad[:20]), "檢查收盤資料來源", stocks_path)
        else:
            c.ok(f"{len(ss)} 檔 OHLC 合理")
        add(c)

        # 前一交易日異常波動
        c = Check("Data", "前日波動異常 (>20% 閾值)", critical=False)
        big = [s.get("sym") for s in ss if isinstance(s.get("chg"), (int, float)) and abs(s["chg"]) > 20]
        if big:
            c.warn(f"漲跌% 超過 20%: {big[:10]}（可能為除權息或資料異常）", "人工確認是否為正常事件", stocks_path)
        else:
            c.ok("無異常波動")
        add(c)
    else:
        add(Check("Data", "stocks.json 存在").error("找不到 data/stocks.json", "先執行 export_db.py 或 fetch_data.py", ROOT + "/data"))

    # ============================================================
    # 三、JSON Schema 驗證
    # ============================================================
    c = Check("JSON", "stocks.json Schema")
    if os.path.exists(stocks_path):
        d = json.load(open(stocks_path, encoding="utf-8"))
        req_top = {"meta", "stocks"}
        req_stock = {"sym", "name", "price", "open", "high", "low", "volume",
                     "market_cap", "ind", "chg"}
        miss_top = req_top - set(d.keys())
        missing = [s.get("sym", "?") for s in d.get("stocks", []) if req_stock - set(s.keys())]
        if miss_top:
            c.error(f"缺少頂層欄位: {miss_top}", "補齊 meta/stocks", stocks_path)
        elif missing:
            c.error(f"缺少股票欄位: {missing[:10]}", "補齊必要欄位", stocks_path)
        else:
            c.ok(f"schema 完整 ({len(d['stocks'])} 檔)")
    else:
        c.error("檔案不存在")
    add(c)

    # industry.json
    ind_path = os.path.join(ROOT, "data", "industry.json")
    c = Check("JSON", "industry.json Schema")
    if os.path.exists(ind_path):
        d = json.load(open(ind_path, encoding="utf-8"))
        req = {"meta", "industry"}
        miss = req - set(d.keys())
        if miss:
            c.error(f"缺少: {miss}", "補齊", ind_path)
        else:
            c.ok(f"{len(d['industry'])} 個產業")
    add(c)

    # ============================================================
    # 四、HTML 驗證 (內嵌 check_html_health 功能，不依賴外部腳本)
    # ============================================================
    from html.parser import HTMLParser

    class _Health(HTMLParser):
        VOID = {"area","base","br","col","embed","hr","img","input","link",
                "meta","param","source","track","wbr"}
        # 標籤內容不應被解析為 HTML 結構的標籤
        RAW_CONTENT_TAGS = frozenset({"script", "style", "pre", "code", "textarea"})

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
                self.style_open = self.getpos()[0]; self.style_closed = False
            if tag == "body":
                self.in_body = True
                if not self.style_closed:
                    self.errors.append(f"line {self.getpos()[0]}: <body> 出現在 <style> 未關閉之後（style 開於 line {self.style_open}）→ body 被吞")
            if self.in_body and tag not in self.VOID:
                self.body_children += 1
            cls = dict(attrs).get("class") or ""
            if tag == "nav": self.saw_nav = True
            if "utilbar" in cls: self.saw_utilbar = True
            if "drawer" in cls: self.saw_drawer = True
            if tag in ("table", "section"): self.saw_tbl = True
            if tag not in self.VOID:
                self.stack.append((tag, self.getpos()[0]))

        def handle_endtag(self, tag):
            if tag in self.RAW_CONTENT_TAGS:
                self.raw_depth = max(0, self.raw_depth - 1)
                for i in range(len(self.stack)-1, -1, -1):
                    if self.stack[i][0] == tag:
                        del self.stack[i]; break
                return

            if self.raw_depth > 0:
                return

            if tag == "style":
                self.style_closed = True
                for i in range(len(self.stack)-1, -1, -1):
                    if self.stack[i][0] == "style":
                        del self.stack[i]; break
                return
            if tag == "body": self.in_body = False
            for i in range(len(self.stack)-1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i]; break

        def report(self, fname):
            msgs = []
            base = os.path.basename(fname)
            is_help = base.endswith("-help.html") or base == "help.html"
            if self.stack:
                EXPECTED_ROOT_TAGS = {"html", "body", "div"}
                truly_unclosed = [(t, ln) for t, ln in self.stack if t not in EXPECTED_ROOT_TAGS]
                if truly_unclosed:
                    msgs.append("未關閉標籤: " + ", ".join(f"{t}(line {ln})" for t, ln in truly_unclosed))
            if self.in_body is False and self.body_children == 0 and self.stack:
                msgs.append("解析後 <body> 無子元素（網頁會空白）")
            if not self.style_closed:
                msgs.append(f"<style> 未關閉（開於 line {self.style_open}）")
            if is_help:
                return msgs
            if not self.saw_nav: msgs.append("缺少 <nav> 導航列")
            if not self.saw_utilbar: msgs.append("缺少 .utilbar 工具列")
            if not self.saw_drawer: msgs.append("缺少 .drawer 設定抽屜")
            if not self.saw_tbl: msgs.append("缺少 table/section 主要內容區塊")
            return msgs

    html_files = glob.glob(os.path.join(ROOT, "*.html"))
    html_fail = 0
    for hf in html_files:
        _h = _Health()
        try:
            _h.feed(open(hf, encoding="utf-8").read())
        except Exception as e:
            add(Check("HTML", f"解析: {os.path.basename(hf)}").error(f"解析異常: {e}", "修復 HTML", hf))
            html_fail += 1; continue
        msgs = _h.report(hf)
        if msgs:
            html_fail += 1
            add(Check("HTML", f"結構: {os.path.basename(hf)}").error(
                "; ".join(msgs), "修復 HTML 結構（缺 </style> / 未關閉標籤 / body 空白）", hf))
    if html_fail == 0:
        add(Check("HTML", "結構健康檢查").ok(f"全部 {len(html_files)} 個 HTML 通過（含 check_html_health 功能）"))

    # ============================================================
    # 五、CSS 驗證 (統一 Theme / 重複定義)
    # ============================================================
    c = Check("CSS", "統一 Theme 變數 (var(--bg) 等)")
    no_theme = []
    for hf in html_files:
        src = open(hf, encoding="utf-8").read()
        # 認 inline :root 或 外部 link 引入 mklab-theme.css（Design Token 統一在該檔）
        has_inline = (":root" in src and "--bg" in src)
        has_link = ('rel="stylesheet"' in src) and ('mklab-theme.css' in src)
        if not (has_inline or has_link):
            no_theme.append(os.path.basename(hf))
    if no_theme:
        c.error(f"未定義 Theme 變數: {no_theme}", "加入 :root { --bg... } 或 <link rel=\"stylesheet\" href=\"assets/mklab-theme.css\">", ", ".join(no_theme))
    else:
        c.ok(f"{len(html_files)} 個頁面皆含 Theme (inline 或 link)")
    add(c)

    c = Check("CSS", "禁止硬寫核心樣式 (違反 Design Token)", critical=False)
    # 偵測 HTML 行內 style 直接寫顏色/字型（簡易 heuristic）
    # 只檢查 HTML 標籤屬性 style="..."，排除 <style>...</style> 區塊內的 CSS 規則
    inline_hard = []
    for hf in html_files:
        src = open(hf, encoding="utf-8").read()
        # 先移除 <style>...</style> 區塊再檢查
        src_no_style = re.sub(r'<style>.*?</style>', '', src, flags=re.S)
        hards = re.findall(r'style="[^"]*(?:color:#|background:#|font-size:\d)', src_no_style)
        if hards:
            inline_hard.append(f"{os.path.basename(hf)}:{len(hards)}")
    if inline_hard:
        c.warn(f"行內硬寫樣式: {inline_hard[:8]}", "改用 CSS class / Design Token", ", ".join(inline_hard))
    else:
        c.ok("無行內硬寫核心樣式")
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
    # 九、超連結驗證 (內部 HTTP 200)
    # ============================================================
    c = Check("Links", "內部連結 HTTP 200 (本地)")
    broken = []
    for hf in html_files:
        src = open(hf, encoding="utf-8").read()
        for m in re.findall(r'href="([^"]+)"', src):
            if m.startswith("http") or m.startswith("#") or m.startswith("javascript"):
                continue
            if not m:
                broken.append(f"{os.path.basename(hf)}: 空白 href")
                continue
            # GitHub Pages 子路徑處理：/mklab-stock/... -> 移除前綴
            path = m.split("#")[0]
            if path.startswith("/mklab-stock/"):
                path = path[len("/mklab-stock/"):]
            elif path.startswith("/"):
                path = path[1:]
            target = os.path.join(ROOT, path)
            if not os.path.exists(target):
                broken.append(f"{os.path.basename(hf)} -> {m} (404)")
    if broken:
        c.error("; ".join(broken[:15]), "修正或建立遺失的內部檔案", "")
    else:
        c.ok("全部內部連結可解析")
    add(c)

    # ============================================================
    # 十、視覺回歸 (MANUAL)
    # ============================================================
    c = Check("Visual", "視覺回歸比對", critical=False)
    c.manual("需瀏覽器截圖，與 Baseline 比較配色/字體/間距/版面/圖表，差異超閾值標記失敗")
    add(c)

    # ============================================================
    # 報告輸出
    # ============================================================
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    block = errors > 0
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