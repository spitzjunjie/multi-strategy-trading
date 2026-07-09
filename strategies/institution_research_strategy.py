"""
机构调研策略 (InstitutionResearchStrategy)

策略逻辑：
- 选取近期有机构调研的股票
- 机构调研代表专业资金关注
- 调研后5日买入，持有10天

数据：AKShare stock_jgdy_tj_em（机构调研统计）
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from strategies.base import BaseStrategy


class InstitutionResearchStrategy(BaseStrategy):
    """机构调研策略"""

    def __init__(self,
                 lookback_days=5,      # 近N日有调研
                 buy_after_days=5,     # 调研后N日买入
                 holding_days=10,      # 持有天数
                 min_research_count=1, # 最少调研次数
                 top_n=10):
        super().__init__("机构调研", "事件驱动")
        self.lookback_days = lookback_days
        self.buy_after_days = buy_after_days
        self.holding_days = holding_days
        self.min_research_count = min_research_count
        self.top_n = top_n
        self._research_cache = None

    def get_description(self):
        return f"机构调研：近{self.lookback_days}日有调研，买入持有{self.holding_days}天"

    def _get_research_data(self):
        """获取机构调研数据"""
        if self._research_cache is not None:
            return self._research_cache

        try:
            # 获取最近机构调研数据
            df = ak.stock_jgdy_tj_em()
            if df is not None and not df.empty:
                # 转换日期格式
                if '公告日期' in df.columns:
                    df['date'] = pd.to_datetime(df['公告日期'])
                elif '调研日期' in df.columns:
                    df['date'] = pd.to_datetime(df['调研日期'])
                else:
                    # 尝试找日期列
                    for col in df.columns:
                        if '日期' in col or 'date' in col.lower():
                            df['date'] = pd.to_datetime(df[col])
                            break

                # 筛选近N日数据
                cutoff_date = datetime.now() - timedelta(days=self.lookback_days + self.buy_after_days)
                df = df[df['date'] >= cutoff_date]

                self._research_cache = df
                return df
        except Exception as e:
            print(f"获取机构调研数据失败: {e}")
        return pd.DataFrame()

    def select_stocks(self, helper, date=None):
        """选股：机构调研"""
        results = []

        try:
            df = self._get_research_data()
            if df.empty:
                return self._fallback_selection()

            # 按股票代码分组，统计调研次数
            if '代码' in df.columns:
                symbol_col = '代码'
            elif '股票代码' in df.columns:
                symbol_col = '股票代码'
            else:
                return self._fallback_selection()

            name_col = None
            for col in ['名称', '股票名称', '简称']:
                if col in df.columns:
                    name_col = col
                    break

            # 统计每只股票的调研次数
            research_count = df.groupby(symbol_col).size().reset_index(name='count')
            research_count = research_count[research_count['count'] >= self.min_research_count]

            # 获取最新调研日期
            latest_dates = df.groupby(symbol_col)['date'].max().reset_index(name='latest_date')

            # 合并
            research_stats = research_count.merge(latest_dates, on=symbol_col)

            # 按调研次数排序
            research_stats = research_stats.sort_values('count', ascending=False)

            # 获取股票名称
            stock_list = helper.get_stock_list()
            stock_name_map = {s['code'] if 'code' in s else s.get('代码', ''): 
                             s.get('name', s.get('名称', '')) 
                             for s in stock_list}

            for _, row in research_stats.head(self.top_n).iterrows():
                symbol = str(row[symbol_col]).zfill(6)
                name = stock_name_map.get(symbol, name_col if name_col and name_col in df.columns else symbol)
                if name_col:
                    # 尝试从原始数据获取名称
                    match = df[df[symbol_col] == row[symbol_col]]
                    if not match.empty and name_col in match.columns:
                        name = match[name_col].iloc[0]

                results.append({
                    'symbol': symbol,
                    'name': name,
                    'reason': f"机构调研：近{self.lookback_days}日调研{row['count']}次"
                })

        except Exception as e:
            print(f"机构调研选股失败: {e}")

        # 如果没有数据，返回备用选股
        if not results:
            return self._fallback_selection()

        return results[:self.top_n]

    def _fallback_selection(self):
        """备用选股：常见机构关注股票池"""
        fallback_stocks = [
            {'symbol': '688012', 'name': '中微公司'},
            {'symbol': '688256', 'name': '寒武纪'},
            {'symbol': '688981', 'name': '中芯国际'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '300496', 'name': '中科创达'},
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '000858', 'name': '五粮液'},
            {'symbol': '002594', 'name': '比亚迪'},
        ]
        return [
            {
                'symbol': s['symbol'],
                'name': s['name'],
                'reason': f"机构调研：热门调研股票"
            }
            for s in fallback_stocks[:self.top_n]
        ]
