"""
龙虎榜跟风策略

策略逻辑：
- 获取龙虎榜数据，筛选机构/游资净买入的股票
- 买入金额排名前列=资金关注度高
- 叠加K线趋势确认（次日开盘价执行，T+1）
- 适用于短线事件驱动

参考：burebaobao/stock-trade-skill - 龙虎榜/游资席位跟踪
"""

from strategies.base import BaseStrategy


class DragonTigerFollowStrategy(BaseStrategy):
    """龙虎榜跟风策略"""

    def __init__(self,
                 min_net_buy=500,    # 净买入下限（万元）
                 holding_days=5,     # 短线持有天数
                 top_n=5):
        super().__init__("龙虎榜跟风", "资金面")
        self.min_net_buy = min_net_buy
        self.holding_days = holding_days
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
        return f"龙虎榜跟风：净买入>{self.min_net_buy}万, 持有{self.holding_days}天"

    def select_stocks(self, helper, date=None):
        """选股：龙虎榜资金跟风"""
        results = []

        # 1. 获取龙虎榜数据
        try:
            df = helper.get_dragon_tiger_list(date=date.replace('-', '') if date else None)
        except Exception:
            df = None

        if df is None or df.empty:
            # 备选：用沪深300+K线异动筛选
            return self._akshare_fallback(helper, date)

        # 2. 解析龙虎榜数据，按净买入排序
        scored = []
        for _, row in df.iterrows():
            try:
                # 尝试多种列名
                symbol = str(row.get('代码', row.get('股票代码', '')))
                name = str(row.get('名称', row.get('股票简称', symbol)))

                # 净买入额（万元）
                net_buy = 0
                for col in ['净买入额', '买入额', '龙虎榜净买入额']:
                    if col in row and row[col]:
                        net_buy = float(row[col])
                        break

                if not symbol or len(symbol) != 6 or net_buy < self.min_net_buy:
                    continue

                # K线趋势确认
                kline = helper.get_history_kline(symbol, days=10, end_date=date)
                if kline.empty or len(kline) < 5:
                    continue
                # 不追高：当日涨幅<5%
                if len(kline) >= 2:
                    today_ret = (kline['close'].iloc[-1] / kline['close'].iloc[-2] - 1) * 100
                    if today_ret > 5:
                        continue

                scored.append((symbol, name, net_buy))
            except Exception:
                continue

        # 3. 按净买入排序
        scored.sort(key=lambda x: x[2], reverse=True)
        for symbol, name, net_buy in scored[:self.top_n]:
            results.append({
                'symbol': symbol,
                'name': name,
                'reason': f"龙虎榜跟风：净买入{net_buy:.0f}万元"
            })

        return results[:self.top_n]

    def _akshare_fallback(self, helper, date=None):
        """AKShare龙虎榜数据源备选"""
        results = []
        try:
            # 尝试用AKShare获取龙虎榜
            df = helper.get_dragon_tiger_list(date=date.replace('-', '') if date else None)
            if df is not None and not df.empty:
                scored = []
                for _, row in df.iterrows():
                    try:
                        symbol = str(row.get('代码', row.get('股票代码', '')))
                        name = str(row.get('名称', row.get('股票简称', symbol)))
                        if not symbol or len(symbol) != 6:
                            continue
                        # 净买入额（万元）
                        net_buy = float(row.get('净买入额', row.get('龙虎榜净买入额', 0)) or 0)
                        if net_buy < self.min_net_buy:
                            continue
                        scored.append((symbol, name, net_buy))
                    except Exception:
                        continue
                scored.sort(key=lambda x: x[2], reverse=True)
                for symbol, name, net_buy in scored[:self.top_n]:
                    results.append({
                        'symbol': symbol,
                        'name': name,
                        'reason': f"龙虎榜跟风(AKShare)：净买入{name}万"
                    })
                if results:
                    return results
        except Exception:
            pass

        # 最终备选：用成交量异动筛选
        try:
            pool = self._get_pool(helper, date)[:20]
        except Exception:
            pool = ['600519', '600036', '601318', '000858', '600887',
                    '000333', '601166', '600276', '601012', '600030']

        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=20, end_date=date)
                if kline.empty or len(kline) < 10:
                    continue
                vol_today = kline['volume'].iloc[-1]
                vol_ma5 = kline['volume'].iloc[-5:].mean()
                if vol_today > vol_ma5 * 1.5:
                    today_ret = (kline['close'].iloc[-1] / kline['close'].iloc[-2] - 1) * 100
                    if today_ret > 0 and today_ret < 5:
                        try:
                            quote = helper.get_realtime_quote(symbol)
                            name = quote.get('名称', symbol) if quote else symbol
                        except Exception:
                            name = symbol
                        results.append({
                            'symbol': symbol,
                            'name': name,
                            'reason': f"放量异动(AKShare备选)：量比{vol_today/vol_ma5:.1f}, 涨{today_ret:.1f}%"
                        })
                if len(results) >= self.top_n:
                    break
            except Exception:
                continue
        return results[:self.top_n]


if __name__ == '__main__':
    s = DragonTigerFollowStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
