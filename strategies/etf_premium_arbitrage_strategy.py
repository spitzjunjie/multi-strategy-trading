# -*- coding: utf-8 -*-
"""
ETF折溢价套利策略

策略逻辑：
- 监测ETF场内价格与IOPV（基金净值）的偏离
- 溢价>0.5%时卖出ETF，申购ETF
- 折价>0.5%时买入ETF，赎回ETF
- 低风险，适合震荡市
- 注意：需要ETF实时行情数据
- 适配3只持仓限制

参考：CSDN开源LOF套利tushare实现
"""

from strategies.base import BaseStrategy


class ETFPremiumArbitrageStrategy(BaseStrategy):
    """ETF折溢价套利策略"""

    def __init__(self,
                 premium_threshold=0.5,    # 折溢价阈值%
                 min_trade_amount=1000,     # 最低成交金额（万元）
                 holding_days=5,            # 持有天数
                 top_n=3):
        super().__init__("ETF折溢价套利", "套利策略")
        self.premium_threshold = premium_threshold
        self.min_trade_amount = min_trade_amount
        self.holding_days = holding_days
        self.top_n = top_n
        self._pool_cache = None

    def get_description(self):
        return (f"ETF折溢价套利：偏离>{self.premium_threshold}%, "
                f"成交>{self.min_trade_amount}万, 持有{self.holding_days}天")

    def select_stocks(self, helper, date=None):
        """选股：ETF折溢价套利"""
        results = []

        # 获取主要ETF列表
        etf_list = self._get_etf_list()

        for etf in etf_list:
            try:
                symbol = etf['symbol']
                name = etf['name']

                # 获取ETF价格
                kline = helper.get_history_kline(symbol, days=5, end_date=date)
                if kline is None or kline.empty:
                    continue

                current_price = kline['close'].iloc[-1]
                iopv = etf.get('iopv', current_price)  # 估算IOPV

                # 计算折溢价率
                if iopv > 0:
                    premium = (current_price - iopv) / iopv * 100
                else:
                    premium = 0

                # 筛选条件
                if abs(premium) >= self.premium_threshold:
                    # 估算成交金额
                    vol = kline['volume'].iloc[-1] if len(kline) >= 1 else 0
                    trade_amount = vol * current_price / 10000  # 万元

                    if trade_amount >= self.min_trade_amount:
                        direction = "溢价" if premium > 0 else "折价"
                        results.append({
                            'symbol': symbol,
                            'name': name,
                            'reason': f"ETF套利：{direction}{abs(premium):.2f}%, 成交{trade_amount:.0f}万"
                        })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        # 备选：成交量大的ETF
        if not results:
            return self._volume_fallback(helper, date)

        return results[:self.top_n]

    def _get_etf_list(self):
        """获取主要ETF列表"""
        # 核心宽基ETF
        etfs = [
            {'symbol': '510300', 'name': '沪深300ETF'},
            {'symbol': '510500', 'name': '中证500ETF'},
            {'symbol': '159915', 'name': '创业板ETF'},
            {'symbol': '510050', 'name': '上证50ETF'},
            {'symbol': '512000', 'name': '券商ETF'},
            {'symbol': '512880', 'name': '军工ETF'},
            {'symbol': '512760', 'name': '芯片ETF'},
            {'symbol': '515000', 'name': '科技ETF'},
            {'symbol': '159928', 'name': '消费ETF'},
            {'symbol': '512010', 'name': '医药ETF'},
        ]
        return etfs

    def _volume_fallback(self, helper, date=None):
        """备选：成交量大的ETF"""
        results = []
        etfs = self._get_etf_list()[:5]

        for etf in etfs:
            try:
                kline = helper.get_history_kline(etf['symbol'], days=20, end_date=date)
                if kline is None or kline.empty or len(kline) < 10:
                    continue

                # 近5日平均成交额
                avg_vol = kline['volume'].iloc[-5:].mean()
                avg_price = kline['close'].iloc[-5:].mean()
                trade_amount = avg_vol * avg_price / 10000  # 万元

                # 成交量稳定
                vol_std = kline['volume'].iloc[-5:].std()
                vol_cv = vol_std / avg_vol if avg_vol > 0 else 1

                if trade_amount >= 500 and vol_cv < 0.5:  # 成交稳定
                    # 计算近期折溢价特征
                    ret_5d = (kline['close'].iloc[-1] / kline['close'].iloc[-6] - 1) * 100 if len(kline) >= 6 else 0

                    results.append({
                        'symbol': etf['symbol'],
                        'name': etf['name'],
                        'reason': f"ETF备选：日均成交{trade_amount:.0f}万, 5日涨跌{ret_5d:.1f}%"
                    })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        return results[:self.top_n]


if __name__ == '__main__':
    s = ETFPremiumArbitrageStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
