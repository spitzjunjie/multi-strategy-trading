import json
d=json.load(open('output/strategy_data.json'))
zero=[s for s in d['strategies'] if s.get('total_return',0)==0]
print(f'0收益策略: {len(zero)}个')
for s in zero[:15]:
    holdings = len(s.get('holdings',[]))
    trades = len(s.get('trades',[]))
    f_pnl = s.get('floating_pnl',0)
    f_pnl_pct = s.get('floating_pnl_pct',0)
    total_pnl_pct = s.get('total_pnl_pct',0)
    print(f"{s['name']}: 持仓{holdings}只, 交易{trades}笔, floating_pnl={f_pnl:.2f}({f_pnl_pct*100:.2f}%), total_pnl_pct={total_pnl_pct*100:.2f}%")
