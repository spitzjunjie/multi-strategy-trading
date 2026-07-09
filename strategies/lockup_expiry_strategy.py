"""
限售解禁策略

策略逻辑：
- 逆向博弈"利空出尽是利好"：解禁前被错杀，解禁后反弹
- 邢不行6909次解禁事件大数据：解禁前5日平均-1.34%
- 筛选近期待解禁股票（用次新股/小市值替代，解禁概率高）
- 叠加超跌+基本面支撑
- 适用于事件驱动逆向

参考：NengjiangLunpi/astockevent-mcp - A股公告事件Feed
      邢不行解禁数据研究 - 解禁前5日平均-1.34%
"""

from strategies.base import BaseStrategy


class LockupExpiryStrategy(BaseStrategy):
    """限售解禁策略（用超跌+小市值替代解禁信号）"""

    def __init__(self,
                 max_pb=3.0,           # PB上限
                 min_roe=5,            # ROE下限%（基本面支撑）
                 drop_threshold=-5,    # 近期跌幅阈值%（超跌）
                 holding_days=15,
                 top_n=5):
        super().__init__("解禁逆向", "事件驱动")
        self.max_pb = max_pb
        self.min_roe = min_roe
        self.drop_threshold = drop_threshold
        self.holding_days = holding_days
        self.top_n = top_n
        self._pool_cache = None

    def get_description(self):
        return f"解禁逆向：超跌{self.drop_threshold}%+PB<{self.max_pb}+ROE>{self.min_roe}%"

    def _get_pool(self, helper, date=None):
        """获取股票池（带缓存，取市值较小的）"""
        if self._pool_cache is None:
            try:
                pool = helper.get_stock_pool("hs300", sorted_by_market_value=True)
                self._pool_cache = pool[-30:] if len(pool) > 30 else pool
            except Exception:
                self._pool_cache = [
                    '300059', '002422', '000725', '300750', '002475',
                    '601012', '600276', '002594', '300015', '002241',
                ]
        return self._pool_cache

    def select_stocks(self, helper, date=None):
        """选股：超跌+基本面支撑（解禁逆向博弈）"""
        results = []

        # 1. 获取股票池（中小市值，解禁概率高）
        pool = self._get_pool(helper, date)

        # 2. 筛选超跌股票（近10日跌幅>阈值）
        candidates = []
        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=15, end_date=date)
                if kline.empty or len(kline) < 10:
                    continue

                current = kline['close'].iloc[-1]
                close_10d_ago = kline['close'].iloc[-10]
                ret_10d = (current / close_10d_ago - 1) * 100

                # 超跌：近10日跌幅超过阈值
                if ret_10d < self.drop_threshold:
                    # 止跌信号：近3日不再创新低
                    recent_3 = kline['close'].iloc[-3:]
                    if recent_3.iloc[-1] >= recent_3.min():
                        candidates.append((symbol, ret_10d))
                if len(candidates) >= 8:
                    break
            except Exception:
                continue

        # 3. 基本面支撑筛选
        scored = []
        for symbol, ret_10d in candidates:
            try:
                # PB估值
                val = helper.get_valuation_data(symbol)
                if not val:
                    continue
                pb = val.get('pb', 0)
                if pb <= 0 or pb > self.max_pb:
                    continue

                # ROE基本面
                fin = helper.get_financial_indicator(symbol)
                if not fin:
                    continue
                roe = fin.get('roe', 0) * 100
                if roe < self.min_roe:
                    continue

                # 逆向得分：跌幅越大+PB越低+ROE越高 = 反弹潜力越大
                score = abs(ret_10d) / 10 + (self.max_pb - pb) + roe / 20
                scored.append((symbol, score, ret_10d, pb, roe))
            except Exception:
                continue

        # 4. 按反弹潜力排序
        scored.sort(key=lambda x: x[1], reverse=True)
        for symbol, score, ret_10d, pb, roe in scored[:self.top_n]:
            try:
                quote = helper.get_realtime_quote(symbol)
                name = quote.get('名称', symbol) if quote else symbol
            except Exception:
                name = symbol

            results.append({
                'symbol': symbol,
                'name': name,
                'reason': f"解禁逆向：跌幅={ret_10d:.1f}%, PB={pb:.2f}, ROE={roe:.1f}%, 反弹得分={score:.2f}"
            })

        return results[:self.top_n]


if __name__ == '__main__':
    s = LockupExpiryStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
