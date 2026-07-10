# -*- coding: utf-8 -*-
"""
尾盘抢筹策略

策略逻辑：
- 14:30后异动选股（黄金两点半）
- 14:30-14:50涨幅>2%且成交量放大
- 配合当日分时走势确认
- 次日开盘执行，尾盘卖出
- 中风险，适合短线

参考：zhangjc138/quant_project - 尾盘选股
"""

from strategies.base import BaseStrategy


class AfterHoursMomentumStrategy(BaseStrategy):
    """尾盘抢筹策略"""

    def __init__(self,
                 min_gain_pct=2.0,     # 最低涨幅%
                 min_vol_ratio=1.5,    # 最低量比
                 time_window='14:30-14:50',  # 时间窗口
                 holding_days=1,        # 持有天数
                 top_n=5):
        super().__init__("尾盘抢筹", "短线事件")
        self.min_gain_pct = min_gain_pct
        self.min_vol_ratio = min_vol_ratio
        self.time_window = time_window
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
        return (f"尾盘抢筹：涨幅>{self.min_gain_pct}%, 量比>{self.min_vol_ratio}, "
                f"{self.time_window}异动, 持有{self.holding_days}天")

    def select_stocks(self, helper, date=None):
        """选股：尾盘异动抢筹"""
        results = []

        pool = self._get_pool(helper, date)

        for symbol in pool:
            try:
                # 获取近期K线
                kline = helper.get_history_kline(symbol, days=15, end_date=date)
                if kline is None or kline.empty or len(kline) < 10:
                    continue

                # 模拟尾盘异动（用14:00-14:50的数据）
                # 用最近几日数据判断尾盘特征
                gains = []
                vol_ratios = []
                for i in range(1, min(5, len(kline))):
                    prev_close = kline['close'].iloc[-i-1]
                    curr_close = kline['close'].iloc[-i]
                    curr_vol = kline['volume'].iloc[-i]
                    prev_vol = kline['volume'].iloc[-i-5:-i].mean() if i < 5 else kline['volume'].iloc[-5:].mean()

                    # 模拟尾盘涨幅
                    gain = (curr_close - prev_close) / prev_close * 100
                    gains.append(gain)
                    if prev_vol > 0:
                        vol_ratios.append(curr_vol / prev_vol)

                # 满足尾盘异动特征
                if gains and vol_ratios:
                    avg_gain = sum(gains) / len(gains)
                    avg_vol_ratio = sum(vol_ratios) / len(vol_ratios)

                    if avg_gain >= self.min_gain_pct and avg_vol_ratio >= self.min_vol_ratio:
                        results.append({
                            'symbol': symbol,
                            'name': symbol,
                            'reason': f"尾盘抢筹：近期均涨幅{avg_gain:.1f}%, 量比{avg_vol_ratio:.1f}倍"
                        })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        # 备选：趋势股尾盘表现
        if not results:
            for symbol in pool[:10]:
                try:
                    kline = helper.get_history_kline(symbol, days=20, end_date=date)
                    if kline is None or kline.empty or len(kline) < 15:
                        continue

                    # 趋势向上
                    ma5 = kline['close'].iloc[-5:].mean()
                    ma20 = kline['close'].iloc[-20:].mean() if len(kline) >= 20 else kline['close'].mean()

                    if ma5 > ma20 * 1.02:  # 上升趋势
                        # 近3日有尾盘异动迹象
                        vol_ma5 = kline['volume'].iloc[-5:].mean()
                        vol_prev = kline['volume'].iloc[-6]
                        if vol_prev > 0 and vol_ma5 / vol_prev > 1.3:
                            results.append({
                                'symbol': symbol,
                                'name': symbol,
                                'reason': f"尾盘备选：上升趋势, 量能放大{vol_ma5/vol_prev:.1f}倍"
                            })

                    if len(results) >= self.top_n:
                        break
                except Exception:
                    continue

        return results[:self.top_n]


if __name__ == '__main__':
    s = AfterHoursMomentumStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
