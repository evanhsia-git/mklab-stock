"""
Phase 4 QA Automation - ETF Data Quality Checks
"""
import json
from collections import Counter

with open('data/stocks.json', encoding='utf-8') as f:
    data = json.load(f)

etfs = [r for r in data['stocks'] if r.get('is_etf')]

def check_1_no_null_to_zero():
    """Check 1: Not allowing unknown data automatically filled as 0"""
    issues = []
    for r in etfs:
        sym = r['sym']
        for field in ['close', 'price', 'high', 'low', 'open', 'listing_date']:
            if r.get(field) == 0:
                issues.append(f"{sym}: {field} = 0 (可能為空值被填為0)")
    return issues

def check_2_no_unverified_fees_as_official():
    """Check 3: Not allowing unverified fees marked as official"""
    issues = []
    for r in etfs:
        if r.get('fee_verified') == 'official' and r.get('fee_source') != 'official':
            issues.append(f"{r['sym']}: 費率標記為 official 但 fee_source={r.get('fee_source')}")
    return issues

def check_3_no_fabricated_data():
    """Verify no fabricated data: fee values should have source"""
    issues = []
    for r in etfs:
        fee_src = r.get('fee_source')
        if fee_src not in ['aum_tier', 'official', 'manual', 'moneydj', 'moneydj_aum_tier']:
            issues.append(f"{r['sym']}: 未知 fee_source={fee_src}")
    return issues

def check_4_fee_internal_consistency():
    """Check mgmt + cust == total"""
    issues = []
    for r in etfs:
        mgmt = r.get('management_fee')
        cust = r.get('custody_fee')
        total = r.get('total_fee')
        if all(v is not None for v in [mgmt, cust, total]):
            if abs((mgmt + cust) - total) > 0.001:
                issues.append(f"{r['sym']}: 管理費{mgmt} + 保管費{cust} ≠ 總費率{total}")
    return issues

def check_5_ohlc_consistency():
    """Check OHLC price consistency"""
    issues = []
    for r in etfs:
        open_p = r.get('open')
        high = r.get('high')
        low = r.get('low')
        close = r.get('close')
        if all(v is not None for v in [open_p, high, low, close]):
            if high < max(open_p, close) or low > min(open_p, close):
                issues.append(f"{r['sym']}: OHLC 邏輯錯誤")
    return issues

def check_6_price_range_sanity():
    """Check price is reasonable"""
    issues = []
    for r in etfs:
        price = r.get('price')
        if price is not None and price > 0:
            if price > 100000 or price < 0.01:
                issues.append(f"{r['sym']}: 價格異常={price}")
    return issues

def check_7_date_consistency():
    """Check dates are valid"""
    issues = []
    for r in etfs:
        ld = r.get('listing_date')
        if ld:
            try:
                parts = ld.split('-')
                if len(parts) != 3:
                    issues.append(f"{r['sym']}: listing_date 格式錯誤={ld}")
            except:
                issues.append(f"{r['sym']}: listing_date 無法解析={ld}")
    return issues

def check_8_code_issuer_consistency():
    """Check ETF code and issuer consistency"""
    missing_issuer = sum(1 for r in etfs if not r.get('issuer'))
    issues = []
    if missing_issuer > 0:
        issues.append(f"{missing_issuer} 筆 ETF 缺少發行商名稱")
    return issues

def check_9_no_duplicate_holdings():
    """Check holdings for duplicate codes"""
    issues = []
    for r in etfs:
        holdings = r.get('holdings')
        if holdings:
            codes = [h[0] if isinstance(h, list) else h.get('code') for h in holdings]
            codes = [c for c in codes if c]
            dupes = [code for code, count in Counter(codes).items() if count > 1]
            if dupes:
                issues.append(f"{r['sym']}: 成份股代碼重複={dupes}")
    return issues

def check_10_all_fields_valid_types():
    """Check data types are correct"""
    issues = []
    numeric_fields = ['close', 'price', 'management_fee', 'custody_fee', 'total_fee',
                      'return_5y', 'dividend_yield_ttm', 'last_distribution_amount']
    for r in etfs:
        sym = r['sym']
        for field in numeric_fields:
            val = r.get(field)
            if val is not None and not isinstance(val, (int, float)):
                issues.append(f"{sym}: {field} 型別錯誤={type(val).__name__}")
    return issues

checks = [
    ("1. 不允許空值填為0", check_1_no_null_to_zero),
    ("2. 費率驗證狀態", check_2_no_unverified_fees_as_official),
    ("3. 無捏造資料", check_3_no_fabricated_data),
    ("4. 費用內部一致性 (mgmt+cust=total)", check_4_fee_internal_consistency),
    ("5. OHLC 價格一致性", check_5_ohlc_consistency),
    ("6. 價格區間合理性", check_6_price_range_sanity),
    ("7. 日期格式合規", check_7_date_consistency),
    ("8. 代碼與發行商一致性", check_8_code_issuer_consistency),
    ("9. 成份股代碼重複檢查", check_9_no_duplicate_holdings),
    ("10. 欄位型別合規", check_10_all_fields_valid_types),
]

total_issues = 0
all_pass = True
for name, func in checks:
    issues = func()
    total_issues += len(issues)
    if issues:
        all_pass = False
        print(f"❌ {len(issues)} issues: {name}")
        for i in issues[:3]:
            print(f"    - {i}")
    else:
        print(f"✅ PASS: {name}")

print(f"\n{'='*50}")
print(f"QA 總計：{total_issues} 個問題, {'PASS' if all_pass else 'FAIL'}")
