# -*- coding: utf-8 -*-
"""
SEPA成长股选股策略

策略逻辑：
- 基于Mark Minervini的SEPA(Superior Performance Plan)方法论
- SEPA技术面8条简化为可落地版：
  1. 股价>200日均线（数据不足用60日均线替代并标注）
  2. 200日（或60日）均线呈上升趋势（近20日均线斜率>0）
  3. 股价>50日均线
  4. 50日均线>200日（或60日）均线
  5. 股价距52周高点不超过25%（高相对强度）
  6. 基本面：营收增速>15%或ROE>12%（获取不到基本面则跳过此条件）
- 计算相对强度RS = 个股近60日涨幅排名百分位，按RS排序取前3

研究来源：Mark Minervini《Trade Like a Stock Market Wizard》SEPA方法论
参考风格：garp_strategy.py（基本面+K线结合）

参数：
- ma_long: 长期均线天数（默认200，降级用60）
- ma_short: 短期均线天数（默认50）
- max_from_high: 距52周高点上限%（默认25）
- min_revenue_growth: 营收增速下限%（默认15）
- holding_days: 持有天数（默认10）
- top_n: 最多选股数（默认3）
"""

from strategies.base import BaseStrategy


class SEPAGrowthStrategy(BaseStrategy):
    """SEPA成长股选股策略"""

    # 降级用硬编码30只成长股
    FALLBACK_POOL = [
        '600519', '300750', '688981', '688256', '300059',
        '002475', '000858', '600036', '601318', '002594',
        '600276', '601012', '000333', '688041', '300308',
        '000725', '002422', '600584', '002156', '603986',
        '300394', '300502', '002281', '600487', '688126',
        '605358', '600206', '301308', '300223', '002185',
    ]

    def __init__(self,
                 ma_long=200,
                 ma_short=50,
                 max_from_high=25,
                 min_revenue_growth=15,
                 holding_days=10,
                 top_n=3):
        super().__init__("SEPA成长股", "成长股选股")
        self.ma_long = ma_long
        self.ma_short = ma_short
        self.max_from_high = max_from_high
        self.min_revenue_growth = min_revenue_growth
        self.holding_days = holding_days
        self.top_n = top_n
        self._pool_cache = None

    def _get_pool(self, helper, date=None):
        """获取股票池（带缓存，降级用硬编码）"""
        if self._pool_cache is None:
            try:
                pool = helper.get_stock_pool("hs300", sorted_by_market_value=True)
                if pool and len(pool) > 0:
                    self._pool_cache = pool[:50]
                else:
                    self._pool_cache = self.FALLBACK_POOL
            except Exception:
                self._pool_cache = self.FALLBACK_POOL
        return self._pool_cache

    def get_description(self):
        return (f"SEPA成长股：>{self.ma_long}日线, >{self.ma_short}日线, "
                f"距高点<{self.max_from_high}%, 营收>{self.min_revenue_growth}%, 持有{self.holding_days}天")

    def _check_sepa_technical(self, kline):
        """
        检查SEPA技术面条件1-5
        返回: (通过与否, 实际使用的长均线, 距高点%, 近60日涨幅)
        """
        n = len(kline)
        if n < self.ma_short:
            return False, self.ma_long, 0.0, 0.0

        close = kline['close'].iloc[-1]

        # 长均线：优先200日，不足则降级60日
        use_long = self.ma_long
        long_version = "200日"
        if n < self.ma_long:
            use_long = 60
            long_version = "60日"
            if n < use_long:
                return False, use_long, 0.0, 0.0

        ma_long_val = kline['close'].rolling(use_long).mean().iloc[-1]
        ma_short_val = kline['close'].rolling(self.ma_short).mean().iloc[-1] if n >= self.ma_short else None

        # 条件1：股价 > 长均线
        if close <= ma_long_val:
            return False, use_long, 0.0, 0.0

        # 条件2：长均线呈上升趋势（近20日均线斜率>0）
        if n >= use_long + 20:
            ma_long_20ago = kline['close'].rolling(use_long).mean().iloc[-21]
            if ma_long_20ago is None or ma_long_val <= ma_long_20ago:
                return False, use_long, 0.0, 0.0
        # 数据不足时跳过此条件（降级）

        # 条件3：股价 > 短均线
        if ma_short_val is not None and close <= ma_short_val:
            return False, use_long, 0.0, 0.0

        # 条件4：短均线 > 长均线
        if ma_short_val is not None and ma_short_val <= ma_long_val:
            return False, use_long, 0.0, 0.0

        # 条件5：距52周高点不超过25%（数据不足用可用区间最高点）
        lookback = min(252, n)
        high_n = kline['high'].tail(lookback).max()
        if high_n <= 0:
            return False, use_long, 0.0, 0.0
        pct_from_high = (high_n - close) / high_n * 100
        if pct_from_high > self.max_from_high:
            return False, use_long, 0.0, 0.0

        # 近60日涨幅（用于RS排名）
        if n >= 61:
            ret60 = (close / kline['close'].iloc[-61] - 1) * 100
        elif n >= 2:
            ret60 = (close / kline['close'].iloc[0] - 1) * 100
        else:
            ret60 = 0.0

        return True, use_long, pct_from_high, ret60

    def select_stocks(self, helper, date=None):
        """选股：SEPA技术面筛选 + RS排名"""
        results = []
        pool = self._get_pool(helper, date)

        candidates = []  # (ret60, symbol, use_long, pct_from_high, name)

        for symbol in pool:
            try:
                # 尝试获取200天数据，不足则获取至少60天
                kline = helper.get_history_kline(symbol, days=self.ma_long + 10, end_date=date)
                if kline is None or kline.empty:
                    # 降级获取60天
                    kline = helper.get_history_kline(symbol, days=60, end_date=date)
                if kline is None or kline.empty or len(kline) < self.ma_short:
                    continue

                passed, use_long, pct_from_high, ret60 = self._check_sepa_technical(kline)
                if not passed:
                    continue

                # 基本面条件6：营收增速>15%或ROE>12%（获取不到则跳过此条件=通过）
                try:
                    growth = helper.get_growth_data(symbol)
                    fin = helper.get_financial_indicator(symbol)
                    revenue_growth = growth.get('revenue_growth', 0) if growth else 0
                    roe = fin.get('roe', 0) if fin else 0  # 小数
                    if growth or fin:
                        if not (revenue_growth > self.min_revenue_growth or roe > 0.12):
                            continue
                except Exception:
                    pass  # 基本面获取失败，跳过此条件

                # 获取股票名称
                name = symbol
                try:
                    quote = helper.get_realtime_quote(symbol)
                    if quote:
                        name = quote.get('名称', symbol)
                except Exception:
                    pass

                candidates.append((ret60, symbol, use_long, pct_from_high, name))
            except Exception:
                continue

        # 计算RS排名百分位：按ret60降序，排名越靠前RS越高
        candidates.sort(key=lambda x: x[0], reverse=True)
        n_cand = len(candidates)
        for idx, (ret60, symbol, use_long, pct_from_high, name) in enumerate(candidates[:self.top_n]):
            # RS百分位：第1名=100，最后一名接近0
            rs = (n_cand - idx) / n_cand * 100 if n_cand > 0 else 0
            ma_label = f"{use_long}日版" if use_long < self.ma_long else f"{use_long}日"
            if use_long < self.ma_long:
                ma_label = "(60日版)"
                ma_text = "60"
            else:
                ma_text = str(use_long)
            results.append({
                'symbol': symbol,
                'name': name,
                'reason': f"SEPA:RS={rs:.0f}, >{ma_text}日线, 距高点{pct_from_high:.0f}% {ma_label}"
            })

        # 降级处理：若没选出股票，返回硬编码池前3只
        if not results:
            for symbol in self.FALLBACK_POOL[:self.top_n]:
                try:
                    name = symbol
                    try:
                        quote = helper.get_realtime_quote(symbol)
                        if quote:
                            name = quote.get('名称', symbol)
                    except Exception:
                        pass
                    results.append({
                        'symbol': symbol,
                        'name': name,
                        'reason': "SEPA降级:无符合条件标的"
                    })
                except Exception:
                    continue

        return results[:self.top_n]


if __name__ == '__main__':
    s = SEPAGrowthStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
