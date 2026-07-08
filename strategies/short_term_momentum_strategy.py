"""
短线动量策略

策略逻辑：
- 筛选近5日涨幅前20%的股票（强势股）
- 要求成交量持续放大
- 持有3-5天，快速止盈止损
- 止损：-3%，止盈：+5%

参考：A股短线交易策略
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class ShortTermMomentumStrategy:
    """短线动量策略"""
    
    def __init__(self, 
                 lookback_days=5,  # 回看天数
                 top_percentile=20,  # 涨幅前百分比
                 holding_days=3,  # 持仓天数
                 stop_loss=3,  # 止损%
                 take_profit=5,  # 止盈%
                 top_n=5):  # 持仓数量
        self.lookback_days = lookback_days
        self.top_percentile = top_percentile
        self.holding_days = holding_days
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.top_n = top_n
        self.name = "短线动量"
        
    def get_price_data(self, code, days=10):
        """获取价格数据"""
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days+10)).strftime('%Y%m%d')
            
            df = ts.pro_bar(ts_code=code, start_date=start_date, end_date=end_date, 
                          asset='E', adj='qfq')
            if df is not None and len(df) >= self.lookback_days:
                df = df.sort_values('trade_date')
                return df
        except Exception as e:
            print(f"获取{code}数据失败: {e}")
        return None
    
    def calculate_return(self, df):
        """计算区间涨幅"""
        if df is None or len(df) < self.lookback_days:
            return None
        
        recent = df.tail(self.lookback_days)
        start_price = recent['close'].iloc[0]
        end_price = recent['close'].iloc[-1]
        
        return (end_price / start_price - 1) * 100
    
    def check_volume_increase(self, df):
        """检查成交量是否持续放大"""
        if df is None or len(df) < self.lookback_days:
            return False
        
        recent = df.tail(self.lookback_days)
        # 近3天成交量相比前3天平均成交量放大1.5倍
        recent_vol = recent['vol'].tail(3).mean()
        prev_vol = recent['vol'].head(-3).mean() if len(recent) > 3 else recent_vol
        
        if prev_vol == 0:
            return False
        
        return recent_vol / prev_vol > 1.5
    
    def generate_signal(self):
        """生成交易信号"""
        print(f"策略: {self.name}")
        print(f"筛选条件: 近{self.lookback_days}日涨幅前{self.top_percentile}%, 成交量放大")
        print(f"风控: 止损{self.stop_loss}%, 止盈{self.take_profit}%, 持有{self.holding_days}天")
        
        return {
            'strategy': self.name,
            'signal': 'SELECT_STOCKS',
            'filters': {
                'lookback_days': self.lookback_days,
                'top_percentile': f'前{self.top_percentile}%',
                'volume_increase': '>1.5倍'
            },
            'holding_count': self.top_n,
            'holding_days': self.holding_days,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'rebalance': f'every_{self.holding_days}_days',
            'note': '短线策略：追强势、快进快出、严格止损',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = ShortTermMomentumStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
