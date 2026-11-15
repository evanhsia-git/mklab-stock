#!/usr/bin/env python3
"""公司行為自動偵測（每日 Build-Time 執行）。

做什麼：掃 data/kline/*.json，找出單日跳空 > 20% 的標的，寫成候選清單
`data/corporate-actions-candidates.json`（status=detected），並在輸出印出報告。

為什麼：Ivan 2026-11-15 指示「要能完整應對未來其他 ETF 產生股票拆分，可以立即回應」。
只靠人工登記 corporate-actions.json，下一檔（0053、00757、006208…）就會被漏掉。

⚠️ 安全設計（不可以拿掉）：
  - 候選只是「疑似」，一律不套用到指標、不寫入 stocks.json（真實崩跌也會造成跳空）。
  - 已登記（status=done/pending）的事件不重複列入候選。
  - 輸出冪等：候選檔每次整份重寫且排序固定，重跑不會累積重複筆數。

用法：
  python3 skills/data/detect_corporate_actions.py
  python3 skills/data/detect_corporate_actions.py --json     # 只輸出 JSON（給排程摘要用）
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corporate_actions as ca  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KLINE = os.path.join(ROOT, "data", "kline")
OUT = os.path.join(ROOT, "data", "corporate-actions-candidates.json")
THRESHOLD = 0.2
# 公司行為一定伴隨停止交易（換發期間無行情）→ 要求跳空的兩列之間至少隔 3 個日曆天。
# 沒有這個條件，槓桿／反向型 ETF（期元大／期街口系列）單日 ±20~30% 的**正常行情**
# 會被誤報成公司行為（2026-11-15 實測：無此條件時 64 筆跳空／59 檔候選）。
MIN_GAP_DAYS = 3


def scan_kline_dir(kline_dir=None, threshold=THRESHOLD):
    """掃全部 K 線檔 → 跳空清單（每檔取最大一跳，足以辨識事件）。"""
    kline_dir = kline_dir or KLINE
    hits = []
    for fp in sorted(glob.glob(os.path.join(kline_dir, "*.json"))):
        sym = os.path.basename(fp)[:-5]
        if sym.endswith("U"):        # 期貨型 ETF / 認購權證：價格型態特殊，不納入
            continue
        try:
            with open(fp, encoding="utf-8") as f:
                rows = json.load(f).get("rows", [])
        except (OSError, json.JSONDecodeError):
            continue
        clean = [(str(r[0]).replace("-", ""), r[1], r[2], r[3], r[4]) for r in rows]
        for h in ca.scan_for_discontinuity(sym, clean, threshold, min_gap_days=MIN_GAP_DAYS):
            hits.append(h)
    return hits


def classify_hit(hit):
    """由跳空方向推測類型：價格變低＝分割（或減資）；變高＝反分割（或合併）。
    僅為提示，需人工確認。"""
    r = hit.get("implied_ratio")
    if r is None:
        return "unknown"
    return "split" if r > 1 else "reverse_split"


def build_candidates(hits, confirmed, names=None):
    """把跳空清單轉成候選（排除已登記事件的標的）。"""
    have = {str(a.get("sym")) for a in confirmed}
    out = []
    for h in hits:
        if str(h["sym"]) in have:
            continue
        out.append({
            "sym": h["sym"],
            "name": (names or {}).get(h["sym"]),
            "type": classify_hit(h),
            "ratio": None,                     # 未經確認不填倍數（填了就會被拿去還原）
            "implied_ratio": h["implied_ratio"],
            "halt_from": None,
            "resume_date": h["after_date"],
            "status": "detected",
            "source": "auto:price_discontinuity",
            "source_note": ("本站 K 線相鄰日跳空 "
                            f"{h['drop_pct']}%（{h['before_date']} 收 {h['before_close']} → "
                            f"{h['after_date']} 收 {h['after_close']}），隱含倍數 "
                            f"{h['implied_ratio']}。可能是分割／反分割／減資，也可能是真實崩跌，"
                            "須人工確認後才可寫入倍數並套用還原價。"),
        })
    out.sort(key=lambda x: str(x["sym"]))
    return out


def main(as_json=False):
    confirmed = ca.load_actions(root=ROOT, statuses=("done", "pending"))
    names = {}
    try:
        with open(os.path.join(ROOT, "data", "stocks.json"), encoding="utf-8") as f:
            names = {s["sym"]: s.get("name") for s in json.load(f).get("stocks", [])}
    except (OSError, json.JSONDecodeError, KeyError):
        pass
    hits = scan_kline_dir()
    cands = build_candidates(hits, confirmed, names)
    doc = {
        "meta": {
            "note": ("自動偵測的公司行為候選（未確認）。**不套用**到指標或快照；"
                     "確認後把該筆 status 改 pending/done 並補上 ratio 與來源即可。"),
            "threshold": THRESHOLD,
            "generated_from": "data/kline/*.json",
        },
        "candidates": cands,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    if as_json:
        print(json.dumps({"candidates": len(cands)}, ensure_ascii=False))
        return 0
    print(f"[detect_corporate_actions] 掃到跳空 {len(hits)} 筆、已知事件 "
          f"{len({h['sym'] for h in hits} & {str(a.get('sym')) for a in confirmed})} 檔已登記")
    print(f"[detect_corporate_actions] 待確認候選 {len(cands)} 檔 → {os.path.relpath(OUT, ROOT)}")
    for c in cands[:15]:
        print(f"   {c['sym']:<8}{(c['name'] or '')[:10]:<12}{c['type']:<14}"
              f"隱含倍數 {c['implied_ratio']}  跳空 {c['resume_date']}")
    if len(cands) > 15:
        print(f"   …另有 {len(cands) - 15} 檔")
    return 0


if __name__ == "__main__":
    sys.exit(main(as_json="--json" in sys.argv))
