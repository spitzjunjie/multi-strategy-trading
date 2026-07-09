"""
回购策略

策略逻辑：
- 上市公司发布回购预案=股价被低估信号
- 回购注销型+规模>2%效果最佳（开源证券研报：超额年化14.89%）
- 用高管增持作为回购信号替代（AKShare无直接回购接口）
- 叠加低估值+基本面筛选
- 适用于事件驱动中长期

参考：NengjiangLunpi/astockevent-mcp - A股公告事件Feed
      开源证券研报 - 回购组合超额年化14.89%，信息比率0.8
"""

from strategies.base import BaseStrategy


class RepurchaseStrategy(BaseStrategy):
    """回购策略（用高管增持替代信号）"""

    def __init__(self,
                 max_pe=20,         # PE上限（低估）
                 max_pb=2.0,        # PB上限
                 min_roe=8,         # ROE下限%
                 holding_days=30,
                 top_n=5):
        super().__init__("回购信号", "事件驱动")
        self.max_pe = max_pe
        self.max_pb = max_pb
        self.min_roe = min_roe
        self.holding_days = holding_days
        self.top_n = top_n
        self._pool_cache = None

    def get_description(self):
        return f"回购信号：高管增持+PE<{self.max_pe}+PB<{self.max_pb}+ROE>{self.min_roe}%"

    def select_stocks(self, helper, date=None):
        """选股：高管增持(回购信号)+低估+基本面"""
        results = []

        # 1. 获取高管增持/回购信号
        buyback_signals = []
        try:
            # 尝试获取高管交易数据
            df = helper.get_executive_trading()
            if df is not None and not df.empty:
                # 筛选增持（买入）
                for _, row in df.iterrows():
                    try:
                        change = float(row.get('变动股数', 0) or row.get('增减', 0) or 0)
                        if change > 0:
                            symbol = str(row.get('代码', row.get('股票代码', '')))
                            name = str(row.get('名称', row.get('股票简称', symbol)))
                            if symbol and len(symbol) == 6:
                                buyback_signals.append({'symbol': symbol, 'name': name})
                    except Exception:
                        continue
        except Exception:
            pass

        # 2. 如果无法获取高管数据，用低估+高ROE替代筛选
        if not buyback_signals:
            try:
                pool = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:30]
            except Exception:
                pool = ['600519', '600036', '601318', '000858', '600887',
                        '000333', '601166', '600276', '601012', '600030']
            buyback_signals = [{'symbol': s, 'name': s} for s in pool]

        # 3. 低估+基本面筛选
        scored = []
        for sig in buyback_signals[:15]:  # 限制数量避免API超限
            symbol = sig['symbol']
            try:
                val = helper.get_valuation_data(symbol)
                if not val:
                    continue
                pe = val.get('pe', 0)
                pb = val.get('pb', 0)
                if pe <= 0 or pe > self.max_pe:
                    continue
                if pb <= 0 or pb > self.max_pb:
                    continue

                fin = helper.get_financial_indicator(symbol)
                if not fin:
                    continue
                roe = fin.get('roe', 0) * 100
                if roe < self.min_roe:
                    continue

                # 趋势确认：K线20日均线上方
                kline = helper.get_history_kline(symbol, days=30, end_date=date)
                if kline.empty or len(kline) < 20:
                    continue
                ma20 = kline['close'].rolling(20).mean().iloc[-1]
                if kline['close'].iloc[-1] < ma20:
                    continue

                # 综合得分：PE越低+PB越低+ROE越高 = 得分越高
                score = (self.max_pe - pe) / self.max_pe + (self.max_pb - pb) / self.max_pb + roe / 50
                name = sig.get('name', symbol)
                scored.append((symbol, name, score, pe, pb, roe))
            except Exception:
                continue

        # 4. 按得分排序
        scored.sort(key=lambda x: x[2], reverse=True)
        for symbol, name, score, pe, pb, roe in scored[:self.top_n]:
            results.append({
                'symbol': symbol,
                'name': name,
                'reason': f"回购信号：PE={pe:.1f}, PB={pb:.2f}, ROE={roe:.1f}%, 得分={score:.2f}"
            })

        return results[:self.top_n]


if __name__ == '__main__':
    s = RepurchaseStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
