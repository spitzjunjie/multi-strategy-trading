# -*- coding: utf-8 -*-
"""
网格交易策略

策略逻辑：
- 在震荡行情中，等间距买入卖出
- 设置网格上下限和格数
- 价格触及网格线时自动买卖
- 中风险，适合震荡市
- 注意：网格策略需要独立资金管理
- 适配3只持仓限制（每只标的独立网格）

参考：jordantete/grid_trading_bot - 网格交易
"""

from strategies.base import BaseStrategy


class GridTradingStrategy(BaseStrategy):
    """网格交易策略"""

    def __init__(self,
                 grid_count=5,           # 网格数量
                 grid_range=0.10,       # 网格幅度（上下10%）
                 base_price=None,       # 基准价格（None=当前价）
                 holding_days=60,       # 持有天数
                 top_n=3):
        super().__init__("网格交易", "另类策略")
        self.grid_count = grid_count
        self.grid_range = grid_range
        self.base_price = base_price
        self.holding_days = holding_days
        self.top_n = top_n
        self._pool_cache = None

    def _get_pool(self, helper, date=None):
        """获取股票池（带缓存）"""
        if self._pool_cache is None:
            try:
                self._pool_cache = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:30]
            except Exception:
                self._pool_cache = ['510300', '510500', '159915', '510050', '512000',
                                    '512880', '512760', '515000', '159928', '512010']
        return self._pool_cache

    def get_description(self):
        return (f"网格交易：{self.grid_count}格, 幅度±{self.grid_range*100:.0f}%, "
                f"持有{self.holding_days}天")

    def select_stocks(self, helper, date=None):
        """选股：网格交易（适合ETF和大盘股）"""
        results = []

        # 优先使用ETF
        etf_list = [
            {'symbol': '510300', 'name': '沪深300ETF'},
            {'symbol': '510500', 'name': '中证500ETF'},
            {'symbol': '159915', 'name': '创业板ETF'},
            {'symbol': '510050', 'name': '上证50ETF'},
        ]

        pool = self._get_pool(helper, date)

        # 先检查ETF
        for etf in etf_list:
            try:
                kline = helper.get_history_kline(etf['symbol'], days=60, end_date=date)
                if kline is None or kline.empty or len(kline) < 30:
                    continue

                current_price = kline['close'].iloc[-1]

                # 计算近期波动率
                returns = kline['close'].pct_change().dropna()
                volatility = returns.std() * 100

                # 计算近期高低点
                high_60d = kline['high'].iloc[-60:].max()
                low_60d = kline['low'].iloc[-60:].min()

                # 震荡特征：高低点幅度在一定范围内
                range_pct = (high_60d - low_60d) / low_60d * 100

                # 震荡市特征：波动率适中，高低点幅度15%-40%
                if 1 < volatility < 3 and 15 < range_pct < 40:
                    results.append({
                        'symbol': etf['symbol'],
                        'name': etf['name'],
                        'reason': f"网格交易(ETF)：波动率{volatility:.1f}%, 振幅{range_pct:.1f}%, 震荡市"
                    })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        # 备选：大盘蓝筹股
        if len(results) < self.top_n:
            for symbol in pool[:10]:
                try:
                    kline = helper.get_history_kline(symbol, days=60, end_date=date)
                    if kline is None or kline.empty or len(kline) < 30:
                        continue

                    current_price = kline['close'].iloc[-1]

                    # 计算波动率
                    returns = kline['close'].pct_change().dropna()
                    volatility = returns.std() * 100

                    # 计算高低点
                    high_60d = kline['high'].iloc[-60:].max()
                    low_60d = kline['low'].iloc[-60:].min()
                    range_pct = (high_60d - low_60d) / low_60d * 100

                    # 震荡市特征
                    if 1 < volatility < 2.5 and 10 < range_pct < 35:
                        val = helper.get_valuation_data(symbol)
                        pb = val.get('pb', 5) if val else 5

                        # 低PB更稳定
                        if pb < 3:
                            results.append({
                                'symbol': symbol,
                                'name': symbol,
                                'reason': f"网格交易：波动率{volatility:.1f}%, PB={pb:.1f}, 震荡特征"
                            })

                    if len(results) >= self.top_n:
                        break
                except Exception:
                    continue

        return results[:self.top_n]


if __name__ == '__main__':
    s = GridTradingStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
