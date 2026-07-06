# -*- coding: utf-8 -*-
"""
AKShare数据封装模块
提供A股行情、财务数据、估值数据、资金流、事件数据等
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import time

class AKShareHelper:
    """AKShare数据助手"""

    def __init__(self, cache_dir="data/cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._hs300_cache = None

    def _get_cache(self, key, days=1):
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(cache_file):
            file_time = os.path.getmtime(cache_file)
            if (datetime.now().timestamp() - file_time) < days * 86400:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        return None

    def _set_cache(self, key, data):
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    # ==================== 基础行情 ====================

    def get_stock_list(self):
        """获取A股股票列表"""
        cache = self._get_cache("stock_list", days=7)
        if cache:
            return cache
        try:
            df = ak.stock_info_a_code_name()
            stocks = df.to_dict('records')
            self._set_cache("stock_list", stocks)
            return stocks
        except Exception as e:
            print(f"获取股票列表失败: {e}")
            return []

    def get_realtime_quote(self, symbol):
        """获取实时行情"""
        try:
            df = ak.stock_zh_a_spot_em()
            stock = df[df['代码'] == symbol]
            if not stock.empty:
                return stock.iloc[0].to_dict()
        except Exception as e:
            print(f"获取实时行情失败 {symbol}: {e}")
        return None

    def get_history_kline(self, symbol, period="daily", days=60, end_date=None):
        """获取历史K线（前复权）
        symbol: 6位股票代码，如 '000001' / '600000'
        end_date: 指定结束日期(YYYYMMDD字符串或YYYY-MM-DD)，None=今天
        优先用新浪源 stock_zh_a_daily（稳定），降级用东方财富 stock_zh_a_hist
        """
        # 统一end_date格式为YYYYMMDD
        if end_date and isinstance(end_date, str) and '-' in end_date:
            end_date = end_date.replace('-', '')
        cache_key = f"kline_{symbol}_{period}_{days}_{end_date or 'now'}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return pd.DataFrame(cache)
        actual_end = end_date or datetime.now().strftime("%Y%m%d")
        actual_start = (datetime.strptime(actual_end, "%Y%m%d") - timedelta(days=days*2)).strftime("%Y%m%d")

        # 方案1: 新浪源 stock_zh_a_daily（稳定，需要sz/sh前缀）
        try:
            # 转换symbol为新浪格式：6开头=sh，其余=sz
            prefix = 'sh' if symbol.startswith('6') else 'sz'
            sina_symbol = f"{prefix}{symbol}"
            df = ak.stock_zh_a_daily(symbol=sina_symbol, start_date=actual_start,
                                      end_date=actual_end, adjust="qfq")
            if df is not None and not df.empty:
                df = df.tail(days)
                # stock_zh_a_daily返回英文列名：date, open, high, low, close, volume, amount, outstanding_share, turnover
                # 已经是统一格式，只需保留需要的列
                keep_cols = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount']
                df = df[[c for c in keep_cols if c in df.columns]]
                df['date'] = df['date'].astype(str)
                self._set_cache(cache_key, df.to_dict('records'))
                return df
        except Exception as e:
            print(f"新浪源K线失败 {symbol}: {e}")

        # 方案2: 东方财富源 stock_zh_a_hist（降级）
        try:
            df = ak.stock_zh_a_hist(symbol=symbol, period=period,
                                    start_date=actual_start, end_date=actual_end, adjust="qfq")
            if df is not None and not df.empty:
                df = df.tail(days)
                col_map = {
                    '日期': 'date', '开盘': 'open', '收盘': 'close',
                    '最高': 'high', '最低': 'low', '成交量': 'volume',
                    '成交额': 'amount', '振幅': 'amplitude'
                }
                df = df.rename(columns=col_map)
                self._set_cache(cache_key, df.to_dict('records'))
                return df
        except Exception as e:
            print(f"东方财富源K线失败 {symbol}: {e}")
        return pd.DataFrame()

    def get_trading_dates(self, n=60, end_date=None):
        """获取过去n个交易日列表
        优先用新浪交易日历（稳定），降级用沪深300指数K线
        返回: ['2026-06-01', '2026-06-02', ...] YYYY-MM-DD格式
        """
        # 确定截止日期：默认今天
        if end_date:
            end_norm = end_date.replace('-', '') if '-' in end_date else end_date
        else:
            end_norm = datetime.now().strftime("%Y%m%d")

        # 优先方案：新浪交易日历
        try:
            cache_key = f"trade_dates_sina"
            cache = self._get_cache(cache_key, days=1)
            if cache:
                all_dates = cache
            else:
                df = ak.tool_trade_date_hist_sina()
                all_dates = df['trade_date'].astype(str).tolist()
                self._set_cache(cache_key, all_dates)
            # 过滤 <= end_norm（排除未来日期），取最后n个
            all_dates = [d for d in all_dates if d.replace('-', '') <= end_norm]
            dates = all_dates[-n:] if len(all_dates) >= n else all_dates
            # 统一为YYYY-MM-DD格式
            return [d if '-' in d else f"{d[:4]}-{d[4:6]}-{d[6:8]}" for d in dates]
        except Exception as e:
            print(f"新浪交易日历获取失败: {e}，降级用沪深300指数K线")

        # 降级方案：用沪深300指数K线（stock_zh_index_daily）
        try:
            df = ak.stock_zh_index_daily(symbol='sh000300')
            if df is not None and not df.empty:
                df['date'] = df['date'].astype(str)
                df = df[df['date'].str.replace('-', '') <= end_norm]
                dates = df['date'].tolist()[-n:]
                return dates
        except Exception as e:
            print(f"沪深300指数K线失败: {e}")
        return []

    def get_stock_pool(self, pool="hs300", sorted_by_market_value=False):
        """获取股票池（默认沪深300）

        Args:
            pool: 指数池 hs300/zz500/sz50
            sorted_by_market_value: True=按市值降序（用实时行情spot_em补充市值）
        """
        cache_key = f"pool_{pool}_mv{int(sorted_by_market_value)}"
        cache = self._get_cache(cache_key, days=7)
        if cache:
            return cache
        try:
            if pool == "hs300":
                df = ak.index_stock_cons_csindex(symbol="000300")
            elif pool == "zz500":
                df = ak.index_stock_cons_csindex(symbol="000905")
            elif pool == "sz50":
                df = ak.index_stock_cons_csindex(symbol="000016")
            else:
                df = ak.index_stock_cons_csindex(symbol="000300")

            if df is not None and not df.empty:
                # 统一成分股代码格式
                if '成分券代码' in df.columns:
                    stocks = df['成分券代码'].tolist()
                elif '代码' in df.columns:
                    stocks = df['代码'].tolist()
                else:
                    stocks = df.iloc[:, 0].tolist()

                # 按市值降序排序（抽样时取大盘股而非代码最小的）
                if sorted_by_market_value and stocks:
                    try:
                        spot = ak.stock_zh_a_spot_em()
                        spot = spot[spot['代码'].isin(stocks)]
                        if '总市值' in spot.columns:
                            spot = spot.sort_values('总市值', ascending=False)
                            stocks = spot['代码'].tolist()
                    except Exception as e:
                        print(f"按市值排序失败，降级用原顺序: {e}")

                self._set_cache(cache_key, stocks)
                return stocks
        except Exception as e:
            print(f"获取股票池失败: {e}")
        # 降级：返回常见大盘股
        return ['600519', '000858', '600036', '601318', '000333',
                '600276', '300750', '601012', '600900', '000651']

    # ==================== 财务指标 ====================

    def get_financial_indicator(self, symbol):
        """获取财务指标：ROE、ROIC、资产负债率、现金流等"""
        cache_key = f"fin_ind_{symbol}"
        cache = self._get_cache(cache_key, days=30)
        if cache:
            return cache
        try:
            df = ak.stock_financial_analysis_indicator(symbol=symbol)
            if df is not None and not df.empty:
                latest = df.iloc[0].to_dict()
                data = {
                    'roe': self._safe_float(latest.get('净资产收益率(%)', 0)),
                    'roic': self._safe_float(latest.get('投入资本回报率(%)', 0)),
                    'debt_ratio': self._safe_float(latest.get('资产负债率(%)', 0)),
                    'current_ratio': self._safe_float(latest.get('流动比率', 0)),
                    'gross_margin': self._safe_float(latest.get('销售毛利率(%)', 0)),
                    'net_margin': self._safe_float(latest.get('销售净利率(%)', 0)),
                }
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"获取财务指标失败 {symbol}: {e}")
        return {}

    def get_valuation_data(self, symbol):
        """获取估值数据：PE、PB、PS、股息率"""
        cache_key = f"val_{symbol}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return cache
        try:
            # 使用实时行情获取估值
            df = ak.stock_a_indicator_lg(symbol=symbol)
            if df is not None and not df.empty:
                latest = df.iloc[-1].to_dict()
                data = {
                    'pe': self._safe_float(latest.get('pe', 0)),
                    'pe_ttm': self._safe_float(latest.get('pe_ttm', 0)),
                    'pb': self._safe_float(latest.get('pb', 0)),
                    'ps': self._safe_float(latest.get('ps', 0)),
                    'ps_ttm': self._safe_float(latest.get('ps_ttm', 0)),
                    'dv_ratio': self._safe_float(latest.get('dv_ratio', 0)),
                    'dv_ttm': self._safe_float(latest.get('dv_ttm', 0)),
                    'total_mv': self._safe_float(latest.get('total_mv', 0)),
                }
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"获取估值数据失败 {symbol}: {e}")
        return {}

    def get_growth_data(self, symbol):
        """获取成长数据：净利润增速、营收增速"""
        cache_key = f"growth_{symbol}"
        cache = self._get_cache(cache_key, days=30)
        if cache:
            return cache
        try:
            df = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按报告期")
            if df is not None and not df.empty:
                latest = df.iloc[0].to_dict()
                data = {
                    'profit_growth': self._safe_float(latest.get('净利润同比增长率', 0)),
                    'revenue_growth': self._safe_float(latest.get('营业收入同比增长率', 0)),
                    'profit_yoy': self._safe_float(latest.get('归属净利润同比增长率', 0)),
                }
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"获取成长数据失败 {symbol}: {e}")
        return {}

    def get_cash_flow(self, symbol):
        """获取现金流数据"""
        cache_key = f"cashflow_{symbol}"
        cache = self._get_cache(cache_key, days=30)
        if cache:
            return cache
        try:
            df = ak.stock_cash_flow_sheet_by_report_em(symbol=symbol)
            if df is not None and not df.empty:
                latest = df.iloc[0].to_dict()
                data = {
                    'operating_cf': self._safe_float(latest.get('经营活动产生的现金流量净额', 0)),
                    'net_profit': self._safe_float(latest.get('净利润', 0)),
                }
                # 现金流质量 = 经营现金流 / 净利润
                if data['net_profit'] and data['net_profit'] != 0:
                    data['cf_quality'] = data['operating_cf'] / data['net_profit']
                else:
                    data['cf_quality'] = 0
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"获取现金流失败 {symbol}: {e}")
        return {}

    # ==================== 资金流数据 ====================

    def get_north_holding(self, symbol):
        """获取个股北向资金持股比例"""
        cache_key = f"north_{symbol}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return cache
        try:
            df = ak.stock_hsgt_individual_em(symbol=symbol)
            if df is not None and not df.empty:
                latest = df.iloc[-1].to_dict()
                data = {
                    'hold_ratio': self._safe_float(latest.get('持股数量比例', 0)),
                    'hold_market_value': self._safe_float(latest.get('持股市值', 0)),
                }
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"获取北向持股失败 {symbol}: {e}")
        return {}

    def get_north_flow(self):
        """获取北向资金整体流向"""
        cache = self._get_cache("north_flow", days=1)
        if cache:
            return pd.DataFrame(cache)
        try:
            df = ak.stock_hsgt_hist_em(symbol="北向资金")
            if df is not None and not df.empty:
                df = df.tail(30)
                self._set_cache("north_flow", df.to_dict('records'))
                return df
        except Exception as e:
            print(f"获取北向资金失败: {e}")
        return pd.DataFrame()

    # ==================== 事件数据 ====================

    def get_limit_up_list(self, date=None):
        """获取涨停板股票列表"""
        if date is None:
            date = datetime.now().strftime("%Y%m%d")
        cache_key = f"limitup_{date}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return pd.DataFrame(cache)
        try:
            df = ak.stock_zt_pool_em(date=date)
            if df is not None and not df.empty:
                self._set_cache(cache_key, df.to_dict('records'))
                return df
        except Exception as e:
            print(f"获取涨停板失败: {e}")
        return pd.DataFrame()

    def get_dragon_tiger_list(self, date=None):
        """获取龙虎榜数据"""
        if date is None:
            date = datetime.now().strftime("%Y%m%d")
        cache_key = f"lhb_{date}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return pd.DataFrame(cache)
        try:
            df = ak.stock_lhb_detail_em(start_date=date, end_date=date)
            if df is not None and not df.empty:
                self._set_cache(cache_key, df.to_dict('records'))
                return df
        except Exception as e:
            print(f"获取龙虎榜失败: {e}")
        return pd.DataFrame()

    def get_executive_trading(self):
        """获取高管增减持数据"""
        cache = self._get_cache("exec_trade", days=1)
        if cache:
            return pd.DataFrame(cache)
        try:
            df = ak.stock_ggcg_em()
            if df is not None and not df.empty:
                df = df.head(100)  # 最近100条
                self._set_cache("exec_trade", df.to_dict('records'))
                return df
        except Exception as e:
            print(f"获取高管增减持失败: {e}")
        return pd.DataFrame()

    def get_analyst_rating(self, symbol):
        """获取分析师评级"""
        cache_key = f"rating_{symbol}"
        cache = self._get_cache(cache_key, days=7)
        if cache:
            return cache
        try:
            df = ak.stock_research_report_em(symbol=symbol)
            if df is not None and not df.empty:
                latest = df.iloc[0].to_dict()
                data = {
                    'rating': latest.get('评级', ''),
                    'target_price': self._safe_float(latest.get('目标价', 0)),
                    'institution': latest.get('机构', ''),
                }
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"获取分析师评级失败 {symbol}: {e}")
        return {}

    # ==================== 指数数据 ====================

    def get_index_data(self, symbol="000300", days=60):
        """获取指数历史数据"""
        cache_key = f"idx_{symbol}_{days}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return pd.DataFrame(cache)
        try:
            df = ak.stock_zh_index_daily(symbol=f"sh{symbol}" if symbol.startswith('000') else f"sz{symbol}")
            if df is not None and not df.empty:
                df = df.tail(days)
                self._set_cache(cache_key, df.to_dict('records'))
                return df
        except Exception as e:
            print(f"获取指数数据失败: {e}")
        return pd.DataFrame()

    # ==================== 批量数据 ====================

    def get_hs300_valuation_batch(self):
        """批量获取沪深300估值数据（用于因子选股）"""
        cache = self._get_cache("hs300_val_batch", days=1)
        if cache:
            return pd.DataFrame(cache)
        try:
            # 使用东财实时行情获取全部A股估值
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                # 筛选沪深300
                hs300 = self.get_stock_pool("hs300")
                df = df[df['代码'].isin(hs300)]
                # 重命名列
                df = df.rename(columns={
                    '代码': 'symbol', '名称': 'name',
                    '最新价': 'close', '涨跌幅': 'pct_change',
                    '市盈率-动态': 'pe', '市净率': 'pb',
                    '总市值': 'total_mv', '流通市值': 'circ_mv',
                    '换手率': 'turnover', '量比': 'volume_ratio'
                })
                self._set_cache("hs300_val_batch", df.to_dict('records'))
                return df
        except Exception as e:
            print(f"批量获取估值失败: {e}")
        return pd.DataFrame()

    # ==================== 工具方法 ====================

    def _safe_float(self, value, default=0.0):
        """安全转换为浮点数"""
        if value is None or value == '' or value == '--':
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def get_market_baojun(self):
        """获取大盘指数行情"""
        cache = self._get_cache("market", days=1)
        if cache:
            return pd.DataFrame(cache)
        try:
            result = []
            for sym, name in [('000001', '上证指数'), ('399001', '深证成指'), ('399006', '创业板指')]:
                try:
                    df = ak.stock_zh_index_daily(symbol=f"sh{sym}" if sym.startswith('000') else f"sz{sym}")
                    if df is not None and not df.empty:
                        latest = df.iloc[-1]
                        result.append({
                            'symbol': sym, 'name': name,
                            'close': latest.get('close', 0),
                            'open': latest.get('open', 0),
                            'high': latest.get('high', 0),
                            'low': latest.get('low', 0),
                            'volume': latest.get('volume', 0),
                        })
                except:
                    continue
            if result:
                self._set_cache("market", result)
                return pd.DataFrame(result)
        except Exception as e:
            print(f"获取大盘指数失败: {e}")
        return pd.DataFrame()


if __name__ == "__main__":
    helper = AKShareHelper()
    # 测试数据获取
    print("=== 测试数据层 ===")
    stocks = helper.get_stock_pool("hs300")
    print(f"沪深300成分股: {len(stocks)}只")

    if stocks:
        symbol = stocks[0]
        print(f"\n测试股票: {symbol}")

        kline = helper.get_history_kline(symbol, days=30)
        print(f"K线数据: {len(kline)}条")

        val = helper.get_valuation_data(symbol)
        print(f"估值数据: PE={val.get('pe')}, PB={val.get('pb')}")

        fin = helper.get_financial_indicator(symbol)
        print(f"财务指标: ROE={fin.get('roe')}")

        growth = helper.get_growth_data(symbol)
        print(f"成长数据: {growth}")
