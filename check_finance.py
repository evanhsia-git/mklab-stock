import json
with open('data/stocks.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
stocks = data['stocks']

symbols = ['2881', '2882', '2883', '2884', '2885', '2886', '2880', '2891']
for sym in symbols:
    for s in stocks:
        if s['sym'] == sym:
            print(f'{sym} {s["name"]}: is_etf={s.get("is_etf")}, ind={s.get("ind")}, security_type={s.get("security_type")}')
            break
    else:
        print(f'{sym}: NOT FOUND')