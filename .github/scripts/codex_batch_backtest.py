#!/usr/bin/env python3
"""
Codex 本地批处理回测脚本

专门为 Codex 执行设计，用于本地/云端沙箱运行历史回测。

使用方法：
    python codex_batch_backtest.py --batch 1
    python codex_batch_backtest.py --batch all
    python codex_batch_backtest.py --source tushare --strategies "多周期共振,均线多头"
"""

import os
import sys
import json
import argparse
import subprocess
from datetime import datetime
from typing import List, Optional

# 策略批次定义
BATCH_STRATEGIES = {
    '1': '护城河选股,质量因子选股,GARP成长,股权激励,周期股择时',
    '2': '回购信号,龙虎榜跟风,打板接力,次新股,尾盘抢筹',
    '3': '集合竞价,戴维斯双击,股东户数变化,困境反转,涨停封单',
    '4': '跌停撬板,限售解禁博弈,游资席位跟踪,ETF折溢价套利,网格交易,可转债双低,可转债下修博弈',
}

# 默认数据源
DEFAULT_SOURCE = 'tushare'


class CodexBatchBacktest:
    """Codex 批处理回测"""
    
    def __init__(self, source: str = DEFAULT_SOURCE):
        self.source = source
        self.results = []
        self.errors = []
        
    def log(self, message: str, level: str = 'info'):
        """日志输出"""
        prefix = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'error': '❌',
            'success': '✅',
            'start': '🚀',
            'done': '🏁'
        }.get(level, '•')
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {prefix} {message}")
    
    def get_backtest_command(self, strategies: str = '') -> List[str]:
        """构建回测命令"""
        cmd = ['python', 'backtest_history.py', '--source', self.source]
        
        if strategies:
            cmd.extend(['--strategies', strategies])
        
        return cmd
    
    def run_backtest(self, strategies: str = '', label: str = '') -> bool:
        """运行单次回测"""
        if label:
            self.log(f"开始回测: {label}", 'start')
        else:
            self.log(f"开始回测 (数据源: {self.source})", 'start')
        
        cmd = self.get_backtest_command(strategies)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=False,  # 实时输出
                timeout=3600  # 1小时超时
            )
            
            if result.returncode == 0:
                self.log(f"回测成功: {label or '完成'}", 'success')
                return True
            else:
                self.log(f"回测失败: {label or '失败'}", 'error')
                self.errors.append({
                    'strategies': strategies,
                    'label': label,
                    'returncode': result.returncode
                })
                return False
                
        except subprocess.TimeoutExpired:
            self.log(f"回测超时: {label or '超时'}", 'error')
            self.errors.append({
                'strategies': strategies,
                'label': label,
                'error': 'timeout'
            })
            return False
        except Exception as e:
            self.log(f"回测异常: {str(e)}", 'error')
            self.errors.append({
                'strategies': strategies,
                'label': label,
                'error': str(e)
            })
            return False
    
    def run_batch(self, batch: str) -> bool:
        """运行批次回测"""
        strategies = BATCH_STRATEGIES.get(batch, '')
        
        if not strategies:
            self.log(f"无效批次: {batch}", 'error')
            return False
        
        self.log(f"="*50, 'info')
        self.log(f"批次 {batch} 回测开始", 'start')
        self.log(f"策略: {strategies}", 'info')
        self.log(f"="*50, 'info')
        
        # 运行回测
        success = self.run_backtest(strategies=strategies, label=f"批次{batch}")
        
        return success
    
    def run_all(self) -> bool:
        """运行全部批次"""
        self.log(f"="*60, 'info')
        self.log(f"全部批次回测开始", 'start')
        self.log(f"="*60, 'info')
        
        for batch, strategies in BATCH_STRATEGIES.items():
            self.log(f"-"*50, 'info')
            self.log(f"批次 {batch}: {strategies}", 'info')
            
            success = self.run_backtest(strategies=strategies, label=f"批次{batch}")
            
            if not success:
                self.log(f"批次 {batch} 失败，继续下一批次", 'warning')
        
        self.log(f"="*60, 'done')
        self.log(f"全部批次回测完成", 'done')
        self.log(f"="*60, 'info')
        
        return len(self.errors) == 0
    
    def generate_report(self) -> dict:
        """生成回测报告"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'source': self.source,
            'errors': self.errors,
            'error_count': len(self.errors),
            'success_count': len(BATCH_STRATEGIES) - len(self.errors)
        }
        
        report_path = 'output/codex_batch_report.json'
        os.makedirs('output', exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        return report


def main():
    parser = argparse.ArgumentParser(
        description='Codex 本地批处理回测脚本'
    )
    parser.add_argument(
        '--batch',
        choices=['1', '2', '3', '4', 'all'],
        default='all',
        help='回测批次（默认: all）'
    )
    parser.add_argument(
        '--source',
        choices=['tushare', 'akshare'],
        default=DEFAULT_SOURCE,
        help=f'数据源（默认: {DEFAULT_SOURCE}）'
    )
    parser.add_argument(
        '--strategies',
        type=str,
        default='',
        help='指定策略（逗号分隔）'
    )
    
    args = parser.parse_args()
    
    # 创建回测器
    tester = CodexBatchBacktest(source=args.source)
    
    # 运行回测
    if args.strategies:
        # 指定策略
        tester.log(f"运行指定策略: {args.strategies}", 'start')
        success = tester.run_backtest(strategies=args.strategies)
    elif args.batch == 'all':
        # 全部批次
        success = tester.run_all()
    else:
        # 单个批次
        success = tester.run_batch(args.batch)
    
    # 生成报告
    report = tester.generate_report()
    
    print(f"\n{'='*60}")
    print(f"回测报告")
    print(f"{'='*60}")
    print(f"数据源: {report['source']}")
    print(f"成功: {report['success_count']} 个批次")
    print(f"失败: {report['error_count']} 个批次")
    print(f"报告: output/codex_batch_report.json")
    print(f"{'='*60}")
    
    # 如果有失败，显示错误
    if report['errors']:
        print(f"\n失败详情:")
        for err in report['errors']:
            print(f"  - {err.get('label', '未知')}: {err.get('error', '未知错误')}")
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
