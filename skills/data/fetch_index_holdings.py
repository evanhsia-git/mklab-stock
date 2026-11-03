#!/usr/bin/env python3
"""
四大指數替代 ETF 的持股自動抓取（GitHub Actions 每日執行）。
流程：依 data/index-proxy.json 逐一嘗試來源 → 解析 → 驗證（檔數範圍、權重加總 90~101%、代號格式）
→ 通過才寫入 data/index-holdings/{基金}.json；任何一步失敗都保留上一版，並在日誌中說明原因。
不寫入假資料。手動檔（manual_upload:）存在時才會使用。
exit code：只要有任一基金「所有來源皆失敗且沒有既有版本」→ 回傳 1（job 變紅），
避免像 2026-11-02 之前那樣產出 0 檔卻仍顯示 success。
驗證門檻由 data/index-proxy.json 逐檔設定：expected_min/max（檔數）與 min_weight_total（權重加總下限，預設 90）。
"""
import csv, datetime as dt, io, json, os, re, sys, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CFG = os.path.join(ROOT, "data", "index-proxy.json")
OUT_DIR = os.path.join(ROOT, "data", "index-holdings")
UA = {"User-Agent": "Mozilla/5.0 (mklab-stock; GitHub Actions) contact: github.com/evanhsia-git/mklab-stock"}
TZ = dt.timezone(dt.timedelta(hours=8))

def log(msg): print(f"[holdings] {msg}", flush=True)

def _num(v):
    try:
        s = str(v).replace("%", "").replace(",", "").strip()
        return float(s) if s not in ("", "-") else None
    except ValueError:
        return None

def parse_table(rows):
    """rows: 二維列表。找到含 Ticker/Symbol 與 Weight 欄位的表頭，回傳 [(代號, 名稱, 權重%)]。"""
    for i, r in enumerate(rows):
        cells = [str(c).strip() for c in r]
        low = [c.lower() for c in cells]
        t = next((j for j, c in enumerate(low) if c in ("ticker", "symbol")), None)
        w = next((j for j, c in enumerate(low) if "weight" in c or "% of" in c or "% assets" in c), None)
        if t is None or w is None:
            continue
        n = next((j for j, c in enumerate(low) if c in ("name", "holding", "holdings", "security name")), None)
        out = []
        for rr in rows[i + 1:]:
            if not rr or len(rr) <= max(t, w):
                continue
            tk = str(rr[t]).strip().upper()
            wt = _num(rr[w])
            if not tk or wt is None or not re.match(r"^[A-Z][A-Z0-9.\-]{0,6}$", tk):
                continue
            out.append({"ticker": tk, "name": str(rr[n]).strip() if n is not None and len(rr) > n else "", "weight_pct": wt})
        if out:
            return out
    return []

def fetch_bytes(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def load_source(src):
    if src.startswith("manual_upload:"):
        rel = src.split(":", 1)[1]
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            raise FileNotFoundError(f"手動檔不存在：{rel}")
        # 來源字串寫回 repo 相對路徑，不要把機器的絕對路徑（/home/runner/... 或本機路徑）寫進資料檔
        return open(p, "rb").read(), f"manual_upload:{rel}"
    data = fetch_bytes(src)
    return data, src

def parse_bytes(data, src):
    if data.lstrip()[:1] == b"<":  # HTML：逐一檢查每個表格
        import pandas as pd
        for t in pd.read_html(io.StringIO(data.decode("utf-8", errors="replace"))):
            res = parse_table([list(t.columns)] + t.fillna("").values.tolist())
            if res:
                return res
        return []
    if src.lower().endswith((".xlsx", ".xls")) or data[:2] == b"PK":
        import pandas as pd
        df = pd.read_excel(io.BytesIO(data), header=None)
        rows = df.fillna("").values.tolist()
    else:
        text = data.decode("utf-8-sig", errors="replace")
        rows = list(csv.reader(io.StringIO(text)))
    return parse_table(rows)

def validate(fund, holdings):
    n = len(holdings)
    if not (fund["expected_min"] <= n <= fund["expected_max"]):
        raise ValueError(f"檔數 {n} 不在預期範圍 {fund['expected_min']}~{fund['expected_max']}")
    total = sum(h["weight_pct"] for h in holdings)
    floor = fund.get("min_weight_total", 90)
    if not (floor <= total <= 101):
        raise ValueError(
            f"權重加總 {total:.2f}% 異常（該基金門檻 {floor}~101%）；"
            "若來源本身只提供部分持股，請在 index-proxy.json 明確設定 min_weight_total，不要放寬全體門檻"
        )
    if len({h['ticker'] for h in holdings}) != n:
        raise ValueError("代號重複")

def main():
    cfg = json.load(open(CFG, encoding="utf-8"))
    os.makedirs(OUT_DIR, exist_ok=True)
    ok = 0
    missing = []  # 連既有版本都沒有 → 真的沒有任何產出，最後讓 exit code 非 0
    for fund in cfg["funds"]:
        key = fund["key"]
        out_path = os.path.join(OUT_DIR, f"{key}.json")
        if fund.get("freq") == "monthly" and os.path.exists(out_path):
            last = json.load(open(out_path, encoding="utf-8")).get("fetched_at", "")[:10]
            if last and (dt.date.today() - dt.date.fromisoformat(last)).days < 25:
                log(f"⏭ {key}：每月更新，{last} 已抓過，略過")
                ok += 1
                continue
        done = False
        for src in fund["sources"]:
            try:
                data, used = load_source(src)
                holdings = parse_bytes(data, used)
                validate(fund, holdings)
                doc = {"fund": key, "index": fund["index"], "issuer": fund["issuer"],
                       "count": len(holdings), "source": used,
                       "fetched_at": dt.datetime.now(TZ).isoformat(),
                       "weight_total_pct": round(sum(h["weight_pct"] for h in holdings), 2),
                       "holdings": sorted(holdings, key=lambda h: -h["weight_pct"])}
                json.dump(doc, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                log(f"✅ {key}：{len(holdings)} 檔，來源 {used[:90]}")
                ok += 1; done = True
                break
            except Exception as e:
                log(f"⚠️ {key} 來源失敗（{src[:90]}）：{type(e).__name__}: {e}")
        if not done:
            if os.path.exists(out_path):
                log(f"❌ {key}：所有來源皆失敗，保留上一版（有既有資料）")
            else:
                missing.append(key)
                log(f"❌ {key}：所有來源皆失敗且無既有資料 → 這個基金完全沒有產出")
    log(f"完成：{ok}/{len(cfg['funds'])} 檔成功")
    if missing:
        # 過去這裡無條件 return 0，導致「三個來源全掛、目錄 0 檔」的 job 依然顯示 ✅ success，
        # 只能靠人去翻日誌才發現。真的沒有任何產出時必須讓 job 變紅。
        log(f"❌ 完全沒有資料的基金：{', '.join(missing)}")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
