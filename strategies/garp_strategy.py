"""
GARP成长策略

策略逻辑：
- 合理价格成长股（Growth at a Reasonable Price）
- PEG = PE / 盈利增速 < 1（合理估值）
- 营收增速>15%，净利润增速>20%
- ROE>10%（盈利质量保障）
- 适用于中长期持有

参考：myhhub/stock - 长江证券GARP30组合年化12%+，胜率92%
"""

from strategies.base import BaseStrategy


class GARPStrategy(BaseStrategy):
    """GARP成长策略"""

    def __init__(self,
                 max_peg=1.0,       # PEG上限
                 min_revenue_growth=15,  # 营收增速下限%
                 min_profit_growth=20,   # 净利润增速下限%
                 min_roe=10,             # ROE下限%
                 max_pe=40,              # PE上限（避免极值）
                 holding_days=25,
                 top_n=5):
        super().__init__("GARP成长", "价值成长")
        self.max_peg = max_peg
        self.min_revenue_growth = min_revenue_growth
        self.min_profit_growth = min_profit_growth
        self.min_roe = min_roe
        self.max_pe = max_pe
        self.holding_days = holding_days
        self.top_n = top_n
        self._pool_cache = None

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

    def get_description(self):
        return f"GARP成长：PEG<{self.max_peg}, 营收>{self.min_revenue_growth}%, 净利>{self.min_profit_growth}%, ROE>{self.min_roe}%"

    def select_stocks(self, helper, date=None):
        """选股：GARP合理价格成长"""
        results = []

        # 1. 获取股票池
        pool = self._get_pool(helper, date)

        # 2. K线初步筛选：20日均线上方
        candidates = []
        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=30, end_date=date)
                if kline.empty or len(kline) < 20:
                    continue
                ma20 = kline['close'].rolling(20).mean().iloc[-1]
                if kline['close'].iloc[-1] > ma20:
                    candidates.append(symbol)
                if len(candidates) >= 8:
                    break
            except Exception:
                continue

        # 3. GARP筛选
        scored = []
        for symbol in candidates:
            try:
                growth = helper.get_growth_data(symbol)
                if not growth:
                    growth = {'profit_growth': 0, 'revenue_growth': 0}

                profit_growth = growth.get('profit_growth', 0)
                revenue_growth = growth.get('revenue_growth', 0)

                # 宽松模式：财务数据缺失时，降低增速要求
                has_growth_data = profit_growth > 0 or revenue_growth > 0
                if has_growth_data:
                    if profit_growth < self.min_profit_growth:
                        continue
                    if revenue_growth < self.min_revenue_growth:
                        continue
                else:
                    # 没有增速数据时，用ROE替代筛选
                    fin = helper.get_financial_indicator(symbol)
                    if not fin:
                        continue
                    roe = fin.get('roe', 0) * 100
                    if roe < 15:  # 要求ROE>15%作为替代
                        continue

                # 宽松模式已在上方处理fin，此处只保留需要的部分
                fin = helper.get_financial_indicator(symbol)
                if not fin:
                    continue
                roe = fin.get('roe', 0) * 100
                if roe < self.min_roe:
                    continue

                val = helper.get_valuation_data(symbol)
                if not val:
                    continue
                pe = val.get('pe', 0)
                if pe <= 0 or pe > self.max_pe:
                    continue

                # PEG = PE / 增速
                peg = pe / profit_growth if profit_growth > 0 else 999
                if peg > self.max_peg:
                    continue

                scored.append((symbol, peg, profit_growth, revenue_growth, roe, pe))
            except Exception:
                continue

        # 4. 按PEG排序（越小越好）
        scored.sort(key=lambda x: x[1])
        for symbol, peg, pg, rg, roe, pe in scored[:self.top_n]:
            try:
                quote = helper.get_realtime_quote(symbol)
                name = quote.get('名称', symbol) if quote else symbol
            except Exception:
                name = symbol

            results.append({
                'symbol': symbol,
                'name': name,
                'reason': f"GARP：PEG={peg:.2f}, 净利增={pg:.0f}%, 营收增={rg:.0f}%, ROE={roe:.1f}%, PE={pe:.1f}"
            })

        return results[:self.top_n]


if __name__ == '__main__':
    s = GARPStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
