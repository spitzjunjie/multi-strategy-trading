"""
打板连板接力策略

策略逻辑：
- 获取涨停股列表，筛选连板数>=2的龙头股
- 连板接力=情绪周期+资金共识
- 叠加封单量/换手率分析
- 次日开盘价执行（T+1），短线持有2-3天
- 高风险策略，严格止损

参考：online0001/short-term-stock-picker - 短线打板选股
"""

from strategies.base import BaseStrategy


class LimitUpRelayStrategy(BaseStrategy):
    """打板连板接力策略"""

    def __init__(self,
                 min_consecutive=2,   # 最少连板数
                 holding_days=3,      # 短线持有天数
                 stop_loss=-5,        # 止损线%
                 top_n=5):
        super().__init__("打板接力", "短线事件")
        self.min_consecutive = min_consecutive
        self.holding_days = holding_days
        self.stop_loss = stop_loss
        self.top_n = top_n
        # 缓存股票池，避免33天回测每天重复获取
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
        return f"打板接力：连板≥{self.min_consecutive}, 持有{self.holding_days}天, 止损{self.stop_loss}%"

    def select_stocks(self, helper, date=None):
        """选股：连板接力"""
        results = []

        # 1. 获取涨停股列表
        try:
            df = helper.get_limit_up_list(date=date.replace('-', '') if date else None)
        except Exception:
            df = None

        if df is None or df.empty:
            # 备选：用K线筛选近3日涨停的股票
            return self._fallback_select(helper, date)

        # 2. 筛选连板股
        scored = []
        for _, row in df.iterrows():
            try:
                symbol = str(row.get('代码', row.get('股票代码', '')))
                name = str(row.get('名称', row.get('股票简称', symbol)))

                # 连板数
                consecutive = 1
                for col in ['连板数', '连续涨停天数', '连板']:
                    if col in row and row[col]:
                        consecutive = int(row[col])
                        break

                if consecutive < self.min_consecutive:
                    continue

                # 封单金额（万元）
                seal_amount = 0
                for col in ['封板资金', '封单金额', '最新封单']:
                    if col in row and row[col]:
                        seal_amount = float(row[col])
                        break

                # 换手率
                turnover = 0
                for col in ['换手率', '换手率%']:
                    if col in row and row[col]:
                        turnover = float(row[col])
                        break

                # K线确认
                kline = helper.get_history_kline(symbol, days=10, end_date=date)
                if kline.empty or len(kline) < 5:
                    continue

                # 综合得分：连板数+封单量
                score = consecutive * 10 + seal_amount / 10000
                scored.append((symbol, name, score, consecutive, seal_amount))
            except Exception:
                continue

        # 3. 按得分排序
        scored.sort(key=lambda x: x[2], reverse=True)
        for symbol, name, score, consecutive, seal in scored[:self.top_n]:
            results.append({
                'symbol': symbol,
                'name': name,
                'reason': f"打板接力：{consecutive}连板, 封单{seal:.0f}万, 得分{score:.1f}"
            })

        return results[:self.top_n]

    def _fallback_select(self, helper, date=None):
        """备选：用K线筛选涨停股"""
        results = []
        try:
            pool = self._get_pool(helper, date)[:15]
        except Exception:
            pool = ['600519', '600036', '601318', '000858', '600887',
                    '000333', '601166', '600276', '601012', '600030']

        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=10, end_date=date)
                if kline.empty or len(kline) < 5:
                    continue

                # 检测涨停（涨幅>=9.8%）
                today_ret = (kline['close'].iloc[-1] / kline['close'].iloc[-2] - 1) * 100
                if today_ret >= 9.8:
                    # 检查近3日是否有多次涨停（连板）
                    limit_count = 0
                    for i in range(min(3, len(kline) - 1)):
                        ret = (kline['close'].iloc[-1-i] / kline['close'].iloc[-2-i] - 1) * 100
                        if ret >= 9.8:
                            limit_count += 1

                    if limit_count >= self.min_consecutive:
                        try:
                            quote = helper.get_realtime_quote(symbol)
                            name = quote.get('名称', symbol) if quote else symbol
                        except Exception:
                            name = symbol
                        results.append({
                            'symbol': symbol,
                            'name': name,
                            'reason': f"打板接力：{limit_count}连板, 今日涨{today_ret:.1f}%"
                        })
                if len(results) >= self.top_n:
                    break
            except Exception:
                continue
        return results[:self.top_n]


if __name__ == '__main__':
    s = LimitUpRelayStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
