#!/usr/bin/env python3
"""
TWSE 官方財報與公司資料自動下載（每月執行一次，official-fundamentals job）。
下載後存到 data/raw/official/，供 import_official_fundamentals.py 與 integrate_official_company.py 使用。

來源（2026-11-03 逐一實測）：
- openapi.twse.com.tw/v1/opendata/t187ap03_L → JSON，公司基本資料（產業別），約 1,099 家 ✅
- openapi.twse.com.tw/v1/opendata/t187ap45_L → JSON，股利分派情形，約 1,239 家 ✅
- openapi.twse.com.tw/v1/opendata/t187ap47_L → JSON，基金基本資料（ETF），約 276 檔 ✅
- 綜合損益表 t187ap06_L_* / 資產負債表 t187ap07_L_* → JSON，⚠️ 官方「按產業拆檔」，必須全部抓：
    ci（一般業）、basi、bd（銀行）、fh（金控）、ins（保險）、mim（其他）
    只抓 ci 會讓金融保險類（約 31 檔）永遠沒有官方財報。未開始申報的產業檔會回傳
    「只有出表日期、公司代號空白」的空殼列，逐列過濾空代號即可。
  ⚠️ 無後綴的 t187ap06_L / t187ap07_L 已失效（實測回傳 1KB HTML 錯誤頁，非 JSON），不可使用。
  ⚠️ 每個產業檔只包含「該期別已申報」的公司（實測 2026-11-03 一般業僅 53 家，而完整快照 1,052 家），
     所以這兩個來源採「與既有快照以公司代號 upsert 合併」，合併後才寫成 _latest.csv；
     並且明文禁止筆數變少 —— 否則一份 53 家的當期批次會直接蓋掉 1,052 家的完整快照。
     申報期結束後各產業檔會回到「上一完整季度」的全量（實測 2026-10-30 一般業 1,052 家），
     屆時每月排程即可補齊全部公司。

安全設計：
- 每個來源先下載到記憶體並驗證（非空、含必要欄位、筆數達下限、增量來源合併後不得比原快照少）。
- 驗證通過才刪除同前綴舊檔並寫入 _latest；失敗就保留舊檔（不寫入假資料）。
- 只有「某來源完全沒有任何可用資料（新下載失敗且沒有舊快照）」才回傳 1（job 變紅），
  避免像 2026-11-02 之前那樣失敗卻仍顯示 ✅ success。
- 逐來源結果（含各子檔筆數）寫入 data/raw/official/_fetch_log.json，方便事後稽核。
"""
import csv, datetime as dt, glob, io, json, os, re, sys, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "raw", "official")
OPENAPI = "https://openapi.twse.com.tw/v1/opendata/"
MOPS_OLD = "https://mopsov.twse.com.tw/mops/web/"
UA = {"User-Agent": "mklab-stock/1.0 (GitHub Actions) contact: github.com/evanhsia-git/mklab-stock"}

# 官方財報按產業拆檔，必須全抓（缺一類就會有一整個產業沒有官方財報）
INDUSTRIES = ["ci", "basi", "bd", "fh", "ins", "mim"]

# (輸出前綴, 來源 URL 清單, 來源格式, 輸出格式, 必要欄位, 去重鍵, 筆數下限, 是否為當期增量批次)
SOURCES = [
    ("t187ap03_L", [OPENAPI + "t187ap03_L"], "json", "csv", ["公司代號", "產業別"], "公司代號", 800, False),
    ("t187ap06_L", [OPENAPI + f"t187ap06_L_{s}" for s in INDUSTRIES], "json", "csv",
     ["公司代號", "營業收入"], "公司代號", 800, True),
    ("t187ap07_L", [OPENAPI + f"t187ap07_L_{s}" for s in INDUSTRIES], "json", "csv",
     ["公司代號", "資產總計"], "公司代號", 800, True),
    # 前綴刻意不含 "_L"：與舊檔（t187ap45_openapi_full.json / t187ap47_openapi_full.json）同前綴，
    # 成功時才會一起被清掉。import_official_fundamentals.py 用 paths[0]（glob 第一個符合檔），
    # 若新舊檔並存會隨機讀到過期的那個（2026-11-03 實測）。
    ("t187ap45", [OPENAPI + "t187ap45_L"], "json", "json", ["公司代號", "股利年度"], "公司代號", 500, False),
    ("t187ap47", [OPENAPI + "t187ap47_L"], "json", "json", ["基金代號"], "基金代號", 100, False),
]


