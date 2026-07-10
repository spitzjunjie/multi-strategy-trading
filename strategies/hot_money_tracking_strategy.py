# -*- coding: utf-8 -*-
"""
游资席位跟踪策略

策略逻辑：
- 获取龙虎榜数据，筛选知名游资席位
- 跟买席位净买入>500万的股票
- 知名游资：光大金田、宁波解放、桑田路等
- 次日开盘执行，持有2-3天
- 高风险，需严格止损

参考：burebaobao/stock-trade-skill - 游资席位跟踪
"""

from strategies.base import BaseStrategy


class HotMoneyTrackingStrategy(BaseStrategy):
    """游资席位跟踪策略"""

    # 知名游资席位列表
    HOT_MONEY_SEATS = [
        '光大金田路', '宁波解放南', '桑田路', '上海超短',
        '华鑫宁波', '成都系', '作手新一', '小鳄鱼',
        '赵老哥', '欢乐海', '浙北基金', '飞云江路',
        '中信上海', '银河绍兴', '华泰荣超', '东财拉萨'
    ]

    def __init__(self,
                 min_net_buy=500,     # 最低净买入（万元）
                 min_seat_count=1,    # 最少游资席位数量
                 holding_days=3,      # 持有天数
                 stop_loss=-7,        # 止损线%
                 top_n=5):
        super().__init__("游资席位跟踪", "资金面")
        self.min_net_buy = min_net_buy
        self.min_seat_count = min_seat_count
        self.holding_days = holding_days
        self.stop_loss = stop_loss
        self.top_n = top_n
        self._pool_cache = None

    def _get_pool(self, helper, date=None):
        """获取股票池（带缓存）"""
        if self._pool_cache is None:
            try:
                self._pool_cache = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:30]
            except Exception:
                self._pool_cache = ['600519', '600036', '601318', '000858', '600887',
                                    '000333', '601166', '600276', '601012', '600030']
        return self._pool_cache

    def get_description(self):
        return (f"游资跟踪：净买入>{self.min_net_buy}万, "
                f"席位≥{self.min_seat_count}, 持有{self.holding_days}天")

    def select_stocks(self, helper, date=None):
        """选股：游资席位净买入"""
        results = []

        # 获取龙虎榜数据
        try:
            lhb_data = helper.get_dragon_tiger_list(date=date.replace('-', '') if date else None)
        except Exception:
            lhb_data = None

        if lhb_data is not None and not lhb_data.empty:
            # 分析龙虎榜中的游资席位
            hot_stocks = {}
            for _, row in lhb_data.iterrows():
                try:
                    symbol = str(row.get('代码', row.get('股票代码', '')))
                    name = str(row.get('名称', row.get('股票简称', symbol)))
                    reason = str(row.get('上榜原因', ''))
                    buy_amount = float(row.get('买入金额', 0) or 0)
                    sell_amount = float(row.get('卖出金额', 0) or 0)
                    net_buy = buy_amount - sell_amount

                    # 检查是否为知名游资席位
                    seat_found = []
                    for seat in self.HOT_MONEY_SEATS:
                        if seat in reason:
                            seat_found.append(seat)

                    if seat_found and net_buy >= self.min_net_buy * 10000:
                        if symbol not in hot_stocks:
                            hot_stocks[symbol] = {
                                'name': name,
                                'net_buy': net_buy,
                                'seats': seat_found,
                                'count': len(seat_found)
                            }
                        else:
                            hot_stocks[symbol]['net_buy'] += net_buy
                            hot_stocks[symbol]['seats'].extend(seat_found)
                            hot_stocks[symbol]['count'] = len(set(hot_stocks[symbol]['seats']))
                except Exception:
                    continue

            # 按净买入排序
            scored = [(k, v['name'], v['net_buy'], v['seats'], v['count'])
                      for k, v in hot_stocks.items()]
            scored.sort(key=lambda x: x[2], reverse=True)

            for symbol, name, net_buy, seats, count in scored[:self.top_n]:
                results.append({
                    'symbol': symbol,
                    'name': name,
                    'reason': f"游资跟踪：净买入{net_buy/10000:.0f}万, {count}个席位{seats[0]}等"
                })
        else:
            # 备选：用K线筛选游资偏好股（高价股、热门股）
            return self._kline_fallback(helper, date)

        return results[:self.top_n]

    def _kline_fallback(self, helper, date=None):
        """K线筛选游资偏好股"""
        results = []
        pool = self._get_pool(helper, date)

        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=15, end_date=date)
                if kline is None or kline.empty or len(kline) < 10:
                    continue

                # 游资偏好特征：换手率高、振幅大
                turnover_rate = (kline['volume'].iloc[-1] / kline['volume'].iloc[-20:].mean()) if len(kline) >= 20 else 2.0
                amplitude = (kline['high'].iloc[-1] - kline['low'].iloc[-1]) / kline['low'].iloc[-1] * 100
                gain = (kline['close'].iloc[-1] / kline['close'].iloc[-2] - 1) * 100

                # 筛选条件：换手高、振幅大、涨幅适中
                if turnover_rate > 1.5 and amplitude > 3 and 2 < gain < 9:
                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'reason': f"游资偏好：换手{turnover_rate:.1f}倍, 振幅{amplitude:.1f}%, 涨幅{gain:.1f}%"
                    })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        return results[:self.top_n]


if __name__ == '__main__':
    s = HotMoneyTrackingStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
    print(f"游资席位: {s.HOT_MONEY_SEATS[:5]}...")
