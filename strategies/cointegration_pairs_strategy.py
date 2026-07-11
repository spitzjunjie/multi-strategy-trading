# -*- coding: utf-8 -*-
"""
协整配对交易策略

策略逻辑：
- 基于Ernie Chan《Quantitative Trading》配对交易+协整检验方法论
- 标的为同行业龙头对，价差存在长期均衡关系
- 简化版配对（适合A股T+1无融券环境）：
  1. 计算价差 spread = log(price_A) - β×log(price_B)，β简化用1
  2. 计算价差60日均值mean和标准差std
  3. 当前价差z-score = (current_spread - mean) / std
  4. |z-score| > 1.5触发：
     - z < -2：价差过低，买标的A（A相对B低估）
     - z > +2：价差过高，买标的B（B相对A低估）
  5. 每个对最多选1只，总共最多3只
- 注意：此为简化版配对，不真正做空，只买低估端，适合A股T+1无融券环境

研究来源：Ernie Chan《Quantitative Trading》配对交易+协整检验
参考风格：short_term_momentum_strategy.py（硬编码标的池）

参数：
- lookback_days: 协整计算回看天数（默认60）
- z_threshold: z-score触发阈值（默认2.0）
- holding_days: 持有天数（默认20）
- top_n: 最多选股数（默认3）
"""

import math
from strategies.base import BaseStrategy


class CointegrationPairsStrategy(BaseStrategy):
    """协整配对交易策略"""

    # 硬编码同行业龙头对
    PAIRS = [
        ('600519', '贵州茅台', '000858', '五粮液', '白酒'),
        ('600036', '招商银行', '000001', '平安银行', '银行'),
        ('000333', '美的集团', '600690', '海尔智家', '家电'),
        ('600276', '恒瑞医药', '603259', '药明康德', '医药'),
        ('601012', '隆基绿能', '002129', 'TCL中环', '光伏'),
    ]

    def __init__(self,
                 lookback_days=60,
                 z_threshold=1.5,
                 holding_days=20,
                 top_n=3):
        super().__init__("协整配对交易", "统计套利")
        self.lookback_days = lookback_days
        self.z_threshold = z_threshold
        self.holding_days = holding_days
        self.top_n = top_n

    def get_description(self):
        return (f"协整配对：{self.lookback_days}日价差z-score>|{self.z_threshold}|触发, "
                f"买低估端, 持有{self.holding_days}天")

    def _calc_spread_stats(self, prices_a, prices_b):
        """
        计算价差序列的均值和标准差
        spread = log(A) - β×log(B)，β简化为1
        返回: (current_spread, mean, std) 或 None
        """
        n = len(prices_a)
        if n < 20 or n != len(prices_b):
            return None

        spreads = []
        for i in range(n):
            try:
                pa = float(prices_a[i])
                pb = float(prices_b[i])
                if pa <= 0 or pb <= 0:
                    continue
                spreads.append(math.log(pa) - math.log(pb))
            except Exception:
                continue

        if len(spreads) < 20:
            return None

        mean = sum(spreads) / len(spreads)
        var = sum((s - mean) ** 2 for s in spreads) / len(spreads)
        std = math.sqrt(var)
        if std <= 0:
            return None

        current_spread = spreads[-1]
        return (current_spread, mean, std)

    def select_stocks(self, helper, date=None):
        """选股：协整配对，价差偏离2σ时买低估端"""
        results = []

        for pair in self.PAIRS:
            try:
                sym_a, name_a, sym_b, name_b, industry = pair

                # 获取两只股票60日收盘价
                kline_a = helper.get_history_kline(sym_a, days=self.lookback_days, end_date=date)
                kline_b = helper.get_history_kline(sym_b, days=self.lookback_days, end_date=date)

                if kline_a is None or kline_b is None:
                    continue
                if kline_a.empty or kline_b.empty:
                    continue

                # 对齐长度
                n = min(len(kline_a), len(kline_b))
                if n < 20:
                    continue
                prices_a = kline_a['close'].tail(n).values
                prices_b = kline_b['close'].tail(n).values

                stats = self._calc_spread_stats(prices_a, prices_b)
                if stats is None:
                    continue

                current_spread, mean, std = stats
                z_score = (current_spread - mean) / std

                if abs(z_score) < self.z_threshold:
                    # 未达触发阈值，跳过该对
                    continue

                if z_score < -self.z_threshold:
                    # 价差过低：A相对B低估，买A
                    results.append({
                        'symbol': sym_a,
                        'name': name_a,
                        'reason': f"配对:{industry}, z-score={z_score:.2f}, 买{name_a}(价差偏低买A)"
                    })
                elif z_score > self.z_threshold:
                    # 价差过高：B相对A低估，买B
                    results.append({
                        'symbol': sym_b,
                        'name': name_b,
                        'reason': f"配对:{industry}, z-score={z_score:.2f}, 买{name_b}(价差偏高买B)"
                    })

                # 每个对最多选1只（上面逻辑已保证），总共最多top_n只
                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        # 降级处理：若没有触发配对信号，返回第一对的两只股票（按价差偏离大小排序）
        if not results:
            # 尝试返回偏离最大的一对的低估端
            best_z = None
            best_pair = None
            best_side = None
            for pair in self.PAIRS:
                try:
                    sym_a, name_a, sym_b, name_b, industry = pair
                    kline_a = helper.get_history_kline(sym_a, days=self.lookback_days, end_date=date)
                    kline_b = helper.get_history_kline(sym_b, days=self.lookback_days, end_date=date)
                    if kline_a is None or kline_b is None or kline_a.empty or kline_b.empty:
                        continue
                    n = min(len(kline_a), len(kline_b))
                    if n < 20:
                        continue
                    stats = self._calc_spread_stats(
                        kline_a['close'].tail(n).values,
                        kline_b['close'].tail(n).values
                    )
                    if stats is None:
                        continue
                    current_spread, mean, std = stats
                    z = (current_spread - mean) / std
                    if best_z is None or abs(z) > abs(best_z):
                        best_z = z
                        best_pair = pair
                        best_side = 'A' if z < 0 else 'B'
                except Exception:
                    continue

            if best_pair is not None:
                sym_a, name_a, sym_b, name_b, industry = best_pair
                if best_side == 'A':
                    results.append({
                        'symbol': sym_a, 'name': name_a,
                        'reason': f"配对降级:{industry}, z={best_z:.2f}, 买{name_a}(偏离最大端)"
                    })
                else:
                    results.append({
                        'symbol': sym_b, 'name': name_b,
                        'reason': f"配对降级:{industry}, z={best_z:.2f}, 买{name_b}(偏离最大端)"
                    })

            # 仍为空则返回第一个对的两端
            if not results:
                for pair in self.PAIRS[:self.top_n]:
                    try:
                        sym_a, name_a, sym_b, name_b, industry = pair
                        results.append({
                            'symbol': sym_a, 'name': name_a,
                            'reason': f"配对降级:{industry}(无信号,默认A端)"
                        })
                        if len(results) >= self.top_n:
                            break
                    except Exception:
                        continue

        return results[:self.top_n]


if __name__ == '__main__':
    s = CointegrationPairsStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
    print(f"配对数: {len(s.PAIRS)}")
