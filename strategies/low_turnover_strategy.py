"""
低波动选股策略

策略逻辑：
- 筛选近20日波动率最低的股票
- 要求股价在20日均线上方（趋势向上）
- 持有至波动率放大或跌破均线
- 适合震荡市/熊市防御

参考：低波动异象（学术研究证明低波动股票长期跑赢）
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class LowVolatilityStrategy:
    """低波动选股策略"""
    
    def __init__(self, 
                 lookback_days=20,  # 计算波动率天数
                 holding_days=20,  # 持仓天数
                 top_n=10):  # 持仓数量
        self.lookback_days = lookback_days
        self.holding_days = holding_days
        self.top_n = top_n
        self.name = "低波动"
        
    def get_price_data(self, code, days=30):
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
    
    def calculate_volatility(self, df):
        """计算年化波动率"""
        if df is None or len(df) < self.lookback_days:
            return None
        
        recent = df.tail(self.lookback_days)
        returns = recent['close'].pct_change().dropna()
        
        if len(returns) < 5:
            return None
        
        # 日波动率 * sqrt(252) = 年化波动率
        daily_vol = returns.std()
        annual_vol = daily_vol * np.sqrt(252) * 100  # 转为百分比
        
        return annual_vol
    
    def check_above_ma(self, df, ma_days=20):
        """检查是否在均线上方"""
        if df is None or len(df) < ma_days:
            return False
        
        recent = df.tail(ma_days)
        ma = recent['close'].mean()
        latest_close = recent['close'].iloc[-1]
        
        return latest_close > ma
    
    def generate_signal(self):
        """生成交易信号"""
        print(f"策略: {self.name}")
        print(f"筛选条件: 近{self.lookback_days}日波动率最低, 股价在{20}日均线上方")
        print(f"风控: 持有{self.holding_days}天, 跌破均线卖出")
        
        return {
            'strategy': self.name,
            'signal': 'SELECT_STOCKS',
            'filters': {
                'lookback_days': self.lookback_days,
                'volatility': '最低',
                'trend': '20日均线上方'
            },
            'holding_count': self.top_n,
            'holding_days': self.holding_days,
            'rebalance': f'every_{self.holding_days}_days',
            'note': '防御策略：低波动股票在熊市更抗跌',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = LowVolatilityStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
