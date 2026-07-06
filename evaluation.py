# -*- coding: utf-8 -*-
"""
策略评估模块
多维度量化策略好坏，生成综合评分和等级
"""

import os
from datetime import datetime
import numpy as np


class StrategyEvaluator:
    """策略评估器：多维度量化策略好坏"""

    def evaluate(self, strategy_result):
        """评估单个策略

        Args:
            strategy_result: backtest输出的strategy dict

        Returns:
            dict: 包含核心指标、派生指标、综合评分和等级
        """
        metrics = {
            'name': strategy_result.get('name', 'Unknown'),
            'category': strategy_result.get('category', ''),
            'version': strategy_result.get('version', '1.0.0'),
            # 核心指标
            'total_return': strategy_result.get('total_return', 0),
            'sharpe_ratio': strategy_result.get('sharpe_ratio', 0),
            'max_drawdown': strategy_result.get('max_drawdown', 0),
            'win_rate': strategy_result.get('win_rate', 0),
            # 派生指标
            'calmar_ratio': self._calmar(strategy_result),
            'profit_loss_ratio': self._profit_loss_ratio(strategy_result),
            'return_stability': self._return_stability(strategy_result),
            'trade_count': len(strategy_result.get('trades', [])),
            # 综合评分
            'composite_score': 0,
            'grade': 'D',
        }
        metrics['composite_score'] = self._composite_score(metrics)
        metrics['grade'] = self._grade(metrics['composite_score'])
        return metrics

    def _calmar(self, r):
        """卡玛比率 = 年化收益 / 最大回撤"""
        ret = r.get('total_return', 0)
        dd = r.get('max_drawdown', 0)
        if dd <= 0:
            return 0
        return ret / dd

    def _profit_loss_ratio(self, r):
        """盈亏比 = 平均盈利 / 平均亏损"""
        trades = r.get('trades', [])
        wins = [t.get('profit', 0) for t in trades if t.get('profit', 0) > 0]
        losses = [-t.get('profit', 0) for t in trades if t.get('profit', 0) < 0]
        if not wins or not losses:
            return 0
        avg_win = sum(wins) / len(wins)
        avg_loss = sum(losses) / len(losses)
        if avg_loss == 0:
            return 0
        return avg_win / avg_loss

    def _return_stability(self, r):
        """收益稳定性：权益曲线线性拟合R²"""
        curve = r.get('equity_curve', [])
        if len(curve) < 5:
            return 0
        try:
            x = np.arange(len(curve))
            y = np.array(curve, dtype=float)
            coeffs = np.polyfit(x, y, 1)
            y_pred = np.polyval(coeffs, x)
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - y.mean()) ** 2)
            if ss_tot == 0:
                return 0
            r_squared = 1 - ss_res / ss_tot
            # R²可能为负，截断到[0,1]
            return max(0, min(1, r_squared))
        except Exception:
            return 0

    def _composite_score(self, m):
        """综合评分0-100
        权重：夏普30% + 收益25% + 回撤20% + 胜率15% + 稳定性10%
        """
        score = 0.0
        # 夏普0-3映射0-30
        score += min(max(m['sharpe_ratio'], 0), 3) / 3 * 30
        # 收益0-30%映射0-25
        score += min(max(m['total_return'] * 100, 0), 30) / 30 * 25
        # 回撤0-30%映射20-0（回撤越小分越高）
        score += (1 - min(m['max_drawdown'], 0.3) / 0.3) * 20
        # 胜率0-1映射0-15
        score += m['win_rate'] * 15
        # 稳定性0-1映射0-10
        score += m['return_stability'] * 10
        return round(score, 1)

    def _grade(self, score):
        """等级划分：S/A/B/C/D"""
        if score >= 80:
            return 'S'
        if score >= 65:
            return 'A'
        if score >= 50:
            return 'B'
        if score >= 35:
            return 'C'
        return 'D'

    def evaluate_batch(self, strategy_results):
        """批量评估策略

        Args:
            strategy_results: backtest输出的strategies列表

        Returns:
            list: 评估结果列表，按综合分降序排序
        """
        evaluations = [self.evaluate(r) for r in strategy_results]
        evaluations.sort(key=lambda x: x['composite_score'], reverse=True)
        return evaluations

    def grade_stats(self, evaluations):
        """统计各等级策略数量"""
        stats = {grade: 0 for grade in ['S', 'A', 'B', 'C', 'D']}
        for e in evaluations:
            stats[e['grade']] = stats.get(e['grade'], 0) + 1
        return stats


if __name__ == "__main__":
    # 测试评估器
    test_result = {
        'name': '测试策略',
        'category': '因子',
        'total_return': 0.15,
        'sharpe_ratio': 1.5,
        'max_drawdown': 0.08,
        'win_rate': 0.6,
        'equity_curve': [30000, 30500, 31000, 31500, 32000, 32500, 33000, 33500, 34000, 34500],
        'trades': [
            {'profit': 500},
            {'profit': -200},
            {'profit': 800},
        ]
    }
    evaluator = StrategyEvaluator()
    result = evaluator.evaluate(test_result)
    print("评估结果:")
    for k, v in result.items():
        print(f"  {k}: {v}")
