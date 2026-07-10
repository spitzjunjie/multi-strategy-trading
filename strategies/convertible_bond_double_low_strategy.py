# -*- coding: utf-8 -*-
"""
可转债双低策略

策略逻辑：
- 筛选价格<130元且溢价率<20%的双低可转债
- 价格低=债底保护，溢价率低=股性强
- 轮动持有，每20天检视一次
- 低风险，适合震荡市
- 适配3只持仓限制

参考：jackluson/convertible-bond-crawler - 可转债双低策略
"""

from strategies.base import BaseStrategy


class ConvertibleBondDoubleLowStrategy(BaseStrategy):
    """可转债双低策略"""

    def __init__(self,
                 max_price=130,        # 最高价格（元）
                 max_premium=20,       # 最高溢价率%
                 min_price=100,       # 最低价格（元）
                 rebalance_days=20,   # 再平衡周期
                 top_n=3):           # 持仓数量
        super().__init__("可转债双低", "套利策略")
        self.max_price = max_price
        self.max_premium = max_premium
        self.min_price = min_price
        self.rebalance_days = rebalance_days
        self.top_n = top_n
        # 缓存
        self._pool_cache = None
        self._last_rebalance_date = None

    def get_description(self):
        return (f"可转债双低：价格{self.min_price}-{self.max_price}元, "
                f"溢价率<{self.max_premium}%, 每{self.rebalance_days}天轮动")

    def select_stocks(self, helper, date=None):
        """选股：可转债双低"""
        results = []

        # 获取可转债列表
        try:
            cb_list = self._get_convertible_bonds(helper, date)
        except Exception:
            cb_list = []

        if not cb_list:
            # 备选：返回主要可转债正股
            return self._stock_fallback(helper, date)

        # 按双低得分排序
        scored = []
        for cb in cb_list:
            try:
                price = cb.get('price', 130)
                premium = cb.get('premium', 30)

                # 双低得分 = 价格分 + 溢价分
                # 价格越低越好，溢价越低越好
                price_score = (self.max_price - price) / (self.max_price - self.min_price) * 50
                premium_score = (self.max_premium - premium) / self.max_premium * 50
                total_score = price_score + premium_score

                scored.append((cb['symbol'], cb['name'], total_score, price, premium))
            except Exception:
                continue

        scored.sort(key=lambda x: x[2], reverse=True)

        for symbol, name, score, price, premium in scored[:self.top_n]:
            results.append({
                'symbol': symbol,
                'name': name,
                'reason': f"可转债双低：价格{price:.1f}元, 溢价{premium:.1f}%, 得分{score:.1f}"
            })

        return results[:self.top_n]

    def _get_convertible_bonds(self, helper, date=None):
        """获取可转债列表"""
        try:
            # 尝试通过AKShare获取可转债数据
            import akshare as ak
            cb_df = ak.bond_zh_cov()
            if cb_df is not None and not cb_df.empty:
                result = []
                for _, row in cb_df.iterrows():
                    try:
                        symbol = str(row.get('债券代码', ''))
                        name = str(row.get('债券名称', ''))
                        price = float(row.get('最新价', 130) or 130)
                        premium = float(row.get('溢价率', 30) or 30)

                        if self.min_price <= price <= self.max_price and premium <= self.max_premium:
                            # 获取正股代码
                            stock_code = symbol.replace('sh', '').replace('sz', '').replace('bj', '')
                            if len(stock_code) == 6:
                                result.append({
                                    'symbol': stock_code,
                                    'name': name,
                                    'price': price,
                                    'premium': premium
                                })
                    except Exception:
                        continue
                return result
        except Exception:
            pass
        return []

    def _stock_fallback(self, helper, date=None):
        """备选：返回低PB大盘股作为替代"""
        results = []
        try:
            pool = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:20]
        except Exception:
            pool = ['600519', '600036', '601318', '000858', '600887',
                    '000333', '601166', '600276', '601012', '600030']

        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=30, end_date=date)
                if kline is None or kline.empty:
                    continue

                # 低价格特征（当前价位在历史低位）
                price_ma20 = kline['close'].iloc[-20:].mean() if len(kline) >= 20 else kline['close'].mean()
                current_price = kline['close'].iloc[-1]

                if current_price < price_ma20 * 1.1:  # 在20日均线附近或下方
                    val = helper.get_valuation_data(symbol)
                    pb = val.get('pb', 10) if val else 10

                    if pb < 3:  # 低PB
                        results.append({
                            'symbol': symbol,
                            'name': symbol,
                            'reason': f"可转债备选(低PB)：PB={pb:.1f}, 价低于均线"
                        })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        return results[:self.top_n]


if __name__ == '__main__':
    s = ConvertibleBondDoubleLowStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
