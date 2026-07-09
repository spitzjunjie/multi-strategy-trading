import json
with open('output/strategy_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 检查3个策略
targets = ['量价齐升', 'ETF二八轮动', '财务基本面过滤小市值']
print("3个目标策略在strategy_data.json中的状态:")
for s in data['strategies']:
    if s['name'] in targets:
        trades = len(s.get('trades', []))
        ret = s.get('total_return', 0) * 100
        print(f"{s['name']}: 收益={ret:.2f}% 交易={trades}")

# 检查是否有收益非0的策略
print("\n有交易的策略:")
for s in data['strategies']:
    trades = len(s.get('trades', []))
    if trades > 0:
        ret = s.get('total_return', 0) * 100
        print(f"  {s['name']}: 收益={ret:.2f}% 交易={trades}")
