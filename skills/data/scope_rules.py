#!/usr/bin/env python3
"""本站資料範圍的唯一來源（Single Source of Truth）。

範圍：上市一般股票（4 碼純數字、非 91xx）＋ ETF（00 開頭，允許字母尾碼如 00631L／00981A）。
不收：特別股（2881A／2881B／2887E…）、權證、DR / TDR（91xx）、受益證券（01001T）、
      ETN（0200xx）、上櫃一般股票。

為什麼要有這支：這條規則原本散在 4 個地方各寫一份（fetch_data.classify_security、
compute_indicators、purge_out_of_scope_data），結果 2026-11-10 發現 DR（9103/9105/9110/9136）
因為「剛好是 4 碼純數字」被前兩者判成 stock，而清理腳本又用同一個出錯的欄位判斷 → 三方一起漏。
統一成這裡之後，改規則只改一處。

⚠️ 新增任何「以代號為鍵」的資料檔時，寫入前都要先過 in_scope()，否則範圍外證券會慢慢長回來
   （實例：official-fundamentals.json 的 .dividend 由官方 t187ap45 重建，該檔本來就含特別股，
    沒有過濾就會每次 CI 都種回 28 個特別股死鍵）。
"""


def in_scope(sym):
    """回傳該代號是否屬於本站收錄範圍。

    >>> in_scope("2330"), in_scope("0050"), in_scope("00631L")
    (True, True, True)
    >>> in_scope("2881A"), in_scope("9103"), in_scope("01001T"), in_scope("02001L")
    (False, False, False, False)
    """
    s = str(sym or "").strip()
    if not s:
        return False
    if s.startswith("00"):          # ETF（含 00631L／00981A 這類字母尾碼）
        return True
    # 上市一般股票：4 碼純數字且非 91xx（TWSE 產業別代碼 91 = 存託憑證）
    return len(s) == 4 and s.isdigit() and not s.startswith("91")


def is_etf_shaped(sym):
    """只判斷『長得像 ETF』（00 開頭）；是否為真 ETF 仍以官方清單為準。"""
    return str(sym or "").startswith("00")