def log(m):
    print(f"[official] {m}", flush=True)


def download(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()


def parse(data, fmt):
    """回傳 (欄位順序, [dict, ...])；文件必須是 JSON 陣列或 CSV（utf-8-sig）。"""
    text = data.decode("utf-8-sig", errors="replace")
    if fmt == "json":
        rows = json.loads(text)
        if not isinstance(rows, list) or not rows:
            raise ValueError("回傳不是非空列表")
        keys = []
        for r in rows:
            for k in r:
                if k not in keys:
                    keys.append(k)
        return keys, [dict(r) for r in rows]
    rd = list(csv.DictReader(io.StringIO(text)))
    if not rd:
        raise ValueError("CSV 沒有資料列")
    return list(rd[0].keys()), rd


def validate(keys, rows, required, floor, label):
    if not rows:
        raise ValueError("沒有資料列")
    missing = [k for k in required if k not in keys]
    if missing:
        raise ValueError(f"缺少必要欄位：{missing}（實際欄位前 8 個：{list(keys)[:8]}）")
    if len(rows) < floor:
        raise ValueError(f"筆數 {len(rows)} 低於下限 {floor}（{label}）")


def existing_snapshot(prefix, ext):
    """既有快照：優先用 _latest，否則取最新修改的同前綴檔案。"""
    exact = os.path.join(OUT, f"{prefix}_latest.{ext}")
    if os.path.exists(exact):
        return exact
    cands = [p for p in glob.glob(os.path.join(OUT, f"{prefix}*.{ext}")) if os.path.basename(p) != "_fetch_log.json"]
    return max(cands, key=os.path.getmtime) if cands else None


def upsert(keys, rows, base_path, key_field):
    """把當期增量批次併入既有快照：同代號以新資料覆蓋，其餘保留。回傳 (欄位, 合併後列, 原筆數)。"""
    if not base_path:
        return keys, rows, 0
    bkeys, brows = parse(open(base_path, "rb").read(), os.path.splitext(base_path)[1].lstrip("."))
    merged = {str(r.get(key_field, "")).strip(): r for r in brows if str(r.get(key_field, "")).strip()}
    for r in rows:
        k = str(r.get(key_field, "")).strip()
        if k:
            merged[k] = {**merged.get(k, {}), **r}
    okeys = bkeys + [k for k in keys if k not in bkeys]
    return okeys, list(merged.values()), len(brows)


def dump(keys, rows, out_format):
    if out_format == "json":
        return json.dumps(rows, ensure_ascii=False).encode("utf-8")
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=keys, extrasaction="ignore", restval="")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in keys})
    return buf.getvalue().encode("utf-8-sig")


def fetch_all(urls, src_fmt, key_field):
    """抓多個子檔並聯集（官方財報按產業拆檔）；回傳 (欄位, 列, 各子檔筆數)。

    只併入「真的有人申報」的子檔：沒有資料的產業檔會回傳一列只有出表日期、公司代號空白的空殼，
    而且各產業的欄位集不同（一般業 33 欄、金控 61 欄…）。若把空殼檔的欄位也併進來，
    整份檔案的欄位數會從 33 膨脹到 57 以上全是空欄，徒增檔案大小與同名欄位互撞的風險。
    """
    keys, rows, parts = [], [], []
    for u in urls:
        k2, r2 = parse(download(u), src_fmt)
        kept = [r for r in r2 if str(r.get(key_field, "") or "").strip()]  # 濾掉空殼列
        parts.append({"url": u, "rows": len(kept)})
        if not kept:
            continue
        for k in k2:
            if k not in keys:
                keys.append(k)
        rows.extend(kept)
    return keys, rows, parts


# ── MOPS 彙總表（Piotroski 台股層輸入：去年同期對照＋現金流量兩期；2026-11-24）──
# TWSE OpenAPI（t187ap06/07）無期別參數、無現金流量表；MOPS 舊版彙總表（t163sb04/05/20）
# 支援 year/season POST，是「去年同期」的唯一官方批次源。解析後健全性不過→缺檔，
# import 層如實 null（缺值不補值；MOPS 抓取失敗不擋 job——這是增強層，不是主源）。

