# -*- coding: utf-8 -*-
"""
极速历史回测引擎
策略：先用AKShare快速预缓存数据（无速率限制），再用缓存数据回测
"""

import json
import os
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

BENCHMARK_START = datetime(2026, 5, 26)
INITIAL_CAPITAL = 30000
MAX_HOLDINGS = 3
MAX_POOL = 5  # 每策略只用5只股票，减少API调用

# 策略定义：名称 -> (信号类型, 股票池)
STRATEGIES = {
    '集合竞价': {
        'pool': ['600036', '000858', '601318', '600519', '000333'],
        'signal': lambda k: _auction_signal(k),
        'category': '短线技术'
    },
    '尾盘抢筹': {
        'pool': ['600036', '000858', '601318', '600519', '000333'],
        'signal': lambda k: _after_hours_signal(k),
        'category': '短线技术'
    },
    '戴维斯双击': {
        'pool': ['600036', '601318', '600519', '000858', '601166'],
        'signal': lambda k: _davis_signal(k),
        'category': '价值'
    },
    '困境反转': {
        'pool': ['000001', '600016', '601166', '600036', '601328'],
        'signal': lambda k: _turnaround_signal(k),
        'category': '逆向'
    },
    '股东户数变化': {
        'pool': ['600036', '000858', '601318', '600519', '000333'],
        'signal': lambda k: _shareholder_signal(k),
        'category': '事件'
    },
    '涨停封单': {
        'pool': ['600036', '000858', '601318', '600519', '000333'],
        'signal': lambda k: _limit_up_signal(k),
        'category': '短线事件'
    },
    '跌停撬板': {
        'pool': ['000001', '600016', '601166', '600036', '601328'],
        'signal': lambda k: _limit_down_signal(k),
        'category': '短线事件'
    },
    '限售解禁博弈': {
        'pool': ['600036', '000858', '601318', '600519', '000333'],
        'signal': lambda k: _lockup_signal(k),
        'category': '事件'
    },
    '游资席位跟踪': {
        'pool': ['600036', '000858', '601318', '600519', '000333'],
        'signal': lambda k: _hot_money_signal(k),
        'category': '资金面'
    },
    'Hurst择时动量': {
        'pool': ['600036', '601318', '600519', '000858', '601166'],
        'signal': lambda k: _hurst_signal(k),
        'category': '技术面'
    },
    '协整配对交易': {
        'pool': ['600036', '601318', '600519', '000858', '601166'],
        'signal': lambda k: _pairs_signal(k),
        'category': '统计套利'
    },
}


# === 信号函数 ===
def _safe_data(k):
    """安全获取DataFrame和列数据"""
    if not isinstance(k, pd.DataFrame) or k.empty:
        return None, None
    if 'close' not in k.columns:
        return None, None
    try:
        c = k['close'].values
        v = k['volume'].values if 'volume' in k.columns else None
        return c, v
    except:
        return None, None


def _auction_signal(k):
    c, v = _safe_data(k)
    if c is None: return False, ""
    if v is None or len(v) < 5 or len(c) < 10: return False, ""
    if v[-1] > v[-5:].mean() * 1.5:
        ret = (c[-1] / c[-2] - 1) * 100 if len(c) >= 2 else 0
        if 0 < ret < 3: return True, f"竞价放量{v[-1]/v[-5:].mean():.1f}倍"
    return False, ""

def _after_hours_signal(k):
    c, _ = _safe_data(k)
    if c is None or len(c) < 10: return False, ""
    if c[-1] > c[-10:].mean():
        ret5 = (c[-1] / c[-6] - 1) * 100 if len(c) >= 6 else 0
        if ret5 > 2: return True, f"尾盘强势+{ret5:.1f}%"
    return False, ""

def _davis_signal(k):
    c, _ = _safe_data(k)
    if c is None or len(c) < 20: return False, ""
    low = c[-20:].min()
    pct = (c[-1] - low) / (c[-20:].max() - low + 0.001) * 100
    if pct < 30: return True, f"价格低位{int(pct)}%"
    return False, ""

