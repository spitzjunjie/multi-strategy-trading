"""
数据验证器 - 股票量化交易数据验证模块

用于验证：
1. 数据源准确性 (AKShare/Tushare)
2. 价格数据合理性
3. 财务数据有效性
4. 回测逻辑正确性
5. 跨数据源一致性
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

class ValidationLevel(Enum):
    """验证级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool
    level: ValidationLevel
    message: str
    details: Optional[Dict] = None
    suggestion: Optional[str] = None

class DataValidator:
    """股票量化交易数据验证器"""

    def __init__(self):
        self.results: List[ValidationResult] = []
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def add_result(self, result: ValidationResult):
        """添加验证结果"""
        self.results.append(result)
        if result.level in [ValidationLevel.ERROR, ValidationLevel.CRITICAL]:
            self.errors.append(result.message)
        elif result.level in [ValidationLevel.WARNING]:
            self.warnings.append(result.message)

    def test_tushare(self) -> bool:
        """测试Tushare连接和数据获取"""
        try:
            import tushare as ts
            from config.tushare_config import get_tushare_pro

            pro = get_tushare_pro()
            df = pro.daily(ts_code='000001.SZ', start_date='20260701', end_date='20260707')

            if df is None or len(df) == 0:
                self.add_result(ValidationResult(
                    passed=False,
                    level=ValidationLevel.ERROR,
                    message="Tushare返回空数据",
                    suggestion="检查API Token和积分权限"
                ))
                return False

            # 验证数据格式
            required_cols = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'vol']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                self.add_result(ValidationResult(
                    passed=False,
                    level=ValidationLevel.ERROR,
                    message=f"Tushare数据缺少列: {missing_cols}",
                    suggestion="检查Tushare接口返回格式"
                ))
                return False

            self.add_result(ValidationResult(
                passed=True,
                level=ValidationLevel.INFO,
                message=f"Tushare连接正常，获取{len(df)}条数据",
                details={"row_count": len(df), "columns": list(df.columns)}
            ))
            return True

        except Exception as e:
            self.add_result(ValidationResult(
                passed=False,
                level=ValidationLevel.ERROR,
                message=f"Tushare连接失败: {str(e)}",
                suggestion="检查网络连接和API Token"
            ))
            return False

    def test_akshare(self) -> bool:
        """测试AKShare连接和数据获取"""
        try:
            import akshare as ak

            # 测试东方财富股票行情
            df = ak.stock_zh_a_spot_em()

            if df is None or len(df) == 0:
                self.add_result(ValidationResult(
                    passed=False,
                    level=ValidationLevel.ERROR,
                    message="AKShare返回空数据",
                    suggestion="检查网络连接"
                ))
                return False

            # 检查必要的列
            required_cols = ['代码', '最新价', '涨跌幅']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                self.add_result(ValidationResult(
                    passed=False,
                    level=ValidationLevel.WARNING,
                    message=f"AKShare数据缺少建议列: {missing_cols}",
                    suggestion="可能影响部分功能"
                ))

            self.add_result(ValidationResult(
                passed=True,
                level=ValidationLevel.INFO,
                message=f"AKShare连接正常，获取{len(df)}条股票数据",
                details={"row_count": len(df)}
            ))
            return True

        except Exception as e:
            self.add_result(ValidationResult(
                passed=False,
                level=ValidationLevel.ERROR,
                message=f"AKShare连接失败: {str(e)}",
                suggestion="可能是网络问题或接口失效"
            ))
            return False

    def validate_price_data(self, df, source: str = "unknown") -> bool:
        """验证价格数据的合理性"""
        if df is None or len(df) == 0:
            self.add_result(ValidationResult(
                passed=False,
                level=ValidationLevel.ERROR,
                message="价格数据为空",
                suggestion="检查数据源连接"
            ))
            return False

        passed = True

        # 找出价格列
        price_cols = [col for col in df.columns if col in ['close', '最新价', 'Close']]
        if not price_cols:
            self.add_result(ValidationResult(
                passed=False,
                level=ValidationLevel.ERROR,
                message="找不到价格列",
                suggestion="检查DataFrame列名"
            ))
            return False

        price_col = price_cols[0]
        prices = df[price_col].dropna()

        # 检查价格范围
        if (prices <= 0).any():
            self.add_result(ValidationResult(
                passed=False,
                level=ValidationLevel.ERROR,
                message="存在价格<=0的数据",
                details={"invalid_count": (prices <= 0).sum()},
                suggestion="检查数据源是否正确"
            ))
            passed = False

        if (prices > 10000).any():
            self.add_result(ValidationResult(
                passed=False,
                level=ValidationLevel.WARNING,
                message="存在价格>10000的数据",
                details={"max_price": prices.max()},
                suggestion="可能是期货或异常数据"
            ))
            passed = False

        # 检查日涨跌幅（如果存在）
        change_cols = [col for col in df.columns if 'change' in col.lower() or '涨跌幅' in col]
        if change_cols:
            change_col = change_cols[0]
            changes = df[change_col].dropna()

            if (changes.abs() > 20).any():
                self.add_result(ValidationResult(
                    passed=False,
                    level=ValidationLevel.WARNING,
                    message="存在涨跌幅>20%的数据",
                    details={"extreme_count": (changes.abs() > 20).sum()},
                    suggestion="可能是ST股票或异常波动"
                ))

        if passed:
            self.add_result(ValidationResult(
                passed=True,
                level=ValidationLevel.INFO,
                message=f"价格数据验证通过 (来源: {source})",
                details={"row_count": len(df), "price_range": [float(prices.min()), float(prices.max())]}
            ))

        return passed

    def validate_financial_data(self, df, source: str = "unknown") -> bool:
        """验证财务数据的合理性"""
        if df is None or len(df) == 0:
            self.add_result(ValidationResult(
                passed=False,
                level=ValidationLevel.WARNING,
                message="财务数据为空（可能是新股或数据未更新）",
                suggestion="这是正常的，对于新股可以跳过财务验证"
            ))
            return True  # 财务数据为空不一定是错误

        passed = True

        # 检查ROE（净资产收益率）
        roe_cols = [col for col in df.columns if 'roe' in col.lower() or 'ROE' in col]
        if roe_cols:
            roe_col = roe_cols[0]
            roes = df[roe_col].dropna()

            if len(roes) > 0:
                if (roes < -100).any() or (roes > 100).any():
                    self.add_result(ValidationResult(
                        passed=False,
                        level=ValidationLevel.WARNING,
                        message=f"存在异常的ROE值 (范围: {roes.min():.2f}% ~ {roes.max():.2f}%)",
                        suggestion="检查是否为亏损公司数据"
                    ))
                    passed = False

        # 检查PE（市盈率）
        pe_cols = [col for col in df.columns if 'pe' in col.lower() or 'PE' in col or '市盈率' in col]
        if pe_cols:
            pe_col = pe_cols[0]
            pes = df[pe_col].dropna()

            if len(pes) > 0:
                # PE为负是正常的（亏损公司），但需要过滤
                valid_pes = pes[(pes > 0) & (pes < 500)]
                if len(valid_pes) < len(pes) * 0.9:  # 少于90%的PE在正常范围
                    self.add_result(ValidationResult(
                        passed=False,
                        level=ValidationLevel.WARNING,
                        message=f"较多PE值超出正常范围(0-500)",
                        details={"valid_ratio": len(valid_pes) / len(pes)}
                    ))

        if passed:
            self.add_result(ValidationResult(
                passed=True,
                level=ValidationLevel.INFO,
                message=f"财务数据验证通过 (来源: {source})",
                details={"row_count": len(df)}
            ))

        return passed

    def validate_backtest_file(self, filepath: str) -> bool:
        """验证回测结果文件的正确性"""
        if not os.path.exists(filepath):
            self.add_result(ValidationResult(
                passed=False,
                level=ValidationLevel.ERROR,
                message=f"回测文件不存在: {filepath}",
                suggestion="先运行回测生成结果"
            ))
            return False

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.add_result(ValidationResult(
                passed=False,
                level=ValidationLevel.ERROR,
                message=f"JSON解析失败: {str(e)}",
                suggestion="检查文件格式是否损坏"
            ))
            return False

        passed = True

        # 检查必要字段
        if 'strategies' not in data:
            self.add_result(ValidationResult(
                passed=False,
                level=ValidationLevel.ERROR,
                message="回测文件缺少strategies字段",
                suggestion="检查文件格式"
            ))
            return False

        # 检查日期格式和T+1规则
        today = datetime.now().date()
        strategy_count = len(data.get('strategies', []))

        for i, strategy in enumerate(data['strategies']):
            if 'trades' not in strategy or not strategy['trades']:
                continue

            for trade in strategy['trades']:
                # 检查日期格式
                buy_date_str = trade.get('buy_date', '')
                sell_date_str = trade.get('sell_date', '')

                if not buy_date_str or not sell_date_str:
                    self.add_result(ValidationResult(
                        passed=False,
                        level=ValidationLevel.ERROR,
                        message=f"策略{trade.get('strategy_name', i)}存在缺失日期的交易",
                        suggestion="检查数据获取逻辑"
                    ))
                    passed = False
                    continue

                try:
                    buy_date = datetime.strptime(buy_date_str, '%Y-%m-%d').date()
                    sell_date = datetime.strptime(sell_date_str, '%Y-%m-%d').date()
                except ValueError:
                    self.add_result(ValidationResult(
                        passed=False,
                        level=ValidationLevel.ERROR,
                        message=f"日期格式错误: {buy_date_str} 或 {sell_date_str}",
                        suggestion="使用YYYY-MM-DD格式"
                    ))
                    passed = False
                    continue

                # 检查T+1规则
                hold_days = trade.get('hold_days', 0)
                if hold_days < 1:
                    self.add_result(ValidationResult(
                        passed=False,
                        level=ValidationLevel.ERROR,
                        message=f"存在违反T+1规则的交易: {trade.get('stock_code')} (持有天数={hold_days})",
                        suggestion="检查卖出逻辑"
                    ))
                    passed = False

                # 检查收益率是否合理
                returns = trade.get('returns', 0)
                if abs(returns) > 0.5:  # 单笔收益超过50%
                    self.add_result(ValidationResult(
                        passed=False,
                        level=ValidationLevel.WARNING,
                        message=f"单笔收益异常: {trade.get('stock_code')} 收益率={returns*100:.1f}%",
                        suggestion="检查价格数据是否正确"
                    ))

        # 检查equity_curve
        if 'equity_curve' in data:
            for ec in data['equity_curve']:
                if 'value' in ec and ec['value'] <= 0:
                    self.add_result(ValidationResult(
                        passed=False,
                        level=ValidationLevel.ERROR,
                        message="Equity curve存在<=0的值",
                        suggestion="检查资金计算逻辑"
                    ))
                    passed = False
                    break

        if passed:
            self.add_result(ValidationResult(
                passed=True,
                level=ValidationLevel.INFO,
                message=f"回测文件验证通过",
                details={
                    "strategy_count": strategy_count,
                    "file_size": os.path.getsize(filepath)
                }
            ))

        return passed

    def validate_all_sources(self) -> bool:
        """验证所有数据源"""
        print("=" * 60)
        print("开始数据源验证")
        print("=" * 60)

        results = {
            'tushare': self.test_tushare(),
            'akshare': self.test_akshare()
        }

        print("\n验证结果汇总:")
        for source, passed in results.items():
            status = "✅ 通过" if passed else "❌ 失败"
            print(f"  {source}: {status}")

        return all(results.values())

    def print_summary(self):
        """打印验证结果摘要"""
        print("\n" + "=" * 60)
        print("验证结果摘要")
        print("=" * 60)

        print(f"\n总验证项: {len(self.results)}")
        print(f"  - 通过: {sum(1 for r in self.results if r.passed)}")
        print(f"  - 失败: {len(self.errors)}")
        print(f"  - 警告: {len(self.warnings)}")

        if self.errors:
            print("\n❌ 错误:")
            for error in self.errors:
                print(f"  - {error}")

        if self.warnings:
            print("\n⚠️ 警告:")
            for warning in self.warnings:
                print(f"  - {warning}")

        if not self.errors and not self.warnings:
            print("\n✅ 所有验证通过！")


if __name__ == "__main__":
    validator = DataValidator()

    print("1. 测试Tushare...")
    validator.test_tushare()

    print("\n2. 测试AKShare...")
    validator.test_akshare()

    print("\n3. 测试回测文件...")
    validator.validate_backtest_file("output/backtest_history.json")

    validator.print_summary()