MOPS_FLOOR = 800  # 彙總表筆數下限（實測 1,050~1,088 家）


def detect_current_period():
    """從 t187ap06_L_latest.csv 快照讀最新期（年度/季別眾數）→ (民國年, 季) ints。"""
    path = os.path.join(OUT, "t187ap06_L_latest.csv")
    rd = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    cnt = {}
    for r in rd:
        y, q = (r.get("年度") or "").strip(), (r.get("季別") or "").strip()
        if y and q:
            cnt[(y, q)] = cnt.get((y, q), 0) + 1
    if not cnt:
        raise ValueError("t187ap06_L_latest.csv 無年度/季別可偵測")
    (y, q), _ = max(cnt.items(), key=lambda kv: kv[1])
    return int(y), int(q)


def parse_mops_summary(html):
    """MOPS 彙總表 HTML → (欄位順序, [dict,...])。取「含最多 4 位代號列」的 table，
    表頭 tr.tblHead 的 th 與資料列 td 對齊（td[0]=公司代號、td[1]=名稱、td[2:]=數值）。"""
    tables = re.findall(r"<table class='hasBorder'.*?</table>", html, re.S)
    best, best_n, best_headers = None, 0, None
    for tbl in tables:
        m = re.search(r"<tr class='tblHead'>(.*?)</tr>", tbl, re.S)
        if not m:
            continue
        headers = [re.sub(r"[\s\xa0]+", "", x.replace("<br>", "")) for x in re.findall(r"<th[^>]*>(.*?)</th>", m.group(1), re.S)]
        n = len(re.findall(r"<td[^>]*>\s*\d{4}[A-Z]{0,2}\s*</td>", tbl))
        if n > best_n:
            best, best_n, best_headers = tbl, n, headers
    if best is None:
        raise ValueError("頁面無 hasBorder 資料表（MOPS 版面變更？）")
    keys = [k for k in best_headers if k]
    rows = []
    for tr in re.findall(r"<tr class='(?:even|odd)'>(.*?)</tr>", best, re.S):
        tds = [re.sub(r"[\s\xa0]+", "", x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if not tds or not re.fullmatch(r"\d{4}[A-Z]{0,2}", tds[0]):
            continue
        rec = {"公司代號": tds[0]}
        for i, h in enumerate(best_headers):
            if i >= 2 and h and i < len(tds):
                rec[h] = tds[i]  # 原始字串（千分位/--），import 層 num() 統一處理
        rows.append(rec)
    if not rows:
        raise ValueError("資料表無有效公司列")
    return keys, rows


def fetch_mops_piotroski_inputs():
    """抓 Piotroski 台股層輸入（4 份，失敗僅 warn 不擋 job）：
    - mops-t163sb04_prevyear.csv：去年同期損益（營業收入/毛利淨額/本期淨利）
    - mops-t163sb05_prevyear.csv：去年同期資產負債（資產總計/負債總計/流動資產/流動負債/股本）
    - mops-t163sb20_latest.csv：本期現金流量（營業活動之淨現金流入（流出））
    - mops-t163sb20_prevyear.csv：去年同期現金流量
    """
    y, q = detect_current_period()
    py = y - 1
    plan = [
        ("t163sb04", py, q, "mops-t163sb04_prevyear.csv", ["營業收入", "營業毛利（毛損）淨額", "本期淨利（淨損）"]),
        ("t163sb05", py, q, "mops-t163sb05_prevyear.csv", ["資產總計", "負債總計", "流動資產", "流動負債", "股本"]),
        ("t163sb20", y, q, "mops-t163sb20_latest.csv", ["營業活動之淨現金流入（流出）"]),
        ("t163sb20", py, q, "mops-t163sb20_prevyear.csv", ["營業活動之淨現金流入（流出）"]),
    ]
    got = 0
    for tag, yy, qq, fname, needed in plan:
        label = f"{tag} {yy}Q{qq}"
        try:
            form = {"encodeURIComponent": "1", "step": "1", "firstin": "1", "off": "1",
                    "year": str(yy), "season": str(qq), "TYPEK": "sii"}
            req = urllib.request.Request(MOPS_OLD + tag,
                                         data=urllib.parse.urlencode(form).encode(),
                                         headers={**UA, "Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req, timeout=120) as r:
                html = r.read().decode("utf-8", errors="replace")
            keys, rows = parse_mops_summary(html)
            missing_cols = [c for c in needed if c not in keys]
            if missing_cols:
                raise ValueError(f"表頭缺欄位 {missing_cols}（實際 th 前 12：{keys[:12]}）")
            if len(rows) < MOPS_FLOOR:
                raise ValueError(f"筆數 {len(rows)} < {MOPS_FLOOR}")
            # 期別欄（民國）寫進每列——import 層的「去年同期鎖」據此驗證，不靠檔名猜
            for r in rows:
                r["報表年度"], r["報表季別"] = str(yy), str(qq)
            keys = keys + ["報表年度", "報表季別"]
            name = os.path.join(OUT, fname)
            for old in glob.glob(os.path.join(OUT, fname.replace(".csv", "*"))):
                os.remove(old)
            with open(name, "wb") as f:
                f.write(dump(keys, rows, "csv"))
            got += 1
            log(f"✅ MOPS {label}：{len(rows)} 筆 → {fname}")
        except Exception as e:
            log(f"⚠️ MOPS {label} 失敗（Piotroski 對應欄位將如實 null）：{type(e).__name__}: {str(e)[:80]}")
    return got


def main():
    os.makedirs(OUT, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat()
    report, missing = [], []
    for prefix, urls, src_fmt, out_fmt, required, key_field, floor, incremental in SOURCES:
        label = "當期增量批次，合併既有快照" if incremental else "全量"
        entry: dict = {"prefix": prefix, "urls": urls, "mode": label, "status": ""}
        try:
            keys, rows, parts = fetch_all(urls, src_fmt, key_field)
            entry["parts"] = parts
            if not rows:
                raise ValueError(f"全部 {len(urls)} 個子檔都是空的（無有效代號）")
            base = existing_snapshot(prefix, out_fmt) if incremental else None
            if incremental:
                keys, rows, base_n = upsert(keys, rows, base, key_field)
                entry["base_rows"] = base_n
                if base_n and len(rows) < base_n:
                    raise ValueError(f"合併後筆數 {len(rows)} 少於原快照 {base_n}，拒絕寫入（避免覆蓋完整快照）")
            else:
                entry["base_rows"] = 0
            validate(keys, rows, required, floor, label)
            name = f"{prefix}_latest.{out_fmt}"
            for old in glob.glob(os.path.join(OUT, f"{prefix}*.{out_fmt}")):
                os.remove(old)  # 驗證通過才刪舊檔，避免 import 時 glob 取到過期檔案
            with open(os.path.join(OUT, name), "wb") as f:
                f.write(dump(keys, rows, out_fmt))
            entry.update(status="ok", rows=len(rows), file=name)
            log(f"✅ {prefix}：{len(rows)} 筆（{label}，子檔 {len(parts)} 個）→ {name}")
        except Exception as e:
            old = existing_snapshot(prefix, out_fmt)
            entry.update(status="failed", error=f"{type(e).__name__}: {e}",
                         kept=os.path.basename(old) if old else None)
            if old:
                log(f"⚠️ {prefix} 失敗，保留既有檔 {os.path.basename(old)}：{entry['error']}")
            else:
                missing.append(prefix)
                log(f"❌ {prefix} 失敗且沒有任何既有檔 → 這個來源完全沒有資料：{entry['error']}")
        report.append(entry)
    json.dump({"fetched_at": stamp, "sources": report},
              open(os.path.join(OUT, "_fetch_log.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    ok_n = sum(1 for e in report if e["status"] == "ok")
    log(f"完成：成功 {ok_n}/{len(SOURCES)}")
    # Piotroski 台股層輸入（增強層：失敗僅 warn，缺檔→import 如實 null，不影響退出碼）
    try:
        got = fetch_mops_piotroski_inputs()
        log(f"Piotroski 輸入：{got}/4 份 MOPS 彙總表抓取成功")
    except Exception as e:
        log(f"⚠️ Piotroski 輸入層整體失敗（不擋 job）：{type(e).__name__}: {str(e)[:80]}")
    if missing:
        log(f"❌ 完全沒有資料的來源：{', '.join(missing)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
