import sys
sys.path.insert(0, '.')
from data.akshare_helper import AKShareHelper
import pandas as pd
import traceback

helper = AKShareHelper(cache_dir='data/cache')

for sym in ['600036', '000858', '601166']:
    print(f'\n=== Testing {sym} ===')
    try:
        df = helper.get_history_kline(sym, days=30, end_date='20260620')
        print(f'  type={type(df).__name__}, isinstance(DataFrame)={isinstance(df, pd.DataFrame)}')
        if isinstance(df, pd.DataFrame) and not df.empty:
            print(f'  Columns: {list(df.columns)}')
            print(f'  Head:\n{df.head(2)}')
            k = df
            if not isinstance(k, pd.DataFrame):
                print(f'  NOT DataFrame')
            elif k.empty:
                print(f'  Empty')
            elif 'close' not in k.columns:
                print(f'  NO close column! Available: {list(k.columns)}')
            else:
                c = k['close'].values
                v = k['volume'].values if 'volume' in k.columns else None
                print(f'  close type: {type(c).__name__}, len: {len(c)}')
    except Exception as e:
        print(f'  Exception: {type(e).__name__}: {e}')