def _turnaround_signal(k):
    c, _ = _safe_data(k)
    if c is None or len(c) < 20: return False, ""
    if c[-1] > c[-20:].mean():
        ret10 = (c[-1] / c[-11] - 1) * 100 if len(c) >= 11 else 0
        if ret10 < -5: return True, f"超跌反弹{ret10:.1f}%"
    return False, ""

def _shareholder_signal(k):
    _, v = _safe_data(k)
    if v is None or len(v) < 20: return False, ""
    if v[-5:].mean() < v[-20:].mean() * 0.8:
        return True, f"量能萎缩{v[-5:].mean()/v[-20:].mean():.1f}倍"
    return False, ""

def _limit_up_signal(k):
    c, _ = _safe_data(k)
    if c is None or len(c) < 2: return False, ""
    ret = (c[-1] / c[-2] - 1) * 100 if len(c) >= 2 else 0
    if ret >= 9.8: return True, f"涨停+{ret:.1f}%"
    return False, ""

def _limit_down_signal(k):
    c, _ = _safe_data(k)
    if c is None or len(c) < 2: return False, ""
    ret = (c[-1] / c[-2] - 1) * 100 if len(c) >= 2 else 0
    if -3 < ret < 0: return True, f"撬板{ret:.1f}%"
    return False, ""

def _lockup_signal(k):
    c, _ = _safe_data(k)
    if c is None or len(c) < 20: return False, ""
    if c[-1] < c[-20:].mean() * 0.9: return True, "解禁超卖"
    return False, ""

def _hot_money_signal(k):
    _, v = _safe_data(k)
    if v is None or len(v) < 5: return False, ""
    if v[-1] > v[-5:].mean() * 2:
        return True, f"游资放量{v[-1]/v[-5:].mean():.1f}倍"
    return False, ""

def _hurst_signal(k):
    c, _ = _safe_data(k)
    if c is None or len(c) < 30: return False, ""
    if c[-1] > c[-10:].mean() > c[-30:].mean():
        ret20 = (c[-1] / c[-21] - 1) * 100 if len(c) >= 21 else 0
        if ret20 > 5: return True, f"Hurst趋势+{ret20:.1f}%"
    return False, ""

def _pairs_signal(k):
    c, _ = _safe_data(k)
    if c is None or len(c) < 20: return False, ""
    if c[-10:].mean() < c[-20:].mean() * 0.95:
        return True, f"配对收敛{((c[-10:].mean()/c[-20:].mean())-1)*100:.1f}%"
    return False, ""


def get_trading_dates(n=40):
    """生成交易日列表"""
    dates = []
    current = BENCHMARK_START
    end = datetime.now()
    while len(dates) < n and current <= end:
        if current.weekday() < 5:
            dates.append(current.strftime('%Y%m%d'))
        current += timedelta(days=1)
    return dates


