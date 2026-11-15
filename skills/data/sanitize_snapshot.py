#!/usr/bin/env python3
"""
sanitize_snapshot.py — 對既有快照套用 data_rules 的單位/一致性修正（一次性修復 + 可重複執行）

用法：
  python3 skills/data/sanitize_snapshot.py            # 就地修正 data/stocks.json、data/us/*.json
  python3 skills/data/sanitize_snapshot.py --dry-run  # 只列出會改什麼

設計：
  - 只做「確定性」修正（EPS≤0 的 PE → null、美股 ytd ×100 還原、殖利率/淨值比超範圍 → null）。
  - 不做任何猜測性填值。股本為 0 無法在此修正，必須重新抓 TWSE 資產負債表（fetch_data.py）。
  - 冪等：重複執行結果不變。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import data_rules  # noqa: E402

TARGETS = {
    "stocks": os.path.join(ROOT, "data", "stocks.json"),
    "us_stocks": os.path.join(ROOT, "data", "us", "us-stocks.json"),
    "us_etfs": os.path.join(ROOT, "data", "us", "us-etfs.json"),
    # 2026-11-13：n 語意修正（只取得前 10 大者不可再自稱成份股總數）
    "etf_holdings": os.path.join(ROOT, "data", "etf-holdings.json"),
}

DATA = os.path.join(ROOT, "data")
ETf_CLASSIFIED = os.path.join(DATA, "etf-classified.json")
ETF_META = os.path.join(DATA, "etf-meta.json")
CORPORATE_ACTIONS = os.path.join(DATA, "corporate-actions.json")
KLINE_DIR = os.path.join(DATA, "kline")


def _load(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _last_bar(sym):
    """個股 K 線最後一根（本站 K 線由官方日行情產生）→ (date, close) 或 (None, None)。"""
    doc = _load(os.path.join(KLINE_DIR, f"{sym}.json"))
    if not doc:
        return None, None
    rows = doc.get("rows") or []
    fields = doc.get("fields") or []
    if not rows or fields[:1] != ["date"]:
        return None, None
    try:
        hit = fields.index("close")
    except ValueError:
        return None, None
    return rows[-1][0], rows[-1][hit]


def restore_missing_etfs(doc, notes):
    """把「在站內 ETF 清單（etf-classified）卻不在快照裡」的 ETF 補回來。

    2026-11-15：fetch_data 的沿用判定原本只用公司財報（ETF 沒有），
    導致停牌中的 ETF 整檔消失（實測 00662 富邦NASDAQ 5 拆 1）。
    修好判定後，這裡負責把**已經被丟掉**的補回來：用 etf-meta 的官方基本資料
    ＋ K 線最後一根的成交價與日期，標記 suspended（不冒充現價）。
    """
    stocks = doc.get("stocks") or []
    have = {s.get("sym") for s in stocks}
    cls = _load(ETf_CLASSIFIED, {}) or {}
    meta = {e["sym"]: e for e in (_load(ETF_META, {}) or {}).get("etfs", [])}
    added = []
    for e in cls.get("etfs", []):
        sym = e.get("sym")
        if not sym or sym in have:
            continue
        m = meta.get(sym) or {}
        last_date, last_close = _last_bar(sym)
        stocks.append({
            "sym": sym,
            "name": m.get("name") or e.get("name"),
            "security_type": "etf",
            "is_etf": True,
            "source": "TWSE" if (m.get("market") or e.get("market")) == "TWSE" else "TPEX",
            "ind": None,
            "listing_date": m.get("listing_date"),
            "price": None, "open": None, "high": None, "low": None, "volume": None,
            "chg": None,
            "price_asof": last_date,           # 最後有價資料的日期，不冒充當日
            "last_close": last_close,          # 最後一次成交價，另存不混用
            "last_close_date": last_date,
            "trading_status": "suspended",
            "capital_stock": None,             # ETF 無實收資本額（不寫 0）
            "market_cap": None,                # 無當日股價 → 無當日市值
            "quality": "official",
            "restored_by": "sanitize_snapshot.restore_missing_etfs",
        })
        added.append(f"{sym} {m.get('name') or ''}（最後成交 {last_date} 收 {last_close}）")
    if added:
        doc["stocks"] = stocks
        notes.append("復原遺失 ETF " + str(len(added)) + " 檔：" + "；".join(added[:5]))
    return added


def apply_corporate_actions(doc, notes, today=None):
    """把 data/corporate-actions.json 套用到快照：停牌期間標 suspended ＋ 標示公司行為。

    登記表逐筆都有來源（見該檔 meta）；沒有來源的公司行為不寫入。
    """
    import datetime as dt
    reg = _load(CORPORATE_ACTIONS, {}) or {}
    # 2026-11-15：已完成（done）的分割也要標示，否則 0052／00631L 的 K 線跳空
    # 在畫面上沒有「已分割 N:1」可解釋。未確認的自動偵測（detected）一律不寫入
    # ——避免把真實崩跌標成公司行為。
    acts = [a for a in reg.get("actions", []) if a.get("status") != "detected"]
    if not acts:
        return []
    today = today or dt.date.today().isoformat()
    by_sym = {s.get("sym"): s for s in doc.get("stocks") or []}
    touched = []
    for a in acts:
        s = by_sym.get(a.get("sym"))
        if not s:
            continue
        s["corporate_action"] = {
            "type": a.get("type"),
            "ratio": a.get("ratio"),
            "cash_refund": a.get("cash_refund"),   # 現金減資才有（每股退還股款）
            "halt_from": a.get("halt_from"),
            "resume_date": a.get("resume_date"),
            "status": a.get("status"),
            "source": a.get("source"),
        }
        # 停止交易期間：標 suspended、清掉當日價量與市值（不得拿舊價當現價）。
        # 只有「尚未復牌」的事件才會停牌——已完成的（done）停止日雖在過去，
        # 但已恢復交易，若照樣標停牌會把 0052 的現價清成 null（2026-11-15 修）。
        if (a.get("status") == "pending" and a.get("halt_from") and a["halt_from"] <= today
                and (not a.get("resume_date") or a["resume_date"] > today)):
            s["trading_status"] = "suspended"
            s["suspended_reason"] = "corporate_action"
            s["halt_date"] = a.get("halt_from")
            s["halt_resume"] = a.get("resume_date")
            for k in ("price", "open", "high", "low", "volume", "chg", "market_cap"):
                s[k] = None
        touched.append(f"{a.get('sym')} {a.get('type')} {a.get('ratio')}:1"
                       f"（{a.get('status')}；停止 {a.get('halt_from')}、恢復 {a.get('resume_date')}）")
    if touched:
        notes.append("套用公司行為 " + str(len(touched)) + " 筆：" + "；".join(touched))
    return touched


def recompute_meta(doc):
    """meta.count / sources / price_asof_counts 一律由實際陣列重算（不沿用舊值）。"""
    meta = doc.setdefault("meta", {})
    stocks = doc.get("stocks") or []
    meta["count"] = len(stocks)
    src = {}
    pa = {}
    for s in stocks:
        src[s.get("source")] = src.get(s.get("source"), 0) + 1
        pa[s.get("price_asof")] = pa.get(s.get("price_asof"), 0) + 1
    meta["sources"] = src
    meta["price_asof_counts"] = pa
    return meta


def main(dry_run=False):
    total = 0
    for name, path in TARGETS.items():
        if not os.path.exists(path):
            print(f"[skip] {name}: {path} 不存在")
            continue
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        doc = json.loads(raw)
        doc_notes = []
        if name == "stocks":
            # 順序有意義：先把遺失的 ETF 補回來，再套用公司行為（停牌／分割），
            # 最後才逐筆跑確定性修正（新補回來的記錄也要被修到）。
            restore_missing_etfs(doc, doc_notes)
            apply_corporate_actions(doc, doc_notes)
            notes = []
            for rec in doc.get("stocks", []):
                n = data_rules.sanitize_stock_record(rec)
                if n:
                    notes.append((rec.get("sym"), n))
            # 陣列或欄位有變動 → meta（count／sources／price_asof_counts）一律重算，不沿用舊值
            recompute_meta(doc)
        elif name == "us_stocks":
            notes = [(None, [x]) for x in data_rules.sanitize_us_stocks_doc(doc)]
        elif name == "us_etfs":
            notes = [(None, [x]) for x in data_rules.sanitize_us_etfs_doc(doc)]
        else:
            notes = [(None, [x]) for x in data_rules.sanitize_etf_holdings_doc(doc)]
        for ln in doc_notes:
            print(f"[{name}] {ln}")
        print(f"[{name}] 修正 {len(notes)} 項")
        for sym, n in notes[:8]:
            print(f"    {sym + ': ' if sym else ''}{'; '.join(n)}")
        if len(notes) > 8:
            print(f"    ...（其餘 {len(notes) - 8} 項略）")
        total += len(notes) + len(doc_notes)
        if (notes or doc_notes) and not dry_run:
            # 保留原檔格式（避免整檔 diff）：pretty 檔用 indent=2 + 結尾換行；compact 檔用緊湊格式無結尾換行
            pretty = raw.startswith("{\n")
            text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n" if pretty \
                else json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
    print(("[dry-run] " if dry_run else "") + f"合計 {total} 筆")
    return 0


if __name__ == "__main__":
    sys.exit(main(dry_run="--dry-run" in sys.argv))
