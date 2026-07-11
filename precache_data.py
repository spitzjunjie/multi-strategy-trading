# -*- coding: utf-8 -*-
"""
数据预缓存脚本
在回测前预先下载所有需要的K线数据
一次性下载，永久缓存，后续回测零等待
"""

import os
import time
from datetime import datetime

# 所有需要预缓存的股票池（去重）
ALL_STOCKS = list(dict.fromkeys([
    # 核心蓝筹股
    '600036', '000858', '601318', '600519', '000333', '601012', '600276', '600887',
    '601166', '600900', '002475', '002594', '600030', '000001', '601328', '601398',
    '601939', '601288', '601818', '600016', '000002', '002352', '002460', '600009',
    # 周期股
    '601899', '000725', '600111', '002460', '601600', '000060', '000878', '002466',
    # 成长股
    '300750', '688012', '300059', '002475', '300014', '300274', '300015', '002371',
    '688561', '688111',
    # 次新股
    '301601', '301606', '301608', '301610', '301612', '301618', '301626', '301628',
    '301636', '301638', '301656', '688558', '688575', '688601', '688621', '301566',
    '301585', '301586', '301271', '301296', '301308', '301323', '301326', '301339',
    '301368', '301369', '301376', '301378', '301386',
]))

BENCHMARK_START = datetime(2026, 5, 26)
CACHE_DAYS = 150  # 预缓存150天数据（覆盖回测区间）


def main():
    from data.tushare_helper import TushareHelper

    print("=" * 60)
    print("数据预缓存 - 一次性下载K线数据")
    print("=" * 60)
    print(f"股票数量: {len(ALL_STOCKS)}")
    print(f"缓存天数: {CACHE_DAYS}天")
    print(f"回测区间: {BENCHMARK_START.strftime('%Y%m%d')} ~ 今日")
    print()

    helper = TushareHelper(cache_dir="data/cache")
    success = 0
    failed = 0
    total = len(ALL_STOCKS)

    for i, symbol in enumerate(ALL_STOCKS):
        try:
            df = helper.get_history_kline(symbol, days=CACHE_DAYS, end_date=None)
            if df is not None and not df.empty and 'close' in df.columns:
                success += 1
                status = "OK"
            else:
                failed += 1
                status = "EMPTY"
        except Exception as e:
            failed += 1
            status = f"ERR:{str(e)[:30]}"

        if (i + 1) % 10 == 0 or status != "OK":
            print(f"  [{i+1}/{total}] {symbol}: {status}")

    print()
    print(f"缓存完成: 成功 {success}/{total}, 失败 {failed}")
    print(f"缓存目录: {os.path.abspath('data/cache')}")


if __name__ == '__main__':
    main()
