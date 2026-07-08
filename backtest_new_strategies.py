# -*- coding: utf-8 -*-
"""
只回测新策略（跳过已有回测结果的策略）
"""
import json
import os
from datetime import datetime

# 新开发的策略列表（22个）
NEW_STRATEGIES = [
    'ETF二八轮动', '财务基本面过滤小市值', '资金流事件', '反过度自信',
    '行业动量', '研报推荐', '超跌反弹', '短线动量', '低波动',
    '南向资金', '龙虎榜', '北向资金', '价值成长', '业绩暴增',
    '量价齐升', '涨停回调', 'MACD金叉', 'RSI超卖反转',
    '低PB价值', 'KDJ超卖金叉', '高股息', '业绩超预期'
]

def main():
    print("=" * 60)
    print("新策略回测脚本")
    print("=" * 60)

    # 检查已有的回测结果
    output_file = 'output/strategy_data.json'
    existing_results = {}

    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            existing_results = json.load(f)
        print(f"已有回测结果: {len(existing_results)} 个策略")
    else:
        print("没有找到已有回测结果，将全部回测")

    # 找出需要回测的新策略
    need_backtest = []
    for strategy_name in NEW_STRATEGIES:
        if strategy_name not in existing_results or existing_results[strategy_name].get('total_return', 0) == 0:
            need_backtest.append(strategy_name)

    print(f"需要回测的新策略: {len(need_backtest)} 个")
    for s in need_backtest:
        print(f"  - {s}")

    if not need_backtest:
        print("所有新策略都已完成回测！")
        return

    # 这里可以添加实际的回测逻辑
    # 目前只打印需要回测的策略
    print("\n请运行 main_backtest.py 进行回测（会自动跳过已有结果的策略）")

if __name__ == '__main__':
    main()
