# -*- coding: utf-8 -*-
"""
集合竞价选股策略

策略逻辑：
- 9:25竞价结束时筛选高开股
- 竞价涨幅3%-8%（避免一字板）
- 竞价量比>2倍
- 配合K线趋势确认
- 次日开盘执行，短线持有1-2天

参考：online0001/short-term-stock-picker - 竞价选股
"""

from strategies.base import BaseStrategy


class AuctionSelectionStrategy(BaseStrategy):
    """集合竞价选股策略"""

    def __init__(self,
                 min_open_pct=3.0,    # 最低竞价涨幅%
                 max_open_pct=8.0,    # 最高竞价涨幅%
                 min_volume_ratio=2.0,  # 最低量比
                 holding_days=2,      # 持有天数
                 top_n=5):
        super().__init__("集合竞价选股", "短线事件")
        self.min_open_pct = min_open_pct
        self.max_open_pct = max_open_pct
        self.min_volume_ratio = min_volume_ratio
        self.holding_days = holding_days
        self.top_n = top_n
        self._pool_cache = None

    def _get_pool(self, helper, date=None):
        """获取股票池（带缓存）"""
        if self._pool_cache is None:
            try:
                self._pool_cache = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:30]
            except Exception:
                self._pool_cache = ['600519', '600036', '601318', '000858', '600887',
                                    '000333', '601166', '600276', '601012', '600030',
                                    '600028', '601166', '600900', '601398', '601288']
        return self._pool_cache

    def get_description(self):
        return (f"集合竞价：涨幅{self.min_open_pct}%-{self.max_open_pct}%, "
                f"量比>{self.min_volume_ratio}, 持有{self.holding_days}天")

    def select_stocks(self, helper, date=None):
        """选股：集合竞价高开"""
        results = []

        # 获取热门股票池（竞价时段成交量大）
        pool = self._get_pool(helper, date)

        for symbol in pool:
            try:
                # 获取近期K线
                kline = helper.get_history_kline(symbol, days=20, end_date=date)
                if kline is None or kline.empty or len(kline) < 10:
                    continue

                # 计算竞价相关指标（用前一日数据模拟）
                prev_close = kline['close'].iloc[-2]
                prev_open = kline['open'].iloc[-2]
                prev_vol = kline['volume'].iloc[-2]
                prev_vol_ma5 = kline['volume'].iloc[-7:-2].mean()

                # 模拟竞价涨幅（前一日开盘与前一日收盘的偏离）
                open_gap = (prev_open - prev_close) / prev_close * 100

                # 模拟竞价量比（前一日开盘量与均量比）
                if prev_vol_ma5 > 0:
                    vol_ratio = prev_vol / prev_vol_ma5
                else:
                    vol_ratio = 1.0

                # 筛选条件
                if self.min_open_pct <= open_gap <= self.max_open_pct and vol_ratio >= self.min_volume_ratio:
                    # K线趋势确认：20日均线向上
                    ma20 = kline['close'].iloc[-20:].mean() if len(kline) >= 20 else kline['close'].mean()
                    if kline['close'].iloc[-1] > ma20:
                        results.append({
                            'symbol': symbol,
                            'name': symbol,
                            'reason': f"竞价选股：竞价涨幅{open_gap:.1f}%, 量比{vol_ratio:.1f}倍"
                        })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        # 备选：宽松条件
        if not results:
            for symbol in pool[:10]:
                try:
                    kline = helper.get_history_kline(symbol, days=10, end_date=date)
                    if kline is None or kline.empty:
                        continue
                    # 近期有放量上涨
                    vol_ma5 = kline['volume'].iloc[-5:].mean()
                    vol_prev = kline['volume'].iloc[-6:-1].mean()
                    if vol_prev > 0 and vol_ma5 / vol_prev > 1.5:
                        ret = (kline['close'].iloc[-1] / kline['close'].iloc[-5] - 1) * 100
                        if 2 < ret < 10:
                            results.append({
                                'symbol': symbol,
                                'name': symbol,
                                'reason': f"竞价备选：近期涨幅{ret:.1f}%, 放量{vol_ma5/vol_prev:.1f}倍"
                            })
                    if len(results) >= self.top_n:
                        break
                except Exception:
                    continue

        return results[:self.top_n]


if __name__ == '__main__':
    s = AuctionSelectionStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
