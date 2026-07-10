# -*- coding: utf-8 -*-
"""
Hurst择时动量策略

策略逻辑：
- 基于丁鹏《量化投资》Hurst指数 + Chan均值回归vs动量方法论
- 通过R/S分析计算市场Hurst指数，判断市场状态：
  - H > 0.55：持续性（动量），选近5日涨幅最大的3只
  - H < 0.45：反持续性（均值回归），选近5日跌幅最大的3只（超跌反弹）
  - 0.45 ≤ H ≤ 0.55：随机游走，选近20日波动最小的3只（低波动）
- Hurst计算用简化版R/S分析法：分块计算R/S统计量，回归 log(R/S)=log(c)+H×log(N)

研究来源：丁鹏《量化投资》Hurst指数 + Ernie Chan均值回归vs动量
参考风格：short_term_momentum_strategy.py（硬编码标的池+K线筛选）

参数：
- hurst_window: Hurst计算窗口（默认50）
- lookback_days: 动量/回归回看天数（默认5）
- holding_days: 持有天数（默认5）
- top_n: 最多选股数（默认3）
"""

import numpy as np
from strategies.base import BaseStrategy


def calc_hurst(prices):
    """
    简化版Hurst指数（R/S分析）

    原理：将价格序列转为对数收益，分块计算每块R/S统计量，
    回归 log(R/S) = log(c) + H×log(N)，斜率H即Hurst指数。

    Args:
        prices: 价格序列（list或np.array）
    Returns:
        Hurst指数（0-1之间，0.5为随机游走）
    """
    prices = np.array(prices, dtype=float)
    n = len(prices)
    if n < 20:
        return 0.5  # 默认随机

    # 检查价格有效性
    if np.any(prices <= 0):
        # 过滤非正数
        prices = prices[prices > 0]
        n = len(prices)
        if n < 20:
            return 0.5

    returns = np.diff(np.log(prices))

    # 分块计算R/S
    rs_list = []
    ns = []
    for size in [10, 20, 25, 50]:
        if size > n:
            continue
        num_blocks = n // size
        if num_blocks < 1:
            continue
        rs_block = []
        for i in range(num_blocks):
            block = returns[i * size:(i + 1) * size]
            if len(block) < 2:
                continue
            mean = block.mean()
            cumdev = np.cumsum(block - mean)
            R = cumdev.max() - cumdev.min()
            S = block.std()
            if S > 0 and not np.isnan(R) and not np.isinf(R):
                rs_block.append(R / S)
        if rs_block:
            rs_list.append(np.mean(rs_block))
            ns.append(size)

    if len(ns) < 2:
        return 0.5

    # 回归 log(R/S) = log(c) + H*log(N)
    log_n = np.log(ns)
    log_rs = np.log(rs_list)
    try:
        h, _ = np.polyfit(log_n, log_rs, 1)
    except Exception:
        return 0.5

    # Hurst理论上0-1之间，异常值兜底
    if np.isnan(h) or np.isinf(h):
        return 0.5
    return float(h)


