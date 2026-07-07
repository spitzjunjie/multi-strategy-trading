# -*- coding: utf-8 -*-
"""
策略失效原因诊断
分析为什么价值因子、资金因子、质量因子等策略都是零收益
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from data.akshare_helper import AKShareHelper
from backtest import get_all_strategies
import pandas as pd

def diagnose_factor_strategies():
    """诊断因子策略为何失效"""
    helper = AKShareHelper(cache_dir="data/cache")

    print("=" * 60)
    print("策略失效原因诊断")
    print("=" * 60)

    # 获取几只测试股票
    stocks = helper.get_stock_pool("hs300")[:10]
    print(f"\n测试股票池: {len(stocks)} 只\n")

    # ===== 1. 诊断价值因子 =====
    print("=" * 60)
    print("1. 价值因子诊断（低PE/PB/PSR）")
    print("=" * 60)

    for sym in stocks[:3]:
        val = helper.get_valuation_data(sym)
        print(f"\n{sym}:")
        print(f"  PE: {val.get('pe', 'N/A')}")
        print(f"  PB: {val.get('pb', 'N/A')}")
        print(f"  PS: {val.get('ps', 'N/A')}")
        print(f"  股息率: {val.get('dv_ratio', 'N/A')}")

        # 检查是否有无效值
        pe = val.get('pe', 0)
        if pe == 0 or pe > 500 or pe < 0:
            print(f"  ⚠️ PE值异常: {pe} (可能是数据接口问题)")

        if val.get('pe') == 0 and val.get('pb') == 0:
            print(f"  ❌ 估值数据全为0，数据接口可能失效！")

    # ===== 2. 诊断财务因子 =====
    print("\n" + "=" * 60)
    print("2. 财务因子诊断（ROE/净利润增速/营收增长）")
    print("=" * 60)

    for sym in stocks[:3]:
        fin = helper.get_financial_indicator(sym)
        growth = helper.get_growth_data(sym)

        print(f"\n{sym}:")
        print(f"  ROE: {fin.get('roe', 'N/A')}")
        print(f"  资产负债率: {fin.get('debt_ratio', 'N/A')}")
        print(f"  净利润增速: {growth.get('profit_growth', 'N/A')}")
        print(f"  营收增速: {growth.get('revenue_growth', 'N/A')}")

        # 检查是否有None或0
        if fin.get('roe') == 0 or fin.get('roe') is None:
            print(f"  ⚠️ ROE为0或None，财务数据可能为空")

        if growth.get('profit_growth') == 0:
            print(f"  ⚠️ 净利润增速为0，数据可能未更新")

    # ===== 3. 诊断资金因子 =====
    print("\n" + "=" * 60)
    print("3. 资金因子诊断（北向资金/机构持仓）")
    print("=" * 60)

    for sym in stocks[:3]:
        north = helper.get_north_holding(sym)
        inst = helper.get_institution_holding(sym)

        print(f"\n{sym}:")
        print(f"  北向持股比例: {north.get('hold_ratio', 'N/A')}")
        print(f"  持股市值: {north.get('hold_market_value', 'N/A')}")
        print(f"  基金持股占比: {inst.get('fund_hold_ratio', 'N/A')}")
        print(f"  持有基金数: {inst.get('inst_count', 'N/A')}")

        if north.get('hold_ratio') == 0 or north.get('hold_ratio') is None:
            print(f"  ⚠️ 北向持股为0或None，数据接口可能失效")

    # ===== 4. 诊断技术因子 =====
    print("\n" + "=" * 60)
    print("4. 技术因子诊断（MACD/KDJ/RSI）")
    print("=" * 60)

    for sym in stocks[:3]:
        kline = helper.get_history_kline(sym, days=60)
        if kline.empty or len(kline) < 20:
            print(f"\n{sym}: ❌ K线数据不足 ({len(kline)}条)")
            continue

        # 计算技术指标
        ma5 = kline['close'].rolling(5).mean().iloc[-1]
        ma10 = kline['close'].rolling(10).mean().iloc[-1]
        ma20 = kline['close'].rolling(20).mean().iloc[-1]

        # RSI
        delta = kline['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]

        print(f"\n{sym}:")
        print(f"  当前价: {kline['close'].iloc[-1]:.2f}")
        print(f"  MA5: {ma5:.2f}, MA10: {ma10:.2f}, MA20: {ma20:.2f}")
        print(f"  RSI(14): {rsi:.1f}")

        # 检查是否有信号
        if rsi < 30:
            print(f"  📈 RSI超卖，可能有反弹机会")
        elif rsi > 70:
            print(f"  📉 RSI超买，注意回调风险")

        # 均线多头
        if ma5 > ma10 > ma20:
            print(f"  ✅ 均线多头排列")
        elif ma5 < ma10 < ma20:
            print(f"  ❌ 均线空头排列")
        else:
            print(f"  ⚠️ 均线混乱")

    # ===== 5. 诊断策略选股结果 =====
    print("\n" + "=" * 60)
    print("5. 策略选股结果诊断")
    print("=" * 60)

    strategies = get_all_strategies()

    # 测试几个代表性策略
    test_names = ['低PE', 'ROE选股', '北向资金跟投', 'MACD金叉', '高股息']

    for name in test_names:
        strategy = next((s for s in strategies if s.name == name), None)
        if strategy is None:
            print(f"\n{name}: ❌ 策略不存在")
            continue

        print(f"\n{name}:")

        # 因子策略
        if hasattr(strategy, 'calculate_factor'):
            result = strategy.calculate_factor(helper)
            if result is None or result.empty:
                print(f"  ❌ 选股结果为空")
            else:
                print(f"  ✅ 选出 {len(result)} 只股票")
                if len(result) > 0:
                    print(f"  前3只: {result.head(3)['symbol'].tolist()}")

        # 事件策略
        elif hasattr(strategy, 'detect_events'):
            result = strategy.detect_events(helper)
            if not result:
                print(f"  ❌ 选股结果为空")
            else:
                print(f"  ✅ 选出 {len(result)} 只股票")
                if len(result) > 0:
                    print(f"  前3只: {[r['symbol'] for r in result[:3]]}")

    # ===== 6. 诊断结论 =====
    print("\n" + "=" * 60)
    print("诊断结论")
    print("=" * 60)

    print("""
根据诊断结果，可能存在以下问题：

1. 【数据接口问题】
   - 估值数据(PE/PB)返回0或N/A
   - 财务数据(ROE/增速)返回None
   - 北向/机构持仓数据为空

2. 【策略逻辑问题】
   - 价值因子：低估值陷阱（PE低可能是因为基本面恶化）
   - 资金因子：数据滞后，单纯持股比例不能预测收益
   - 技术因子：单一指标不够，需要多指标共振

3. 【优化方向】
   - 使用XGBoost自动发现有效因子组合
   - 增加市场环境判断（趋势市/震荡市）
   - 使用相对排名而非绝对值
   - 增加止损止盈的灵活性
""")


if __name__ == "__main__":
    diagnose_factor_strategies()
