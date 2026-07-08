"""数据验证脚本"""
import tushare as ts
import os

print('=' * 50)
print('数据验证检查')
print('=' * 50)

# 1. Tushare连接
print('\n1. Tushare连接测试')
try:
    pro = ts.pro_api()
    df = pro.trade_cal(exchange='SSE', start_date='20260701', end_date='20260710')
    print(f'   Tushare: ✅ 正常 ({len(df)}行)')
except Exception as e:
    print(f'   Tushare: ❌ 失败 - {e}')

# 2. 价格数据
print('\n2. 价格数据测试')
try:
    df = ts.pro_bar(ts_code='000001.SZ', start_date='20270601', end_date='20270630')
    if df is not None and len(df) > 0:
        print(f'   价格数据: ✅ 正常')
        print(f'   最新价: {df["close"].iloc[-1]}')
    else:
        print(f'   价格数据: ❌ 返回为空')
except Exception as e:
    print(f'   价格数据: ❌ 失败')

# 3. 回测文件
print('\n3. 回测文件检查')
if os.path.exists('output/strategy_data.json'):
    print(f'   回测文件: ✅ 存在')
else:
    print(f'   回测文件: ❌ 不存在')

print('\n' + '=' * 50)
