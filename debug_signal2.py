import sys
sys.path.insert(0, '.')
from data.akshare_helper import AKShareHelper
import pandas as pd

helper = AKShareHelper(cache_dir='data/cache')
df = helper.get_history_kline('600036', days=30, end_date='20260620')

print(f"DataFrame type: {type(df)}")
print(f"Columns: {list(df.columns)}")
print(f"close in df.columns: {'close' in df.columns}")
print(f"df['close'] type: {type(df['close'])}")
print(f"df['close'].values type: {type(df['close'].values)}")

# Test _safe_data
k = df
print(f"\nisinstance DataFrame: {isinstance(k, pd.DataFrame)}")
print(f"k.empty: {k.empty}")
print(f"'close' in k.columns: {'close' in k.columns}")

if isinstance(k, pd.DataFrame) and not k.empty and 'close' in k.columns:
    c = k['close'].values
    v = k['volume'].values if 'volume' in k.columns else None
    print(f"c type: {type(c)}, len: {len(c)}")
    print(f"v type: {type(v)}, len: {len(v) if v is not None else None}")

# Test signal function
from fast_backtest import _auction_signal, _after_hours_signal
print(f"\n_auction_signal(df): {_auction_signal(df)}")
print(f"_after_hours_signal(df): {_after_hours_signal(df)}")

# Test unpacking
result = _auction_signal(df)
print(f"\nUnpacking: triggered={result[0]}, reason={result[1]}")
