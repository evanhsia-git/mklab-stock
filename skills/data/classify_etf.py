#!/usr/bin/env python3
"""
mklab-stock ETF 分類腳本（Build-Time，純本地計算，不對外請求）。

讀取：
  - data/etf-meta.json       ETF 清單（官方 CSV 解析結果，359 檔）
  - data/etf-categories.json 分類規則（人工維護，改規則不需要改這支程式）
輸出：
  - data/etf-classified.json 每檔 ETF 的分類標籤（可能多個）

分類原則（依使用者指定）：
  1. 明確代號清單優先（如 0050、006208… 是市值型；0056、00878、00919 是高配息型）
  2. 代號結尾字母：A=主動型、B=債券型、L=槓桿型、R=反向型
  3. 名稱關鍵字：名稱含「高息/高股息…」歸高配息型、含「債」歸債券型…
  4. 同一檔可以同時屬於多個分類（例如 00937B 同時是債券型，若名稱含高息也會是高配息型）
  5. 「被動型」：非主動型（非 A 結尾）且非槓桿/反向/主題/高配息/市值以外的一般指數型，
     目前規則為「沒有命中主動型、且名稱不含主題關鍵字」者標為被動型（之後可以細分）
  6. 月配/季配/年配/不配息：需要配息頻率資料，目前沒有資料來源，本版本不自動標註，
     保留欄位（pay_frequency: null），之後補上配息資料再由規則或人工填入

用法：
  python3 skills/data/classify_etf.py
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


def classify_one(etf, rules):
    sym = etf["sym"]
    name = etf.get("name") or ""
    labels = {}  # category_key -> reason
    explicit = rules.get("explicit_codes", {})

    # 規則1：明確代號清單
    for cat, codes in explicit.items():
        if sym in codes:
            labels[cat] = "明確代號清單"

    # 規則2：代號結尾字母
    for rule in rules.get("suffix_rules", []):
        if re.search(rule["suffix"] + r"$", sym):
            labels[rule["category"]] = f"代號結尾 {rule['suffix']}"

    # 規則3：名稱關鍵字
    kw = rules.get("name_keywords", {})
    for cat, words in kw.items():
        for w in words:
            if w and w in name:
                labels.setdefault(cat, f"名稱含「{w}」")
                break

    # 規則5：被動型（非主動、非槓桿/反向、非主題、非債券的一般指數型）
    non_passive = {"active", "leveraged", "inverse", "theme"}
    if not (set(labels.keys()) & non_passive) and "bond" not in labels:
        labels.setdefault("passive", "非主動/槓桿/反向/主題，視為被動指數型")

    return labels


def main():
    meta = _load(META_PATH)
    rules = _load(RULES_PATH)
    out = []
    counts = {}
    for etf in meta.get("etfs", []):
        labels = classify_one(etf, rules)
        for cat in labels:
            counts[cat] = counts.get(cat, 0) + 1
        out.append({
            "sym": etf["sym"],
            "name": etf.get("name"),
            "market": etf.get("market"),
            "categories": sorted(labels.keys()),
            "category_reasons": labels,
            "pay_frequency": None,  # 保留欄位：月配/季配/年配/不配息，待配息資料來源補上
        })

    doc = {
        "meta": {
            "as_of": meta.get("meta", {}).get("as_of"),
            "rules_version": _load(RULES_PATH).get("meta", {}).get("version"),
            "count": len(out),
            "category_counts": counts,
            "labels": rules.get("category_labels", {}),
            "note": "同一檔 ETF 可屬於多個分類；pay_frequency 目前未填（待配息資料）",
        },
        "etfs": out,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"[classify_etf] ✅ 已寫入 {OUT_PATH}（{len(out)} 檔）")
    print(f"[classify_etf] 各分類檔數：{counts}")


if __name__ == "__main__":
    main()
