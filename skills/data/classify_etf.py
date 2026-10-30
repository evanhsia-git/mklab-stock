#!/usr/bin/env python3
"""
mklab-stock ETF 分類腳本（Build-Time，純本地計算，不對外請求）。

讀取：
  - data/etf-meta.json       ETF 清單（官方 CSV 解析結果）
  - data/etf-categories.json 分類規則（人工維護；改規則不需改程式）
輸出：
  - data/etf-classified.json 每檔 ETF 的分類標籤（可能多個）

規則優先順序（依使用者指定）：
  1. 排除：代號結尾 U（期貨型）整檔不納入資料庫
  2. 代號結尾字母：L 槓桿、R 反向、B 債券、C 債券外幣、V 期貨外幣、
     T 平衡、A 主動式、D 主動債券、K 待確認
  3. 明確代號清單：市值型 / 高股息型（0050、0056 等）
  4. 名稱關鍵字：含「高息/高股息…」歸高股息型；含產業主題字眼歸主題型
  5. 其餘：歸市值型（沒有任何其他標籤的一般指數型 ETF）
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
META_PATH = os.path.join(ROOT, "data", "etf-meta.json")
RULES_PATH = os.path.join(ROOT, "data", "etf-categories.json")
OUT_PATH = os.path.join(ROOT, "data", "etf-classified.json")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_excluded(sym, rules):
    for suf in rules.get("excluded_suffix", []):
        if sym.endswith(suf):
            return True
    return False


def classify_one(etf, rules):
    sym = etf["sym"]
    name = etf.get("name") or ""
    labels = {}

    # 規則2：代號結尾字母
    for rule in rules.get("suffix_rules", []):
        if sym.endswith(rule["suffix"]):
            labels[rule["category"]] = f"代號結尾 {rule['suffix']}"

    # 規則3：明確代號清單
    for cat, codes in rules.get("explicit_codes", {}).items():
        if sym in codes:
            labels.setdefault(cat, "明確代號清單")

    # 規則4：名稱關鍵字
    for cat, words in rules.get("name_keywords", {}).items():
        for w in words:
            if w and w in name:
                labels.setdefault(cat, f"名稱含「{w}」")
                break

    # 規則5：沒有任何其他標籤的一般指數型，歸市值型
    if not labels:
        labels["market_cap"] = "一般指數型，預設市值型"

    return labels


def main():
    meta = _load(META_PATH)
    rules = _load(RULES_PATH)
    out = []
    excluded = []
    counts = {}
    for etf in meta.get("etfs", []):
        if is_excluded(etf["sym"], rules):
            excluded.append(etf["sym"])
            continue
        labels = classify_one(etf, rules)
        for cat in labels:
            counts[cat] = counts.get(cat, 0) + 1
        out.append({
            "sym": etf["sym"],
            "name": etf.get("name"),
            "market": etf.get("market"),
            "categories": sorted(labels.keys()),
            "category_reasons": labels,
            "pay_frequency": None,
        })

    doc = {
        "meta": {
            "as_of": meta.get("meta", {}).get("as_of"),
            "rules_version": rules.get("meta", {}).get("version"),
            "count": len(out),
            "excluded_count": len(excluded),
            "excluded_syms": excluded,
            "category_counts": counts,
            "labels": rules.get("category_labels", {}),
            "note": "已排除 U 尾期貨型；同一檔可屬多類；pay_frequency 待配息資料來源補上",
        },
        "etfs": out,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"[classify_etf] ✅ 已寫入 {OUT_PATH}（納入 {len(out)} 檔，排除 U 尾 {len(excluded)} 檔）")
    print(f"[classify_etf] 各分類檔數：{counts}")


if __name__ == "__main__":
    main()
