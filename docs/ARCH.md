# 量化策略系统架构文档 (ARCH.md)

> 本文档遵循 Vibe Dev Workflow 规范，记录系统架构设计。

---

## 一、系统概述

### 1.1 项目背景

A股多策略量化交易回测与展示系统，通过自动化回测筛选优质策略并可视化展示。

### 1.2 核心目标

- 自动化回测 90+ 个选股策略
- 多维度评估策略表现（收益、夏普、回撤、胜率）
- 定时任务保持策略数据最新
- GitHub Pages 可视化展示

---

## 二、技术架构

### 2.1 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **数据获取** | Tushare Pro, AKShare | 双数据源自动切换 |
| **回测引擎** | Python | 自定义回测逻辑 |
| **前端展示** | HTML/CSS/JS | GitHub Pages 静态站点 |
| **CI/CD** | GitHub Actions | 每日定时回测 |
| **AI 辅助** | Codex CLI (MiniMax) | 策略迭代优化 |

### 2.2 目录结构

```
stock_intelligence/multi_strategy_trading/
├── strategies/                    # 策略模块
│   ├── base.py                  # 策略基类
│   ├── technical_strategies.py   # 技术指标策略
│   ├── event_strategies.py      # 事件驱动策略
│   ├── factor_strategies.py     # 因子策略
│   └── special_strategies.py     # 特殊策略
│
├── timing/                       # 择时模块
│   └── timing.py                # 均线、RSI、MACD等
│
├── trading/                      # 交易模拟
│   └── simulator.py             # 交易模拟器
│
├── data/                         # 数据层
│   ├── akshare_helper.py       # AKShare封装
│   ├── cache/                  # 数据缓存
│   └── tushare_config.py      # Tushare配置
│
├── config/                       # 配置
│   └── config.py                # 配置文件
│
├── output/                       # 输出
│   ├── strategy_data.json       # 策略数据
│   └── backtest_history.json    # 历史回测
│
├── docs/                         # 文档
│   ├── ARCH.md                  # 本架构文档
│   ├── PROJECT.md               # 项目进度
│   └── RELEASE_NOTES.md         # 发布记录
│
├── backtest.py                   # GitHub每日回测
├── backtest_history.py            # 历史回测
├── verify_strategies.py          # 策略验证
├── data_validator.py            # 数据验证
├── config.py                    # 配置
├── .gitignore                   # Git忽略
└── requirements.txt              # 依赖
```

---

## 三、数据架构

### 3.1 数据源

| 数据源 | 用途 | 稳定性 | 配置 |
|--------|------|--------|------|
| **Tushare Pro** | K线、财务数据 | ✅ 稳定 | `TUSHARE_TOKEN` 环境变量 |
| **AKShare** | 备用数据源 | ⚠️ 不稳定 | 无需密钥 |

### 3.2 数据流

```
Tushare/AKShare → Data Helper → 回测引擎 → 策略评估 → strategy_data.json → GitHub Pages
```

### 3.3 数据存储

| 文件 | 内容 | 更新频率 |
|------|------|----------|
| `strategy_data.json` | 所有策略评分和指标 | 每日更新 |
| `backtest_history.json` | 历史回测记录 | 每日更新 |

---

## 四、策略架构

### 4.1 策略分类

| 类别 | 数量 | 示例 |
|------|------|------|
| **趋势策略** | 8 | 多周期共振、均线多头排列 |
| **事件驱动** | 12 | 高管增持、业绩超预期 |
| **因子策略** | 15 | ROE选股、现金流质量 |
| **技术突破** | 10 | 量价突破、MACD金叉 |
| **特殊策略** | 5 | ST摘帽潜伏、国产替代 |
| **新闻情感** | 2 | 新闻情感选股 |

### 4.2 策略基类

```python
class BaseStrategy:
    name: str                    # 策略名称
    category: str                # 策略类别
    
    def select_stocks(self, date) -> List[Dict]:
        """选股方法，返回格式：[{symbol, name, reason}, ...]"""
        pass
    
    def get_params(self) -> Dict:
        """返回策略参数"""
        pass
```

### 4.3 评估指标

| 指标 | 计算方式 | 权重 |
|------|----------|------|
| **综合评分** | 加权计算 | 100分 |
| **收益率** | 策略收益 | 30% |
| **夏普比率** | 风险调整收益 | 25% |
| **最大回撤** | 权益曲线最大回撤 | 20% |
| **胜率** | 盈利次数/总次数 | 15% |
| **稳定性** | 收益标准差 | 10% |

---

## 五、部署架构

### 5.1 GitHub Actions

| 工作流 | 触发条件 | 功能 |
|--------|----------|------|
| `backtest.yml` | 每天 18:30 (UTC 10:30) | **每日单次回测（上线策略）** |
| `deploy.yml` | 代码推送后 | 部署到 GitHub Pages |

### 5.2 Codex 本地/云端

| 任务 | 触发条件 | 功能 |
|------|----------|------|
| 历史回测 | 按需 | 历史窗口回测（新策略） |
| 代码修复 | 失败时 | 自动修复代码问题 |
| 策略优化 | 按需 | ODAEI 循环优化 |

### 5.3 GitHub Pages

- 仓库：`spitzjunjie/q8k3m2n1`
- 页面：`https://spitzjunjie.github.io/q8k3m2n1/`
- 数据源：`docs/output/strategy_data.json`

---

## 六、安全架构

### 6.1 API密钥管理

```python
# ✅ 正确
import os
TUSHARE_TOKEN = os.environ.get('TUSHARE_TOKEN')

# ❌ 错误
TUSHARE_TOKEN = "abc123..."
```

### 6.2 .gitignore 配置

```
.env
*.token
output/*.json
backtest_history*.json
*.log
__pycache__/
```

### 6.3 GitHub Secrets

```
Settings → Secrets and variables → Actions
  ├── TUSHARE_TOKEN
  ├── MINIMAX_API_KEY
  └── GROQ_API_KEY
```

---

## 七、SOP 体系

### 7.1 三大 SOP

| SOP | 功能 | 触发场景 |
|-----|------|----------|
| `quant-strategy-deploy` | 策略上线 | 新策略首次上线 |
| `strategy-param-change` | 参数修改 | 修改现有策略参数 |
| `strategy-iteration` | 自动迭代 | ODAEI 循环优化 |

### 7.2 SOP 关系图

```
quant-strategy-deploy → 策略上线
         ↓
strategy-param-change → 参数修改
         ↓
strategy-iteration → ODAEI 自动迭代
         ↓
    直到不能优化为止
```

---

## 八、变更记录

### 架构重大变更

| 日期 | 变更内容 | 原因 |
|------|----------|------|
| 2026-07-11 | 添加风控模块（止盈止损） | 增强策略稳定性 |
| 2026-07-09 | 添加数据源自动切换 | 解决AKShare不稳定问题 |
| 2026-07-07 | 初始架构设计 | 项目启动 |

---

## 九、联系方式

- **GitHub**: https://github.com/spitzjunjie/q8k3m2n1
- **Dashboard**: https://spitzjunjie.github.io/q8k3m2n1/
- **问题反馈**: GitHub Issues

---

*本文档遵循 Vibe Dev Workflow 规范，每次架构变更时更新。*
