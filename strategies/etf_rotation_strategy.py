"""
ETF二八轮动策略

策略逻辑：
- 比较沪深300ETF(510300)和中证1000ETF(512010)的20日涨幅
- 哪个强持有哪个
- 每月第一个交易日调仓

适合：小资金（ETF免印花税）
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class ETFRotationStrategy:
    """ETF二八轮动策略"""
    
    def __init__(self, lookback_days=20):
        self.lookback_days = lookback_days
        self.name = "ETF二八轮动"
        
    def get_etf_data(self, code, start_date, end_date):
        """获取ETF数据"""
        try:
            df = ts.pro_bar(ts_code=code, start_date=start_date, end_date=end_date, asset='E')
            if df is not None and len(df) > 0:
                df = df.sort_values('trade_date')
                return df
        except Exception as e:
            print(f"获取{code}数据失败: {e}")
        return None
    
    def calculate_return(self, df, days=20):
        """计算区间涨幅"""
        if df is None or len(df) < days:
            return None
        recent = df.tail(days)
        return (recent['close'].iloc[-1] / recent['close'].iloc[0] - 1) * 100
    
    def select_etf(self):
        """选择最强的ETF"""
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')
        
        # 沪深300ETF
        hs300_df = self.get_etf_data('510300.SH', start_date, end_date)
        hs300_return = self.calculate_return(hs300_df, self.lookback_days)
        
        # 中证1000ETF
        zz1000_df = self.get_etf_data('512010.SH', start_date, end_date)
        zz1000_return = self.calculate_return(zz1000_df, self.lookback_days)
        
        if hs300_return is None or zz1000_return is None:
            return None, None
        
        print(f"沪深300ETF近{self.lookback_days}日涨幅: {hs300_return:.2f}%")
        print(f"中证1000ETF近{self.lookback_days}日涨幅: {zz1000_return:.2f}%")
        
        if hs300_return > zz1000_return:
            return '510300.SH', hs300_return
        else:
            return '512010.SH', zz1000_return
    
    def generate_signal(self):
        """生成交易信号"""
        etf, ret = self.select_etf()
        if etf is None:
            return None
        
        return {
            'strategy': self.name,
            'signal': 'BUY',
            'code': etf,
            'return_20d': ret,
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = ETFRotationStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
