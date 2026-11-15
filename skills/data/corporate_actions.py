#!/usr/bin/env python3
"""公司行為（股票分割／反分割）的單一來源：還原價、死值列剔除、跳空自動偵測。

為什麼需要（2026-11-15，Ivan 指示）：
  K 線／MA／RSI／漲跌幅原本全用「原始價」。ETF 分割後價格從 117.8 變約 23.5，
  指標會把分割當成「崩跌 80%」而失真。本模組讓指標改用**還原價**（原始價 ÷ 分割倍數），
  前端仍顯示原始價，只加「已分割 N:1」標註。

三件事：
  1. load_actions()  —— 讀 data/corporate-actions.json。**沒有來源者一律不套用**；
     自動偵測但未經確認（status=detected）者預設不套用（避免把真實崩跌當分割還原掉）。
  2. adjust_rows()   —— 事件日（含）之前的 OHLC ÷ ratio，供技術指標使用。只依日期判定，
     冪等（重複套用不會二次除）。
  3. find_dead_runs() —— 找出「連續同價且成交量完全相同」的死值列。實測停牌期間會出現
     （0052 五列 60.6／vol 完全相同、00631L 四列 35.26／vol 完全相同），它們不是真實成交。
  4. scan_for_discontinuity() —— 掃 K 線找跳空（>閾值），供自動偵測未來分割。

⚠️ 不可把「跳空」直接當成「分割」套用：價格腰斬也可能是真實崩跌。自動偵測結果一律
   以 status=detected 寫入、待人確認（detect_corporate_actions.py），不直接改指標。
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REGISTRY = os.path.join(ROOT, "data", "corporate-actions.json")

# 死值列的判定門檻：連續 >=3 天 o=h=l=c 且成交量與該段首列完全相同
DEAD_MIN_RUN = 3
# 跳空偵測門檻：單日收盤比值偏離 20% 以上（正常個股／ETF 不可能如此）
JUMP_THRESHOLD = 0.2


def _registry_path(root=None):
    return os.path.join(root, "data", "corporate-actions.json") if root else REGISTRY


def load_actions(root=None, include_unconfirmed=False, statuses=("done", "pending")):
    """讀公司行為登記表 → 可用於還原的事件清單。

    只回傳「有來源 + 有倍數 + 有事件日期 + 狀態屬 statuses」者。
    自動偵測的 status=detected 僅在 include_unconfirmed=True 時回傳（供 QA／清單顯示用，
    仍不應拿去算指標——呼叫端負責區分）。
    """
    try:
        with open(_registry_path(root), encoding="utf-8") as f:
            reg = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    out = []
    for a in reg.get("actions", []):
        st = a.get("status")
        if st == "detected":
            if not include_unconfirmed:
                continue
        elif st not in statuses:
            continue
        if not str(a.get("source") or "").strip():
            continue          # 沒有來源 → 不套用（Ivan 的資料原則）
        if a.get("ratio") is None:
            continue          # 沒有倍數 → 無法還原
        if not (a.get("resume_date") or a.get("halt_from")):
            continue          # 沒有事件日期 → 無法判定還原分界
        out.append(a)
    out.sort(key=lambda a: (a.get("resume_date") or a.get("halt_from") or "", str(a.get("sym"))))
    return out


def event_date(action):
    """還原分界日（YYYY-MM-DD）：復牌日優先，沒有則用停止交易日。該日（含）之後為新價。"""
    return action.get("resume_date") or action.get("halt_from")


def actions_for(sym, actions):
    return [a for a in actions if str(a.get("sym")) == str(sym)]


def _boundary_already_continuous(rows, cut, tol=1.2):
    """事件邊界（事件日前最後一根 vs 事件日起第一根）是否已無跳空 → 序列已還原過。

    還原後 0052：35.04 → 35.35（比值 1.009）；未還原：245.3 → 35.35（6.94）。
    找不到邊界（序列缺該段）時回 False＝照常套用。
    """
    prev = cur = None
    for r in rows:
        if str(r[0]).replace("-", "") < cut:
            prev = r[4]
        elif cur is None:
            cur = r[4]
            break
    if not prev or not cur:
        return False
    return max(prev / cur, cur / prev) < tol


def adjust_rows(sym, rows, actions):
    """把事件日之前的 OHLC 除以分割倍數（還原價，供指標使用）。

    rows: [(YYYYMMDD, open, high, low, close), ...]（日期由舊到新）。
    回傳 (adjusted_rows, applied)；applied 為實際套用的事件（附 ratio 與分界日）。
    只除以「日期 < 事件日」的列，因此重複呼叫結果相同。
    """
    hits = [a for a in actions_for(sym, actions) if event_date(a)]
    if not hits:
        return rows, []
    out = list(rows)
    applied = []
    for a in hits:
        ratio = float(a["ratio"])
        if ratio <= 0:
            continue
        cut = str(event_date(a)).replace("-", "")
        if _boundary_already_continuous(out, cut):
            # 事件邊界已無跳空 → 這份序列已還原過，不再二次除（冪等守門）
            continue
        n = 0
        for i, r in enumerate(out):
            if str(r[0]).replace("-", "") >= cut:
                continue
            o, h, l, c = r[1], r[2], r[3], r[4]
            out[i] = (r[0],
                      round(o / ratio, 4) if o is not None else None,
                      round(h / ratio, 4) if h is not None else None,
                      round(l / ratio, 4) if l is not None else None,
                      round(c / ratio, 4) if c is not None else None)
            n += 1
        applied.append({"sym": sym, "type": a.get("type"), "ratio": ratio,
                        "event_date": event_date(a), "adjusted_rows": n,
                        "status": a.get("status"), "source": a.get("source")})
    return out, applied


def adjust_series_map(series, actions, trace=None):
    """對 {sym: rows} 全體套用還原價 → (新 map, 套用清單)。"""
    out, applied = {}, []
    for sym, rows in series.items():
        adj, hits = adjust_rows(sym, rows, actions)
        out[sym] = adj
        applied.extend(hits)
    if trace is not None:
        trace.extend(applied)
    return out, applied


def implied_ratio(before_close, after_close):
    """由「事件前最後真實收盤 ÷ 復牌後第一筆」推出隱含倍數（含復牌當日行情變動，故為近似）。"""
    try:
        b, a = float(before_close), float(after_close)
    except (TypeError, ValueError):
        return None
    if a <= 0 or b <= 0:
        return None
    return round(b / a, 2)


def find_dead_runs(rows, min_run=DEAD_MIN_RUN):
    """找出「連續同價且成交量完全相同」的死值列（停牌期間的補值／殘值）。

    rows: [(date, open, high, low, close, volume), ...]（history 快照格式）。
    判定：同一段內每天都 ①o=h=l=c ②volume 與該段首列相同。真實平盤的成交量不會
    連續多日一字不差（2026-07-13 整檔 o=h=l=c 但量各不相同 → 是真實資料，不可刪）。
    回傳 [{dates, close, volume, length}]。
    """
    runs, cur = [], []
    for r in rows:
        if len(r) < 6:
            cur = []
            continue
        date, o, h, l, c, v = r[0], r[1], r[2], r[3], r[4], r[5]
        flat = o == h == l == c
        if cur:
            same = cur[0][4] == c and cur[0][5] == v
        else:
            same = True
        if flat and same and c is not None:
            cur.append((date, o, h, l, c, v))
        else:
            if len(cur) >= min_run:
                runs.append({"dates": [x[0] for x in cur], "close": cur[0][4],
                             "volume": cur[0][5], "length": len(cur)})
            cur = [(date, o, h, l, c, v)] if flat and c is not None else []
    if len(cur) >= min_run:
        runs.append({"dates": [x[0] for x in cur], "close": cur[0][4],
                     "volume": cur[0][5], "length": len(cur)})
    return runs


def scan_for_discontinuity(sym, rows, threshold=JUMP_THRESHOLD):
    """掃單一序列的跳空：相鄰收盤比值偏離 > threshold 即視為疑似公司行為。

    回傳 [{sym, before_date, before_close, after_date, after_close, implied_ratio, drop_pct}]。
    只回報事實，不判定是否為分割（分辨真假需要人確認或官方來源）。
    """
    hits = []
    for i in range(1, len(rows)):
        prev, cur = rows[i - 1][4], rows[i][4]
        if not prev or not cur:
            continue
        try:
            chg = cur / prev - 1
        except ZeroDivisionError:
            continue
        if abs(chg) > threshold:
            hits.append({
                "sym": sym,
                "before_date": str(rows[i - 1][0]).replace("-", ""),
                "before_close": prev,
                "after_date": str(rows[i][0]).replace("-", ""),
                "after_close": cur,
                "implied_ratio": implied_ratio(prev, cur),
                "drop_pct": round(chg * 100, 2),
            })
    return hits
