#!/usr/bin/env python3
"""
TWSE 官方財報與公司資料自動下載（每月執行一次，official-fundamentals job）。
下載後存到 data/raw/official/，供 import_official_fundamentals.py 與 integrate_official_company.py 使用。

來源（2026-11-03 逐一實測）：
- openapi.twse.com.tw/v1/opendata/t187ap03_L → JSON，公司基本資料（產業別），約 1,099 家 ✅
- openapi.twse.com.tw/v1/opendata/t187ap45_L → JSON，股利分派情形，約 1,115 家 ✅
- openapi.twse.com.tw/v1/opendata/t187ap47_L → JSON，基金基本資料（ETF），約 275 檔 ✅
- mopsfin.twse.com.tw/opendata/t187ap06_L_ci.csv → CSV，綜合損益表 ✅
- mopsfin.twse.com.tw/opendata/t187ap07_L_ci.csv → CSV，資產負債表 ✅
  ⚠️ openapi 的 t187ap06_L / t187ap07_L 已失效（實測回傳 HTML 錯誤頁，非 JSON）→ 必須走 MOPS。
  ⚠️ MOPS 的 *_ci.csv 是「當日出表」的增量批次（實測 2026-11-03 只有 53 家，而完整快照有 1,052 家），
     所以這兩個來源採「與既有快照以公司代號 upsert 合併」，合併後才寫成 _latest.csv；
     並且明文禁止筆數變少 —— 否則一份 53 家的當日批次會直接蓋掉 1,052 家的完整快照。

安全設計：
- 每個來源先下載到記憶體並驗證（非空、含必要欄位、筆數達下限、增量來源合併後不得比原快照少）。
- 驗證通過才刪除同前綴舊檔並寫入 _latest；失敗就保留舊檔（不寫入假資料）。
- 只有「某來源完全沒有任何可用資料（新下載失敗且沒有舊快照）」才回傳 1（job 變紅），
  避免像 2026-11-02 之前那樣失敗卻仍顯示 ✅ success。
- 逐來源結果寫入 data/raw/official/_fetch_log.json，方便事後稽核（含筆數與失敗原因）。
"""
import csv, datetime as dt, glob, io, json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "raw", "official")
OPENAPI = "https://openapi.twse.com.tw/v1/opendata/"
MOPS = "https://mopsfin.twse.com.tw/opendata/"
UA = {"User-Agent": "mklab-stock/1.0 (GitHub Actions) contact: github.com/evanhsia-git/mklab-stock"}

# (輸出前綴, 來源 URL, 來源格式, 輸出格式, 必要欄位, 去重鍵, 筆數下限, 是否為當日增量批次)
SOURCES = [
    ("t187ap03_L", OPENAPI + "t187ap03_L", "json", "csv", ["公司代號", "產業別"], "公司代號", 800, False),
    ("t187ap06_L", MOPS + "t187ap06_L_ci.csv", "csv", "csv", ["公司代號", "營業收入"], "公司代號", 800, True),
    ("t187ap07_L", MOPS + "t187ap07_L_ci.csv", "csv", "csv", ["公司代號", "資產總計"], "公司代號", 800, True),
    # 前綴刻意不含 "_L"：與舊檔（t187ap45_openapi_full.json / t187ap47_openapi_full.json）同前綴，
    # 成功時才會一起被清掉。import_official_fundamentals.py 用 paths[0]（glob 第一個符合檔），
    # 若新舊檔並存會隨機讀到過期的那個（2026-11-03 實測）。
    ("t187ap45", OPENAPI + "t187ap45_L", "json", "json", ["公司代號", "股利年度"], "公司代號", 500, False),
    ("t187ap47", OPENAPI + "t187ap47_L", "json", "json", ["基金代號"], "基金代號", 100, False),
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
    """把當日增量批次併入既有快照：同代號以新資料覆蓋，其餘保留。回傳 (欄位, 合併後列, 原筆數)。"""
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


def main():
    os.makedirs(OUT, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat()
    report, missing = [], []
    for prefix, url, src_fmt, out_fmt, required, key_field, floor, incremental in SOURCES:
        label = "當日增量批次，合併既有快照" if incremental else "全量"
        entry: dict = {"prefix": prefix, "url": url, "mode": label, "status": ""}
        try:
            keys, rows = parse(download(url), src_fmt)
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
            log(f"✅ {prefix}：{len(rows)} 筆（{label}）→ {name}")
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
    if missing:
        log(f"❌ 完全沒有資料的來源：{', '.join(missing)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
