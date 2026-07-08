"""
财务基本面过滤小市值策略

策略逻辑：
- 筛选总市值在50-200亿的小盘股
- 要求ROE > 10%（盈利能力）
- 要求净利润增速 > 5%
- 持有20只，等权配置
- 每月调仓一次

参考：邢不行 - 财务基本面过滤小市值（年化50.98%）
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tushare as ts


class FundamentalSmallCapStrategy:
    """财务基本面过滤小市值策略"""
    
    def __init__(self, 
                 min_market_cap=50,  # 亿
                 max_market_cap=200,  # 亿
                 min_roe=10,  # %
                 min_profit_growth=5,  # %
                 top_n=20):
        self.min_market_cap = min_market_cap
        self.max_market_cap = max_market_cap
        self.min_roe = min_roe
        self.min_profit_growth = min_profit_growth
        self.top_n = top_n
        self.name = "财务基本面过滤小市值"
        
    def get_stock_list(self):
        """获取股票列表"""
        pro = ts.pro_api()
        
        # 获取所有股票
        df = pro.stock_basic(exchange='', list_status='L')
        df = df[df['market'] == '北交所']  # 先试试北交所
        return df
    
    def get_financial_data(self, codes):
        """获取财务数据"""
        pro = ts.pro_api()
        
        try:
            # 获取ROE和净利润数据
            df = pro.fina_indicator(ts_code=','.join(codes[:100]), period='20251231')
            return df
        except Exception as e:
            print(f"获取财务数据失败: {e}")
            return None
    
    def get_market_cap(self, code):
        """获取总市值"""
        try:
            df = ts.pro_bar(ts_code=code, start_date=(datetime.now() - timedelta(days=5)).strftime('%Y%m%d'))
            if df is not None and len(df) > 0:
                # 市值数据需要从其他接口获取
                return None
        except:
            pass
        return None
    
    def generate_signal(self):
        """生成交易信号"""
        print(f"策略: {self.name}")
        print(f"筛选条件: 市值{self.min_market_cap}-{self.max_market_cap}亿, ROE>{self.min_roe}%, 净利润增速>{self.min_profit_growth}%")
        
        return {
            'strategy': self.name,
            'signal': 'SELECT_STOCKS',
            'filters': {
                'market_cap': f'{self.min_market_cap}-{self.max_market_cap}亿',
                'roe': f'>{self.min_roe}%',
                'profit_growth': f'>{self.min_profit_growth}%'
            },
            'holding_count': self.top_n,
            'rebalance': 'monthly',
            'date': datetime.now().strftime('%Y-%m-%d')
        }


if __name__ == '__main__':
    strategy = FundamentalSmallCapStrategy()
    signal = strategy.generate_signal()
    print("\n交易信号:")
    print(signal)
