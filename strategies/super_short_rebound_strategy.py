"""
超跌反弹策略

策略逻辑：
- 筛选近10日跌幅超过15%的股票（严重超跌）
- 要求RSI < 35（极度超卖）
- 要求股价不低于5元（避免低价垃圾股）
- 持有5个交易日后卖出
- 止损：-5%

参考：经典逆向投资策略
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class SuperShortReboundStrategy:
    """超跌反弹策略"""
    
    def __init__(self, 
                 lookback_days=10,  # 回看天数
                 min_drop=15,  # 最小跌幅 %
                 max_rsi=35,  # RSI最大值
                 min_price=5,  # 最低股价
                 holding_days=5,  # 持仓天数
                 stop_loss=5,  # 止损%
                 top_n=10):  # 持仓数量
        self.lookback_days = lookback_days
        self.min_drop = min_drop
        self.max_rsi = max_rsi
        self.min_price = min_price
        self.holding_days = holding_days
        self.stop_loss = stop_loss
        self.top_n = top_n
        self.name = "超跌反弹"
        
    def get_price_data(self, code, days=20):
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
    
    def calculate_rsi(self, df, period=14):
        """计算RSI"""
        if df is None or len(df) < period + 1:
            return None
        
        prices = df['close'].values
        deltas = np.diff(prices)
        
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_drop(self, df):
        """计算区间跌幅（返回负数）"""
        if df is None or len(df) < self.lookback_days:
            return None
        
        recent = df.tail(self.lookback_days)
        start_price = recent['close'].iloc[0]
        end_price = recent['close'].iloc[-1]
        
        drop = (end_price / start_price - 1) * 100
        return drop
    
    def generate_signal(self):
        """生成交易信号"""
        print(f"策略: {self.name}")
        print(f"筛选条件: 近{self.lookback_days}日跌幅>{self.min_drop}%, RSI<{self.max_rsi}, 股价>{self.min_price}元")
        print(f"风控: 止损{self.stop_loss}%, 持有{self.holding_days}天")
        
        return {
            'strategy': self.name,
            'signal': 'SELECT_STOCKS',
            'filters': {
                'lookback_days': self.lookback_days,
                'min_drop': f'>{self.min_drop}%',
                'max_rsi': self.max_rsi,
                'min_price': f'>{self.min_price}元'
            },
            'holding_count': self.top_n,
            'holding_days': self.holding_days,
            'stop_loss': self.stop_loss,
            'rebalance': f'every_{self.holding_days}_days',
            'note': '逆向策略：严重超跌后反弹，但需严格止损',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = SuperShortReboundStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
