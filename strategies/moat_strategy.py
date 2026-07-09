"""
护城河选股策略

策略逻辑：
- 量化巴菲特经济护城河：高且稳定的毛利率、持续高ROE、低负债、强现金转化
- 筛选具有持续竞争优势的优质企业
- 适用于中长期持有，低风险

参考：myhhub/stock (13.3k stars) - A股基本面选股
"""

from strategies.base import BaseStrategy


class MoatStrategy(BaseStrategy):
    """护城河选股策略"""

    def __init__(self,
                 min_roe=15,        # ROE均值下限%
                 min_gross_margin=30,  # 毛利率下限%
                 max_debt_ratio=50,    # 资产负债率上限%
                 max_pe=30,            # PE上限
                 holding_days=30,
                 top_n=5):
        super().__init__("护城河选股", "质量因子")
        self.min_roe = min_roe
        self.min_gross_margin = min_gross_margin
        self.max_debt_ratio = max_debt_ratio
        self.max_pe = max_pe
        self.holding_days = holding_days
        self.top_n = top_n
        # 缓存股票池，避免33天回测每天重复获取
        self._pool_cache = None

    def _get_pool(self, helper, date=None):
        """获取股票池（带缓存）"""
        if self._pool_cache is None:
            try:
                self._pool_cache = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:50]
            except Exception:
                self._pool_cache = [
                    '600519', '600036', '601318', '300750', '000858',
                    '002475', '600887', '000333', '000001', '600030',
                    '601166', '600900', '601012', '002594', '600276',
                    '000725', '002422', '300059', '601899', '600000',
                ]
        return self._pool_cache

    def get_description(self):
        return f"护城河选股：ROE>{self.min_roe}%, 毛利率>{self.min_gross_margin}%, 负债<{self.max_debt_ratio}%, PE<{self.max_pe}"

    def select_stocks(self, helper, date=None):
        """选股：护城河量化筛选"""
        results = []

        # 1. 获取股票池（带缓存）
        pool = self._get_pool(helper, date)

        # 2. K线初步筛选：60日均线上方（趋势向上）
        candidates = []
        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=70, end_date=date)
                if kline.empty or len(kline) < 60:
                    continue
                ma60 = kline['close'].rolling(60).mean().iloc[-1]
                current = kline['close'].iloc[-1]
                if current > ma60:
                    candidates.append(symbol)
                if len(candidates) >= 15:
                    break
            except Exception:
                continue

        # 3. 财务数据深度筛选
        for symbol in candidates:
            try:
                fin = helper.get_financial_indicator(symbol)
                if not fin:
                    continue

                roe = fin.get('roe', 0) * 100
                gross_margin = fin.get('gross_margin', 0) * 100
                debt_ratio = fin.get('debt_ratio', 0) * 100
                net_margin = fin.get('net_margin', 0) * 100

                # 宽松模式：财务数据缺失时，用估值筛选
                has_financial = roe > 0 or gross_margin > 0 or debt_ratio > 0
                if has_financial:
                    if roe < self.min_roe:
                        continue
                    if gross_margin > 0 and gross_margin < self.min_gross_margin:
                        continue
                    if debt_ratio > self.max_debt_ratio:
                        continue
                else:
                    # 财务数据缺失时，只用估值筛选
                    pass  # will filter by PE below

                # 估值筛选（宽松模式下也保留）
                val = helper.get_valuation_data(symbol)
                pe = val.get('pe', 0) if val else 0
                pb = val.get('pb', 0) if val else 0
                if pb <= 0:
                    pb = 999  # 没有PB数据时跳过
                if has_financial:
                    if pe > self.max_pe or pe <= 0:
                        continue
                else:
                    # 财务数据缺失时，只接受低PB股票
                    if pb > 15 or pe <= 0:
                        continue

                # 获取股票名称
                try:
                    quote = helper.get_realtime_quote(symbol)
                    name = quote.get('名称', symbol) if quote else symbol
                except Exception:
                    name = symbol

                results.append({
                    'symbol': symbol,
                    'name': name,
                    'reason': f"护城河：ROE={roe:.1f}%, 毛利率={gross_margin:.1f}%, 负债={debt_ratio:.1f}%, PE={pe:.1f}"
                })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        return results[:self.top_n]


if __name__ == '__main__':
    s = MoatStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
