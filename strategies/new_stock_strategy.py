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

        # 次新股池（上市1年内，用固定池避免K线长度判断不稳定）
        self.new_stock_pool = [
            # 2024-2025年上市（按时间排序，越新越活跃）
            '301601', '301606', '301608', '301610', '301612',
            '301618', '301626', '301628', '301636', '301638',
            '301656', '688558', '688575', '688601', '688621',
            '301566', '301585', '301586', '301601', '301271',
            '301296', '301308', '301323', '301326', '301339',
            '301368', '301369', '301376', '301378', '301386',
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

        # 1. 获取股票池（优先用固定次新股池，K线判断作为补充）
        try:
            pool = helper.get_stock_pool("hs300", sorted_by_market_value=True)
            # 混合：先用固定次新股池的20只，再用沪深300前20只
            mixed_pool = self.new_stock_pool[:20]
            for s in pool[:20]:
                if s not in mixed_pool:
                    mixed_pool.append(s)
            pool = mixed_pool
        except Exception:
            pool = self.new_stock_pool[:20]

        # 2. 筛选次新股（K线数据长度判断 + 固定池优先）
        scored = []
        for symbol in pool[:40]:  # 缩小范围从80到40，减少API调用
            try:
                # 获取较多天数K线，看实际有多少数据
                kline = helper.get_history_kline(symbol, days=150, end_date=date)
                if kline.empty:
                    continue

                kline_len = len(kline)
                # 宽松判断：K线20-150条之间，或者股票在固定池中（已上市的次新股）
                in_fixed_pool = symbol in self.new_stock_pool
                if not in_fixed_pool and (kline_len < self.min_kline_days or kline_len > self.max_kline_days):
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
