"""
股权激励策略

策略逻辑：
- 股权激励草案公告=管理层信心信号（开源证券：超额年化24.84%，信息比率1.13）
- 激励规模占比大、高管持股占比低是有效筛选指标
- 用财务数据筛选可能实施激励的公司（高ROE+低负债）
- 叠加股价动能确认
- 适用于事件驱动中长期

参考：NengjiangLunpi/astockevent-mcp - A股公告事件Feed
      开源证券研报 - 股权激励优选组合超额年化24.84%
"""

from strategies.base import BaseStrategy


class EquityIncentiveStrategy(BaseStrategy):
    """股权激励策略（用财务筛选替代公告信号）"""

    def __init__(self,
                 min_roe=8,             # ROE下限%（降低）
                 min_profit_growth=0,   # 净利润增速下限%（去掉增速要求）
                 max_debt_ratio=70,     # 负债率上限%（放宽）
                 max_pe=40,             # PE上限（放宽）
                 holding_days=30,
                 top_n=5):
        super().__init__("股权激励", "事件驱动")
        self.min_roe = min_roe
        self.min_profit_growth = min_profit_growth
        self.max_debt_ratio = max_debt_ratio
        self.max_pe = max_pe
        self.holding_days = holding_days
        self.top_n = top_n
        self._pool_cache = None

    def get_description(self):
        return f"股权激励：ROE>{self.min_roe}%, 增速>{self.min_profit_growth}%, 负债<{self.max_debt_ratio}%, PE<{self.max_pe}"

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
        """选股：激励特征+成长+低估"""
        results = []

        # 1. 获取股票池
        pool = self._get_pool(helper, date)

        # 2. K线初步筛选：趋势向上
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

        # 3. 激励特征筛选（高ROE+低负债+合理估值，去掉增速要求）
        scored = []
        for symbol in candidates:
            try:
                # 去掉增速要求，只用ROE筛选（股权激励本质是选好公司）
                fin = helper.get_financial_indicator(symbol)
                if not fin:
                    fin = {}
                roe = fin.get('roe', 0) * 100
                debt_ratio = fin.get('debt_ratio', 0) * 100
                if roe < self.min_roe:
                    continue
                if debt_ratio > self.max_debt_ratio:
                    continue

                val = helper.get_valuation_data(symbol)
                if not val:
                    continue
                pe = val.get('pe', 0)
                if pe <= 0 or pe > max(self.max_pe, 50):  # 放宽PE上限
                    continue

                # 激励特征得分：ROE越高+负债越低+PE越低 = 越可能实施激励
                score = roe / 10 + (self.max_debt_ratio - debt_ratio) / 70 + (self.max_pe - pe) / 40
                scored.append((symbol, score, roe, 0, debt_ratio, pe))
            except Exception:
                continue

        # 4. 按得分排序
        scored.sort(key=lambda x: x[1], reverse=True)
        for symbol, score, roe, pg, dr, pe in scored[:self.top_n]:
            try:
                quote = helper.get_realtime_quote(symbol)
                name = quote.get('名称', symbol) if quote else symbol
            except Exception:
                name = symbol

            results.append({
                'symbol': symbol,
                'name': name,
                'reason': f"激励特征：ROE={roe:.1f}%, 负债={dr:.0f}%, PE={pe:.1f}, 得分={score:.2f}"
            })

        return results[:self.top_n]


if __name__ == '__main__':
    s = EquityIncentiveStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
