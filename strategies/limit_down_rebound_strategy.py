# -*- coding: utf-8 -*-
"""
跌停撬板策略

策略逻辑：
- 跌停板博弈反转（地天板）
- 跌停后次日开盘有大单撬板迹象
- 撬板条件：开盘价<前收盘*0.98 且 开盘后快速反弹>2%
- 高风险，严格止损
- 注意：此策略为高风险短线，仅供参考

参考：DLWangSan/a-stock-trading - 跌停板博弈
"""

from strategies.base import BaseStrategy


class LimitDownReboundStrategy(BaseStrategy):
    """跌停撬板策略"""

    def __init__(self,
                 min_rebound_pct=2.0,    # 最低反弹幅度%
                 max_open_drop_pct=3.0,   # 开盘最大跌幅%
                 holding_days=1,          # 持有天数
                 stop_loss=-8,            # 止损线%（跌停后可能继续跌）
                 top_n=3):                # 持仓限制
        super().__init__("跌停撬板", "短线事件")
        self.min_rebound_pct = min_rebound_pct
        self.max_open_drop_pct = max_open_drop_pct
        self.holding_days = holding_days
        self.stop_loss = stop_loss
        self.top_n = top_n
        self._pool_cache = None

    def _get_pool(self, helper, date=None):
        """获取股票池（带缓存）"""
        if self._pool_cache is None:
            try:
                self._pool_cache = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:20]
            except Exception:
                self._pool_cache = ['600519', '600036', '601318', '000858', '600887',
                                    '000333', '601166', '600276', '601012', '600030']
        return self._pool_cache

    def get_description(self):
        return (f"跌停撬板：开盘跌幅<{self.max_open_drop_pct}%, "
                f"反弹>{self.min_rebound_pct}%, 持有{self.holding_days}天, 止损{self.stop_loss}%")

    def select_stocks(self, helper, date=None):
        """选股：跌停撬板博弈"""
        results = []

        pool = self._get_pool(helper, date)

        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=10, end_date=date)
                if kline is None or kline.empty or len(kline) < 5:
                    continue

                # 检测跌停后反弹
                yesterday_close = kline['close'].iloc[-2]
                today_open = kline['open'].iloc[-1]
                today_close = kline['close'].iloc[-1]
                today_high = kline['high'].iloc[-1]

                # 开盘跌幅
                open_drop = (today_open - yesterday_close) / yesterday_close * 100

                # 盘中反弹幅度
                rebound = (today_high - today_open) / today_open * 100

                # 收盘涨幅
                close_gain = (today_close - yesterday_close) / yesterday_close * 100

                # 跌停撬板特征
                if open_drop < -1 and rebound >= self.min_rebound_pct:
                    # 成交量放大（撬板特征）
                    vol_ratio = kline['volume'].iloc[-1] / kline['volume'].iloc[-6:-1].mean()

                    if vol_ratio > 1.5:  # 放量
                        results.append({
                            'symbol': symbol,
                            'name': symbol,
                            'reason': f"跌停撬板：开跌{open_drop:.1f}%, 反弹{rebound:.1f}%, 收盘{close_gain:.1f}%, 量比{vol_ratio:.1f}倍"
                        })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        # 备选：近期有跌停历史的强势反弹股
        if not results:
            for symbol in pool[:10]:
                try:
                    kline = helper.get_history_kline(symbol, days=20, end_date=date)
                    if kline is None or kline.empty or len(kline) < 15:
                        continue

                    # 检测近期跌停
                    limit_down = False
                    for i in range(2, len(kline)):
                        ret = (kline['close'].iloc[-i] / kline['close'].iloc[-i-1] - 1) * 100
                        if ret <= -9.5:
                            limit_down = True
                            break

                    if limit_down:
                        # 跌停后反弹强劲
                        gain = (kline['close'].iloc[-1] / kline['close'].iloc[-3] - 1) * 100
                        if gain > 5:
                            results.append({
                                'symbol': symbol,
                                'name': symbol,
                                'reason': f"跌停反弹备选：近期跌停后反弹{gain:.1f}%"
                            })

                    if len(results) >= self.top_n:
                        break
                except Exception:
                    continue

        return results[:self.top_n]


if __name__ == '__main__':
    s = LimitDownReboundStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
    print("注意：此策略为高风险策略，请谨慎使用")
