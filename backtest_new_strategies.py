"""
新策略统一回测脚本

回测所有新开发的22个策略
"""

import sys
sys.path.append('.')

from strategies.etf_rotation_strategy import ETFRotationStrategy
from strategies.fundamental_small_cap_strategy import FundamentalSmallCapStrategy
from strategies.money_flow_event_strategy import MoneyFlowEventStrategy
from strategies.anti_overconfidence_strategy import AntiOverconfidenceStrategy
from strategies.industry_momentum_strategy import IndustryMomentumStrategy
from strategies.research_report_strategy import ResearchReportStrategy
from strategies.super_short_rebound_strategy import SuperShortReboundStrategy
from strategies.short_term_momentum_strategy import ShortTermMomentumStrategy
from strategies.low_turnover_strategy import LowVolatilityStrategy
from strategies.southbound_money_strategy import SouthboundMoneyStrategy
from strategies.dragon_tiger_list_strategy import DragonTigerListStrategy
from strategies.northbound_money_strategy import NorthboundMoneyStrategy
from strategies.value_growth_strategy import ValueGrowthStrategy
from strategies.profit_explosion_strategy import ProfitExplosionStrategy
from strategies.continuous_volume_strategy import ContinuousVolumeStrategy
from strategies.limit_callback_strategy import LimitCallbackStrategy
from strategies.golden_cross_strategy import GoldenCrossStrategy
from strategies.rsi_rebound_strategy import RSIReboundStrategy
from strategies.low_pb_value_strategy import LowPBValueStrategy
from strategies.KDJ_strategy import KDJStrategy
from strategies.high_dividend_strategy import HighDividendStrategy
from strategies.profit_exceeds_expectation_strategy import ProfitExceedsExpectationStrategy

# 新策略列表
NEW_STRATEGIES = [
    ('ETF二八轮动', ETFRotationStrategy),
    ('财务基本面过滤小市值', FundamentalSmallCapStrategy),
    ('资金流事件', MoneyFlowEventStrategy),
    ('反过度自信', AntiOverconfidenceStrategy),
    ('行业动量', IndustryMomentumStrategy),
    ('研报推荐', ResearchReportStrategy),
    ('超跌反弹', SuperShortReboundStrategy),
    ('短线动量', ShortTermMomentumStrategy),
    ('低波动', LowVolatilityStrategy),
    ('南向资金', SouthboundMoneyStrategy),
    ('龙虎榜', DragonTigerListStrategy),
    ('北向资金', NorthboundMoneyStrategy),
    ('价值成长', ValueGrowthStrategy),
    ('业绩暴增', ProfitExplosionStrategy),
    ('量价齐升', ContinuousVolumeStrategy),
    ('涨停回调', LimitCallbackStrategy),
    ('MACD金叉', GoldenCrossStrategy),
    ('RSI超卖反转', RSIReboundStrategy),
    ('低PB价值', LowPBValueStrategy),
    ('KDJ超卖金叉', KDJStrategy),
    ('高股息', HighDividendStrategy),
    ('业绩超预期', ProfitExceedsExpectationStrategy),
]


def run_backtest():
    """运行回测"""
    print("=" * 60)
    print("新策略统一回测")
    print("=" * 60)
    
    results = []
    
    for name, StrategyClass in NEW_STRATEGIES:
        try:
            print(f"\n[回测] {name}...")
            strategy = StrategyClass()
            signal = strategy.generate_signal()
            
            results.append({
                'name': name,
                'status': 'SUCCESS',
                'signal': signal
            })
            print(f"[成功] {name}")
            
        except Exception as e:
            print(f"[失败] {name}: {e}")
            results.append({
                'name': name,
                'status': 'FAILED',
                'error': str(e)
            })
    
    # 打印汇总
    print("\n" + "=" * 60)
    print("回测汇总")
    print("=" * 60)
    
    success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    failed_count = sum(1 for r in results if r['status'] == 'FAILED')
    
    print(f"\n成功: {success_count}/{len(results)}")
    print(f"失败: {failed_count}/{len(results)}")
    
    if failed_count > 0:
        print("\n失败策略:")
        for r in results:
            if r['status'] == 'FAILED':
                print(f"  - {r['name']}: {r['error']}")
    
    return results


if __name__ == '__main__':
    run_backtest()
