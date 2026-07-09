import json
d=json.load(open('output/strategy_data.json'))
# 找一个有持仓的策略
for s in d['strategies']:
    if len(s.get('holdings',[])) > 0 and s.get('name') == '南向资金':
        print(f"策略: {s['name']}")
        for h in s['holdings'][:2]:
            print(f"  持仓: {h['symbol']} {h['name']}")
            print(f"    buy_price: {h.get('buy_price')}")
            print(f"    current_price: {h.get('current_price')}")
            print(f"    profit: {h.get('profit')}")
            print(f"    profit_pct: {h.get('profit_pct')}")
        break