def run_backtest(strategy_name, config, helper, trading_dates):
    """运行单个策略的回测"""
    pool = config['pool']
    signal_fn = config['signal']

    holdings = []
    trades = []
    equity_curve = []
    capital = INITIAL_CAPITAL
    buy_date_idx = {}

    for i, date in enumerate(trading_dates):
        # 获取当日价格
        prices = {}
        for h in holdings:
            try:
                df = helper.get_history_kline(h['symbol'], days=5, end_date=date)
                if df is not None and not df.empty:
                    prices[h['symbol']] = float(df['close'].iloc[-1])
            except:
                pass

        # 卖出（持有5天）
        for h in list(holdings):
            idx = buy_date_idx.get(h['symbol'], 0)
            if idx <= i - 5:
                sp = prices.get(h['symbol'])
                if sp:
                    pnl = (sp - h['price']) / h['price'] * 100
                    trades.append({
                        'buy_date': h['date'], 'sell_date': date,
                        'symbol': h['symbol'], 'name': h['name'],
                        'buy_price': h['price'], 'sell_price': sp,
                        'profit': pnl, 'reason': h['reason']
                    })
                    capital += h['qty'] * sp
                    holdings.remove(h)
                    buy_date_idx.pop(h['symbol'], None)

        # 选股买入
        if len(holdings) < MAX_HOLDINGS:
            candidates = []
            for sym in pool:
                try:
                    df = helper.get_history_kline(sym, days=30, end_date=date)
                    # 只处理DataFrame，跳过字符串错误返回值
                    if not isinstance(df, pd.DataFrame) or df.empty:
                        continue
                    triggered, reason = signal_fn(df)
                    if triggered:
                        price = prices.get(sym)
                        if price is None and 'close' in df.columns:
                            try:
                                price = float(df['close'].iloc[-1])
                            except:
                                price = None
                        if price and price > 0:
                            available = capital / max(MAX_HOLDINGS - len(holdings), 1)
                            qty = int(available / price / 100) * 100
                            if qty >= 100:
                                candidates.append({
                                    'symbol': sym, 'name': sym, 'price': price,
                                    'qty': qty, 'reason': reason, 'date': date
                                })
                except:
                    pass

            for c in candidates[:MAX_HOLDINGS - len(holdings)]:
                cost = c['qty'] * c['price']
                if cost <= capital * 0.5:
                    trades.append({
                        'buy_date': c['date'], 'symbol': c['symbol'],
                        'name': c['name'], 'buy_price': c['price'],
                        'quantity': c['qty'], 'reason': c['reason'],
                        'buy_date_idx': i
                    })
                    holdings.append(c)
                    buy_date_idx[c['symbol']] = i
                    capital -= cost

        # 权益曲线
        val = capital + sum(
            prices.get(h['symbol'], h['price']) * h['qty'] for h in holdings
        )
        equity_curve.append({'date': date, 'value': val})

    final_val = equity_curve[-1]['value'] if equity_curve else INITIAL_CAPITAL
    ret = (final_val - INITIAL_CAPITAL) / INITIAL_CAPITAL
    wins = [t for t in trades if isinstance(t.get('profit'), (int, float)) and t['profit'] > 0]
    win_rate = len(wins) / len(trades) * 100 if trades else 0

    return {
        'name': strategy_name,
        'category': config['category'],
        'initial_capital': INITIAL_CAPITAL,
        'current_capital': capital,
        'total_value': final_val,
        'total_return': ret,
        'trades': [t for t in trades if 'sell_price' in t],
        'holdings': holdings,
        'equity_curve': equity_curve,
        'win_rate': win_rate,
        'backtest_start': trading_dates[0],
        'backtest_end': trading_dates[-1],
        'backtest_days': len(trading_dates),
    }


def main():
    from data.akshare_helper import AKShareHelper

    print("=" * 60)
    print("极速历史回测 - AKShare数据源（无速率限制）")
    print(f"基准: {BENCHMARK_START.strftime('%Y-%m-%d')}")
    print("=" * 60)

    # 使用AKShare（无速率限制）
    helper = AKShareHelper(cache_dir="data/cache")
    trading_dates = get_trading_dates(40)

    print(f"回测区间: {trading_dates[0]} ~ {trading_dates[-1]}")
    print(f"策略数: {len(STRATEGIES)}")
    print(f"数据源: AKShare（无速率限制）")
    print()

    results = {}
    start = time.time()

    # 并行回测（2个并发）
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {
            ex.submit(run_backtest, name, cfg, helper, trading_dates): name
            for name, cfg in STRATEGIES.items()
        }
        for f in as_completed(futures):
            name = futures[f]
            try:
                r = f.result()
                results[name] = r
                t = r['total_return'] * 100
                n = len(r['trades'])
                wr = r['win_rate']
                print(f"  {name}: {t:+.2f}% | {n}笔交易 | 胜率{wr:.0f}%")
            except Exception as e:
                import traceback
                print(f"  {name}: ERROR - {e}")
                traceback.print_exc()

    elapsed = time.time() - start
    print(f"\n回测完成，耗时 {elapsed:.1f}秒")

    # 保存结果
    output = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'backtest_type': 'historical_fast',
        'backtest_start': trading_dates[0],
        'backtest_end': trading_dates[-1],
        'backtest_days': len(trading_dates),
        'strategy_count': len(results),
        'strategies': list(results.values()),
    }

    os.makedirs('output', exist_ok=True)
    with open('output/new_strategy_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print(f"已保存到 output/new_strategy_results.json")

    # 排名
    print(f"\n收益排名:")
    for name, r in sorted(results.items(), key=lambda x: x[1]['total_return'], reverse=True):
        print(f"  {name}: {r['total_return']*100:+.2f}%")


if __name__ == '__main__':
    main()