class HurstTimingStrategy(BaseStrategy):
    """Hurst择时动量策略"""

    # 硬编码20只活跃股
    STOCK_POOL = [
        {'symbol': '600519', 'name': '贵州茅台'},
        {'symbol': '300750', 'name': '宁德时代'},
        {'symbol': '688981', 'name': '中芯国际'},
        {'symbol': '688256', 'name': '寒武纪'},
        {'symbol': '300059', 'name': '东方财富'},
        {'symbol': '002475', 'name': '立讯精密'},
        {'symbol': '000858', 'name': '五粮液'},
        {'symbol': '600036', 'name': '招商银行'},
        {'symbol': '601318', 'name': '中国平安'},
        {'symbol': '002594', 'name': '比亚迪'},
        {'symbol': '600276', 'name': '恒瑞医药'},
        {'symbol': '601012', 'name': '隆基绿能'},
        {'symbol': '000333', 'name': '美的集团'},
        {'symbol': '688041', 'name': '海光信息'},
        {'symbol': '300308', 'name': '中际旭创'},
    ]

    # 用于计算市场Hurst的宽基指数（沪深300）
    MARKET_INDEX = '000300'

    def __init__(self,
                 hurst_window=50,
                 lookback_days=5,
                 holding_days=5,
                 top_n=3):
        super().__init__("Hurst择时动量", "择时策略")
        self.hurst_window = hurst_window
        self.lookback_days = lookback_days
        self.holding_days = holding_days
        self.top_n = top_n

    def get_description(self):
        return (f"Hurst择时：H>{0.55}动量/H<{0.45}回归/中间低波动, "
                f"窗口{self.hurst_window}天, 持有{self.holding_days}天")

    def _calc_market_hurst(self, helper, date=None):
        """计算市场Hurst指数，失败返回0.5（随机）"""
        try:
            kline = helper.get_history_kline(self.MARKET_INDEX, days=self.hurst_window + 10, end_date=date)
            if kline is None or kline.empty or len(kline) < 20:
                return 0.5
            prices = kline['close'].tail(self.hurst_window).values
            return calc_hurst(prices)
        except Exception:
            return 0.5

    def select_stocks(self, helper, date=None):
        """选股：Hurst判断市场状态，动量/回归/低波动分别选股"""
        results = []

        # 1. 计算市场Hurst指数
        H = self._calc_market_hurst(helper, date)

        # 2. 判断市场状态
        if H > 0.55:
            mode = "动量"
        elif H < 0.45:
            mode = "均值回归"
        else:
            mode = "低波动"

        # 3. 计算每只股票的指标
        scored = []  # (排序值, symbol, name, ret5)
        for stock in self.STOCK_POOL:
            try:
                symbol = stock['symbol']
                name = stock['name']

                # 动量/回归需要lookback_days+1天，低波动需要20天
                need_days = max(self.lookback_days + 1, 25)
                kline = helper.get_history_kline(symbol, days=need_days, end_date=date)
                if kline is None or kline.empty or len(kline) < self.lookback_days + 1:
                    continue

                close = kline['close'].iloc[-1]
                close_5ago = kline['close'].iloc[-(self.lookback_days + 1)]
                if close_5ago <= 0:
                    continue
                ret5 = (close / close_5ago - 1) * 100

                # 低波动模式需要20日波动率
                vol20 = None
                if mode == "低波动":
                    if len(kline) >= 20:
                        vol20 = kline['close'].pct_change().tail(20).std() * 100
                    if vol20 is None or np.isnan(vol20):
                        continue

                if mode == "动量":
                    # 涨幅最大排序（降序）
                    scored.append((ret5, symbol, name, ret5, False))
                elif mode == "均值回归":
                    # 跌幅最大=ret5最小排序（升序）
                    scored.append((ret5, symbol, name, ret5, False))
                else:
                    # 低波动：波动率最小排序（升序），用-vol20作为降序排序值
                    scored.append((-vol20, symbol, name, ret5, True))
            except Exception:
                continue

        # 4. 排序选股
        if mode == "动量":
            # 涨幅最大：降序
            scored.sort(key=lambda x: x[0], reverse=True)
        elif mode == "均值回归":
            # 跌幅最大：升序
            scored.sort(key=lambda x: x[0])
        else:
            # 低波动：波动最小（-vol20最大=vol20最小），降序
            scored.sort(key=lambda x: x[0], reverse=True)

        for sort_val, symbol, name, ret5, is_vol in scored[:self.top_n]:
            results.append({
                'symbol': symbol,
                'name': name,
                'reason': f"Hurst择时:H={H:.2f}({mode}), 近5日{ret5:+.1f}%"
            })

        # 5. 降级处理：若没选出股票，返回标的池前3只
        if not results:
            for stock in self.STOCK_POOL[:self.top_n]:
                try:
                    results.append({
                        'symbol': stock['symbol'],
                        'name': stock['name'],
                        'reason': f"Hurst降级:H={H:.2f}({mode}), 无符合条件标的"
                    })
                except Exception:
                    continue

        return results[:self.top_n]


if __name__ == '__main__':
    s = HurstTimingStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
    # 测试Hurst计算
    np.random.seed(42)
    # 趋势性序列Hurst应>0.5
    trend_prices = 100 * np.cumprod(1 + np.random.normal(0.001, 0.01, 200))
    print(f"趋势序列Hurst: {calc_hurst(trend_prices):.3f}")
    # 随机序列Hurst应接近0.5
    random_prices = 100 * np.cumprod(1 + np.random.normal(0, 0.01, 200))
    print(f"随机序列Hurst: {calc_hurst(random_prices):.3f}")
