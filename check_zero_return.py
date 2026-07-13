#!/usr/bin/env python3
import json

with open('output/strategy_data.json', encoding='utf-8') as f:
    data = json.load(f)

strategies = data['strategies']
zero_return = [s for s in strategies if s.get('total_return', 0) == 0]

print(f"总策略数: {len(strategies)}")
print(f"0收益策略数: {len(zero_return)}")
print()

# 显示0收益策略
print("=" * 60)
print("0收益策略列表:")
print("=" * 60)
for i, s in enumerate(zero_return, 1):
    trades = s.get('total_trades', 0)
    print(f"{i}. {s['name']} (交易次数: {trades})")
