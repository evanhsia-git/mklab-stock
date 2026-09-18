import json
with open('data/stocks.json') as f:
    data = json.load(f)
etfs = [s for s in data['stocks'] if s.get('security_type')=='etf']
stocks = [s for s in data['stocks'] if s.get('security_type')=='stock']
bad_etfs = [s for s in etfs if s.get('ind') is not None]
bad_stocks = [s for s in stocks if s.get('ind') is None]
print('ETF count:', len(etfs))
print('Stock count:', len(stocks))
print('ETF with non-null ind:', len(bad_etfs))
if bad_etfs:
    print('First bad etf:', bad_etfs[0]['sym'], bad_etfs[0]['name'], 'ind:', bad_etfs[0]['ind'])
print('Stock with null ind:', len(bad_stocks))
if bad_stocks:
    print('First bad stock:', bad_stocks[0]['sym'], bad_stocks[0]['name'], 'ind:', bad_stocks[0]['ind'])
known_etfs = ['2883','00675L','00670L','00647L','00663L']
known_stocks = ['2330','2308','2317','2454']
for sym in known_etfs:
    s = next((x for x in data['stocks'] if x['sym']==sym), None)
    if s:
        print('ETF '+sym+': sec_type='+str(s.get('security_type'))+', ind='+str(s.get('ind')))
for sym in known_stocks:
    s = next((x for x in data['stocks'] if x['sym']==sym), None)
    if s:
        print('Stock '+sym+': sec_type='+str(s.get('security_type'))+', ind='+str(s.get('ind')))
