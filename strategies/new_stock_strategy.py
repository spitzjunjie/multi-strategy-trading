"""
次新股策略

策略逻辑：
- 上市次新股波动大，资金关注度高
- 上市1-6个月的次新股最具交易价值（开板后企稳）
- 筛选K线数据较短（上市时间短）+放量+趋势向上的次新股
- 短线持有5-10天

参考：zhangjc138/quant_project - 次新股策略
"""

from strategies.base import BaseStrategy


class NewStockStrategy(BaseStrategy):
    """次新股策略"""

    def __init__(self,
                 min_kline_days=20,   # K线最少天数（上市时间短）
                 max_kline_days=120,  # K线最多天数（上市6个月内）
                 min_volume_ratio=1.5,  # 量比下限
                 holding_days=8,
                 top_n=5):
        super().__init__("次新股", "事件驱动")
        self.min_kline_days = min_kline_days
        self.max_kline_days = max_kline_days
        self.min_volume_ratio = min_volume_ratio
        self.holding_days = holding_days
        self.top_n = top_n
        self._pool_cache = None

        # 次新股池（2025-2026年上市，具体需动态更新）
        # 这里用K线数据长度判断是否为次新股
        self.fallback_pool = [
            '301601', '301602', '301603', '301605', '301606',
            '301610', '301611', '301612', '301615', '301618',
            '601318', '601698', '601699', '601700', '601701',
        ]

    def get_description(self):
        return f"次新股：上市{self.min_kline_days}-{self.max_kline_days}天, 量比>{self.min_volume_ratio}, 持有{self.holding_days}天"

    def _get_pool(self, helper, date=None):
        """获取股票池（带缓存，次新股范围）"""
        if self._pool_cache is None:
            try:
                # 获取全市场股票，筛选次新股
                pool = helper.get_stock_pool("hs300", sorted_by_market_value=True)
                # 扩大范围以包含次新股
                if len(pool) < 80:
                    pool = helper.get_stock_pool("all", sorted_by_market_value=True)[:100]
                self._pool_cache = pool
            except Exception:
                self._pool_cache = [
                    '301601', '301602', '301603', '301605', '301606',
                    '301610', '301611', '301612', '301615', '301618',
                    '601318', '601698', '601699', '601700', '601701',
                ]
        return self._pool_cache

    def select_stocks(self, helper, date=None):
        """选股：次新股+放量+趋势"""
        results = []

        # 1. 获取股票池
        pool = self._get_pool(helper, date)

        # 2. 筛选次新股（K线数据长度判断上市时间）
        scored = []
        for symbol in pool[:30]:
            try:
                # 获取较多天数K线，看实际有多少数据
                kline = helper.get_history_kline(symbol, days=150, end_date=date)
                if kline.empty:
                    continue

                kline_len = len(kline)
                # 次新股：K线数据在20-120条之间（上市1-6个月）
                if kline_len < self.min_kline_days or kline_len > self.max_kline_days:
                    continue

                # 3. 放量确认
                vol_today = kline['volume'].iloc[-1]
                vol_ma5 = kline['volume'].iloc[-5:].mean() if len(kline) >= 5 else vol_today
                volume_ratio = vol_today / vol_ma5 if vol_ma5 > 0 else 0

                if volume_ratio < self.min_volume_ratio:
                    continue

                # 4. 趋势向上
                current = kline['close'].iloc[-1]
                if len(kline) >= 10:
                    ma10 = kline['close'].iloc[-10:].mean()
                    if current < ma10:
                        continue

                # 5. 不追高：涨幅<7%
                if len(kline) >= 2:
                    today_ret = (current / kline['close'].iloc[-2] - 1) * 100
                    if today_ret > 7:
                        continue

                # 综合得分：量比越大+K线越短（越新）= 得分越高
                score = volume_ratio + (self.max_kline_days - kline_len) / 20
                scored.append((symbol, score, volume_ratio, kline_len))
            except Exception:
                continue

        # 6. 按得分排序
        scored.sort(key=lambda x: x[1], reverse=True)
        for symbol, score, vol_ratio, kline_len in scored[:self.top_n]:
            try:
                quote = helper.get_realtime_quote(symbol)
                name = quote.get('名称', symbol) if quote else symbol
            except Exception:
                name = symbol

            results.append({
                'symbol': symbol,
                'name': name,
                'reason': f"次新股：上市{kline_len}天, 量比{vol_ratio:.1f}, 得分{score:.2f}"
            })

        return results[:self.top_n]


if __name__ == '__main__':
    s = NewStockStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
