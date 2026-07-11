import sys
sys.path.insert(0, '.')
from data.akshare_helper import AKShareHelper
import pandas as pd
import traceback

helper = AKShareHelper(cache_dir='data/cache')
pool = ['600036', '000858', '601318', '600519', '000333']

for sym in pool:
    print(f"\n=== {sym} ===")
    try:
        df = helper.get_history_kline(sym, days=30, end_date='20260620')
        print(f"  get_history_kline OK: type={type(df).__name__}")
        
        # Check type
        if not isinstance(df, pd.DataFrame):
            print(f"  SKIP: not DataFrame, type={type(df)}")
            continue
        
        if df.empty:
            print(f"  SKIP: empty DataFrame")
            continue
            
        if 'close' not in df.columns:
            print(f"  SKIP: no 'close' column, cols={list(df.columns)}")
            continue
            
        # Test signal
        c = df['close'].values
        v = df['volume'].values if 'volume' in df.columns else None
        
        # _after_hours_signal logic
        if len(c) >= 10 and c[-1] > c[-10:].mean():
            ret5 = (c[-1] / c[-6] - 1) * 100 if len(c) >= 6 else 0
            if ret5 > 2:
                print(f"  TRIGGERED: ret5={ret5:.1f}%")
            else:
                print(f"  No signal: ret5={ret5:.1f}%")
        else:
            print(f"  No signal: c[-1]={c[-1]}, ma10={c[-10:].mean():.2f}")
            
    except Exception as e:
        print(f"  EXCEPTION: {type(e).__name__}: {e}")
        traceback.print_exc()
