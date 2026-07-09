"""
高成长股策略

策略逻辑：
- 筛选营收和净利润双高增长的股票
- 营收增速>30%，净利润增速>30%
- 叠加股价动能（20日均线上方）
- ROE>10%确保增长质量
- 适用于成长风格市场

参考：myhhub/stock - 天风长线金股7个年度年化超额均>18%
"""

from strategies.base import BaseStrategy


class HighGrowthStrategy(BaseStrategy):
    """高成长股策略"""

    def __init__(self,
                 min_revenue_growth=30,  # 营收增速下限%
                 min_profit_growth=30,   # 净利润增速下限%
                 min_roe=10,             # ROE下限%
                 holding_days=20,
                 top_n=5):
        super().__init__("高成长股", "成长因子")
        self.min_revenue_growth = min_revenue_growth
        self.min_profit_growth = min_profit_growth
        self.min_roe = min_roe
        self.holding_days = holding_days
        self.top_n = top_n
        self._pool_cache = None

    def get_description(self):
        return f"高成长股：营收>{self.min_revenue_growth}%, 净利>{self.min_profit_growth}%, ROE>{self.min_roe}%"

    def _get_pool(self, helper, date=None):
        """获取股票池（带缓存）"""
        if self._pool_cache is None:
            try:
                self._pool_cache = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:30]
            except Exception:
                self._pool_cache = [
                    '600519', '600036', '601318', '300750', '000858',
                    '002475', '600887', '000333', '000001', '600030',
                    '601166', '600900', '601012', '002594', '600276',
                ]
        return self._pool_cache

    def select_stocks(self, helper, date=None):
        """选股：高成长+动能"""
        results = []

        # 1. 获取股票池
        pool = self._get_pool(helper, date)

        # 2. K线初步筛选：20日均线上方 + 近5日涨幅>0
        candidates = []
        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=30, end_date=date)
                if kline.empty or len(kline) < 20:
                    continue
                ma20 = kline['close'].rolling(20).mean().iloc[-1]
                current = kline['close'].iloc[-1]
                if current > ma20:
                    # 近5日涨幅
                    if len(kline) >= 5:
                        ret_5d = (current / kline['close'].iloc[-5] - 1) * 100
                    else:
                        ret_5d = 0
                    candidates.append((symbol, ret_5d))
                if len(candidates) >= 8:
                    break
            except Exception:
                continue

        # 3. 高成长筛选
        scored = []
        for symbol, ret_5d in candidates:
            try:
                growth = helper.get_growth_data(symbol)
                if not growth:
                    growth = {'profit_growth': 0, 'revenue_growth': 0}

                profit_growth = growth.get('profit_growth', 0)
                revenue_growth = growth.get('revenue_growth', 0)

                # 宽松模式：财务数据缺失时，用ROE>15%替代
                has_growth_data = profit_growth > 0 or revenue_growth > 0
                if has_growth_data:
                    if profit_growth < self.min_profit_growth:
                        continue
                    if revenue_growth < self.min_revenue_growth:
                        continue
                else:
                    fin = helper.get_financial_indicator(symbol)
                    if not fin:
                        continue
                    roe = fin.get('roe', 0) * 100
                    if roe < 15:
                        continue

                fin = helper.get_financial_indicator(symbol)
                if not fin:
                    continue
                roe = fin.get('roe', 0) * 100
                if roe < self.min_roe:
                    continue

                # 综合成长得分 = 增速均值 + 动能
                growth_score = (profit_growth + revenue_growth) / 2 + ret_5d
                scored.append((symbol, growth_score, profit_growth, revenue_growth, roe))
            except Exception:
                continue

        # 4. 按成长得分排序
        scored.sort(key=lambda x: x[1], reverse=True)
        for symbol, score, pg, rg, roe in scored[:self.top_n]:
            try:
                quote = helper.get_realtime_quote(symbol)
                name = quote.get('名称', symbol) if quote else symbol
            except Exception:
                name = symbol

            results.append({
                'symbol': symbol,
                'name': name,
                'reason': f"高成长：净利增={pg:.0f}%, 营收增={rg:.0f}%, ROE={roe:.1f}%, 动能+{score:.1f}"
            })

        return results[:self.top_n]


if __name__ == '__main__':
    s = HighGrowthStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
