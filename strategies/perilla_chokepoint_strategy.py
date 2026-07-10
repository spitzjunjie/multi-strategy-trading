# -*- coding: utf-8 -*-
"""
AI供应链瓶颈选股策略（紫苏叶策略）

策略逻辑：
- 基于Serenity"瓶颈理论"：寻找产业链中"不可替代 + 供给刚性 + 低认知冷门"的节点
- 标的池覆盖A股AI供应链关键节点：光模块(800G/1.6T/CPO)、半导体材料(衬底/外延)、
  HBM/存储、先进封装、算力/GPU
- 技术面筛选：收盘价突破20日均线 + 成交量放大(当日量/10日均量 > 1.3)
- 基本面降级筛选：尝试获取ROE，ROE>5%加分；获取不到则只用技术面
- 按"涨幅 + 量比"综合排序，取前3

研究来源：海外交易者Serenity瓶颈理论——找产业链不可替代、供给刚性、低认知冷门节点
参考风格：short_term_momentum_strategy.py（硬编码股票池 + K线筛选）

参数：
- lookback_days: K线回看天数（默认20）
- volume_ratio: 量比阈值（默认1.3）
- holding_days: 持有天数（默认15，系统择时引擎读取）
- top_n: 最多选股数（默认3，因系统最多持仓3只）
"""

from strategies.base import BaseStrategy


class PerillaChokepointStrategy(BaseStrategy):
    """AI供应链瓶颈选股策略（紫苏叶策略）"""

    # 硬编码标的池：A股AI供应链关键节点
    CHOKEPOINT_POOL = [
        # 光模块(800G/1.6T/CPO)
        {'symbol': '300308', 'name': '中际旭创', 'niche': '800G光模块龙头'},
        {'symbol': '300502', 'name': '新易盛', 'niche': '光模块二线'},
        {'symbol': '002281', 'name': '光迅科技', 'niche': '光器件+光芯片'},
        {'symbol': '300394', 'name': '天孚通信', 'niche': '光器件配套'},
        {'symbol': '600487', 'name': '亨通光电', 'niche': '光纤光缆+CPO'},
        # 半导体材料(衬底/外延)
        {'symbol': '688126', 'name': '沪硅产业', 'niche': '硅片龙头'},
        {'symbol': '605358', 'name': '立昂微', 'niche': '硅片+化合物'},
        {'symbol': '600206', 'name': '有研新材', 'niche': '靶材+稀土'},
        # HBM/存储
        {'symbol': '301308', 'name': '江波龙', 'niche': '存储模组'},
        {'symbol': '603986', 'name': '兆易创新', 'niche': 'NOR Flash+MCU'},
        {'symbol': '300223', 'name': '北京君正', 'niche': 'DRAM+模拟'},
        # 先进封装
        {'symbol': '600584', 'name': '长电科技', 'niche': '封测龙头'},
        {'symbol': '002156', 'name': '通富微电', 'niche': 'AMD封装'},
        {'symbol': '002185', 'name': '华天科技', 'niche': '封测三线'},
        # 算力/GPU
        {'symbol': '688256', 'name': '寒武纪', 'niche': 'AI芯片'},
        {'symbol': '688041', 'name': '海光信息', 'niche': 'CPU+DCU'},
    ]

    def __init__(self,
                 lookback_days=20,
                 volume_ratio=1.3,
                 holding_days=15,
                 top_n=3):
        super().__init__("AI供应链瓶颈", "产业链选股")
        self.lookback_days = lookback_days
        self.volume_ratio = volume_ratio
        self.holding_days = holding_days
        self.top_n = top_n

    def get_description(self):
        return (f"紫苏叶AI瓶颈：突破{self.lookback_days}日线+量比>{self.volume_ratio}, "
                f"ROE>5%加分, 持有{self.holding_days}天")

    def select_stocks(self, helper, date=None):
        """选股：AI供应链瓶颈节点，技术面突破+量能放大，基本面ROE加分"""
        results = []
        scored = []  # (综合分, symbol, name, niche, vol_ratio, ret5)

        for stock in self.CHOKEPOINT_POOL:
            try:
                symbol = stock['symbol']
                name = stock['name']
                niche = stock['niche']

                kline = helper.get_history_kline(symbol, days=self.lookback_days, end_date=date)
                if kline is None or kline.empty or len(kline) < self.lookback_days:
                    continue

                close = kline['close'].iloc[-1]
                ma = kline['close'].rolling(self.lookback_days).mean().iloc[-1]
                if close <= ma:
                    # 未突破均线，跳过
                    continue

                # 量比：当日量 / 近10日均量
                vol_today = kline['volume'].iloc[-1]
                vol_avg10 = kline['volume'].tail(10).mean()
                if vol_avg10 is None or vol_avg10 <= 0:
                    continue
                vol_ratio = vol_today / vol_avg10
                if vol_ratio < self.volume_ratio:
                    continue

                # 近5日涨幅
                if len(kline) >= 6:
                    ret5 = (kline['close'].iloc[-1] / kline['close'].iloc[-6] - 1) * 100
                else:
                    ret5 = 0.0

                # 基本面ROE加分（降级处理：获取不到则不加不分）
                roe_bonus = 0.0
                try:
                    fin = helper.get_financial_indicator(symbol)
                    if fin:
                        roe = fin.get('roe', 0)
                        # roe是小数，>5%即0.05
                        if isinstance(roe, (int, float)) and roe > 0.05:
                            roe_bonus = roe * 100  # ROE越高加分越多
                except Exception:
                    pass

                # 综合分 = 涨幅 + 量比×5 + ROE加分
                score = ret5 + vol_ratio * 5 + roe_bonus
                scored.append((score, symbol, name, niche, vol_ratio, ret5))
            except Exception:
                continue

        # 按综合分排序
        scored.sort(key=lambda x: x[0], reverse=True)
        for score, symbol, name, niche, vol_ratio, ret5 in scored[:self.top_n]:
            results.append({
                'symbol': symbol,
                'name': name,
                'reason': f"紫苏叶:{niche}, 突破{self.lookback_days}日线, 量能{vol_ratio:.1f}倍, 近5日{ret5:+.1f}%"
            })

        # 降级处理：若没选出股票，返回标的池前3只（按代码顺序）
        if not results:
            for stock in self.CHOKEPOINT_POOL[:self.top_n]:
                try:
                    results.append({
                        'symbol': stock['symbol'],
                        'name': stock['name'],
                        'reason': f"紫苏叶降级:{stock['niche']}(无突破信号)"
                    })
                except Exception:
                    continue

        return results[:self.top_n]


if __name__ == '__main__':
    s = PerillaChokepointStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
    print(f"标的池数: {len(s.CHOKEPOINT_POOL)}")
