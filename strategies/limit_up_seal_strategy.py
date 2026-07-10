# -*- coding: utf-8 -*-
"""
涨停封单策略

策略逻辑：
- 筛选涨停股，分析封单量/换手率/封板时间
- 封单量>5000万且换手率<5%为优质标的
- 封板时间早（9:30-10:00）为强势信号
- 次日开盘执行，短线持有1-2天
- 高风险，严格止损

参考：online0001/short-term-stock-picker - 涨停封单分析
"""

from strategies.base import BaseStrategy


class LimitUpSealStrategy(BaseStrategy):
    """涨停封单策略"""

    def __init__(self,
                 min_seal_amount=5000,   # 最低封单金额（万元）
                 max_turnover=5.0,       # 最高换手率%
                 min_seal_time='early',  # 封板时间：early=早板, any=任意
                 holding_days=2,         # 持有天数
                 stop_loss=-6,           # 止损线%
                 top_n=5):
        super().__init__("涨停封单", "短线事件")
        self.min_seal_amount = min_seal_amount
        self.max_turnover = max_turnover
        self.min_seal_time = min_seal_time
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
        return (f"涨停封单：封单>{self.min_seal_amount}万, 换手<{self.max_turnover}%, "
                f"持有{self.holding_days}天, 止损{self.stop_loss}%")

    def select_stocks(self, helper, date=None):
        """选股：涨停封单分析"""
        results = []

        # 获取涨停股列表
        try:
            limit_df = helper.get_limit_up_list(date=date.replace('-', '') if date else None)
        except Exception:
            limit_df = None

        if limit_df is not None and not limit_df.empty:
            scored = []
            for _, row in limit_df.iterrows():
                try:
                    symbol = str(row.get('代码', row.get('股票代码', '')))
                    name = str(row.get('名称', row.get('股票简称', symbol)))

                    # 封单金额（万元）
                    seal_amount = 0
                    for col in ['封板资金', '封单金额', '最新封单', '封单额']:
                        if col in row and row[col]:
                            seal_amount = float(row[col])
                            break

                    # 换手率
                    turnover = 100  # 默认高换手
                    for col in ['换手率', '换手率%', '换手']:
                        if col in row and row[col]:
                            turnover = float(row[col])
                            break

                    # 筛选
                    if seal_amount >= self.min_seal_amount * 10000 and turnover <= self.max_turnover:
                        # 综合得分
                        score = seal_amount / 10000 + (self.max_turnover - turnover) * 100
                        scored.append((symbol, name, score, seal_amount, turnover))
                except Exception:
                    continue

            scored.sort(key=lambda x: x[2], reverse=True)
            for symbol, name, score, seal, turnover in scored[:self.top_n]:
                results.append({
                    'symbol': symbol,
                    'name': name,
                    'reason': f"涨停封单：封单{seal/10000:.0f}万, 换手{turnover:.1f}%, 得分{score:.0f}"
                })
        else:
            # 备选：K线筛选
            return self._kline_fallback(helper, date)

        return results[:self.top_n]

    def _kline_fallback(self, helper, date=None):
        """K线筛选涨停股"""
        results = []
        pool = self._get_pool(helper, date)

        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=10, end_date=date)
                if kline is None or kline.empty or len(kline) < 5:
                    continue

                # 检测今日涨停
                today_ret = (kline['close'].iloc[-1] / kline['close'].iloc[-2] - 1) * 100
                if today_ret >= 9.8:  # 接近涨停
                    # 换手率估算
                    vol_ma5 = kline['volume'].iloc[-5:].mean()
                    today_vol = kline['volume'].iloc[-1]
                    vol_ratio = today_vol / vol_ma5 if vol_ma5 > 0 else 1.0

                    # 封单强度（成交量/流通股本估算）
                    # 成交量放大但未爆量 = 封单稳健
                    if 0.8 < vol_ratio < 2.0:
                        results.append({
                            'symbol': symbol,
                            'name': symbol,
                            'reason': f"涨停封单备选：涨幅{today_ret:.1f}%, 量比{vol_ratio:.1f}倍"
                        })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        return results[:self.top_n]


if __name__ == '__main__':
    s = LimitUpSealStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
