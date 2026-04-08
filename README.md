# A股市场情绪评分框架

> **轻量级 A 股市场情绪量化系统** — 支持多数据源、输出情绪得分与冰点/转暖信号

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 功能亮点

- **多维度情绪特征** — 20+ 个关键市场情绪指标（涨跌比、涨跌停、量能、集合竞价等）
- **三种数据源** — `westock`（实时全市场聚合）/ `csv`（本地文件）/ `download`（akshare/tushare）
- **情绪状态分类** — 自动识别主升、分歧、修复、退潮、冰点等 7 种市场状态
- **冰点信号识别** — 智能识别市场冰点，提示转暖时机
- **完整回测系统** — 冰点策略、情绪动量、逆向策略，20+ 绩效指标
- **可视化报告** — HTML 报告 + 图表分析

---

## 数据源说明

### westock（推荐 ✅）

基于腾讯自选股 **westock-data CLI** 获取全市场聚合数据，**无需注册、无需 token、覆盖沪深 5000+ 只股票**。

| 数据来源 | 覆盖范围 | 核心指标 |
|----------|----------|----------|
| `changedist hs` | 沪深全市场 | 涨跌停数量、11 个涨幅区间分布 |
| `market sh000001` | 上证指数历史 | 成交额、主力净流入、日内高低 |

> **注意**：`changedist` 仅支持当日实时查询，历史数据通过每日自动缓存逐步积累（详见下方）。

### csv / download（akshare / tushare）

使用逐股 OHLCV 数据，适合历史回测。

---

## 快速开始

### 1. 安装

```bash
pip install -e .
```

### 2. 使用 westock 数据源（推荐）

#### 创建配置文件

```bash
cp example_westock_config.yaml config.yaml
```

修改 `config.yaml` 中的日期范围：

```yaml
provider:
  type: westock
  westock:
    start_date: "2025-01-01"
    end_date: "2026-04-08"
    market: hs
    cache_dir: "./westock_cache"   # 历史数据缓存目录
```

#### 运行情绪分析

```bash
ashare-sentiment analyze config.yaml --output sentiment.csv
```

输出示例：
```
使用 WeStock 市场聚合特征计算...
Saved sentiment analysis to sentiment.csv

最新市场情绪状态:
  日期: 2026-04-08
  情绪得分: 0.832
  情绪状态: 主升
```

#### 每日缓存（建议每个交易日收盘后运行）

```bash
# 手动运行
ashare-sentiment westock-cache --cache-dir ./westock_cache

# 或使用配置文件
ashare-sentiment westock-cache --config config.yaml
```

> 系统已内置**定时调度**（每个工作日 15:35 自动运行），缓存目录逐步积累历史数据后，历史情绪特征将全面有效。

---

### 3. 使用 CSV / akshare 数据源

```bash
# 下载 akshare 数据（免费）
ashare-sentiment download --source akshare \
  --start-date 2024-01-01 --end-date 2024-12-31 \
  --max-stocks 100 --delay 1.0

# 运行分析
cp example_config_download.yaml config.yaml
ashare-sentiment analyze config.yaml --output sentiment.csv --advanced
```

---

## 情绪特征说明

### 基础特征（7 个）

| 特征名 | 中文名 | 说明 |
|--------|--------|------|
| `advance_decline` | 涨跌比 | 上涨股票占比（排除平盘） |
| `limit_up_down` | 涨跌停净比 | `(涨停 - 跌停) / 总数` |
| `gap_breadth` | 强势股广度 | `(涨停 + >7% 区间) / 总数` |
| `reversal_breadth` | 反转候选广度 | `-2%~-5% 区间 / 总数` |
| `turnover_surge` | 量能激增 | 当日成交额 / MA20 成交额 |
| `intraday_volatility` | 日内波动率 | `(最高 - 最低) / 开盘` |
| `amount_breadth` | 成交金额广度 | 同 advance_decline 代理 |

### 高级特征（10+ 个）

| 特征名 | 中文名 | 说明 |
|--------|--------|------|
| `advance_ratio` | 上涨比例 | 上涨股票 / 总数 |
| `limit_up_ratio` | 涨停比例 | 涨停股票 / 总数（正向） |
| `limit_down_ratio` | 跌停比例 | `-(跌停 / 总数)`（已取反，跌停多→负向） |
| `limit_net_ratio` | 涨跌停净比 | 同 limit_up_down |
| `continuation_stocks` | 连板代理 | 涨停数量近似代理 |
| `volume_change_ratio` | 量能变化率 | 日成交额环比变化 |
| `abnormal_movement_count` | 大幅波动数 | 涨停+跌停+>7%+<-7% 合计 |
| `auction_strength` | 开盘强度代理 | 指数当日涨跌幅 |

> **符号约定**：`limit_down_ratio` 在特征层已取反，权重配置保持正值即可正确驱动负向评分。

---

## 情绪状态分类

| 状态 | 中文名 | 特征描述 | 操作建议 |
|------|--------|----------|----------|
| `MAIN_RISE` | 主升 | 上涨比例 >70%，涨停多，量能放大 | 可参与强势股，注意风险 |
| `WEAK_DIVERGENCE` | 弱分歧 | 涨跌相对平衡 | 适度参与，关注板块轮动 |
| `STRONG_DIVERGENCE` | 强分歧 | 涨跌分化明显，破板率高 | 谨慎操作 |
| `WEAK_RECOVERY` | 弱修复 | 小幅反弹，力度有限 | 谨慎乐观 |
| `STRONG_RECOVERY` | 强修复 | 快速反弹，量能配合 | 可积极参与超跌反弹 |
| `RETREAT` | 退潮 | 连续下跌，涨停减少 | 建议观望 |
| `ICE_POINT` | 冰点 | 极度悲观，成交萎缩 | 关注转暖信号，准备抄底 |

---

## 配置说明

### westock 配置（`example_westock_config.yaml`）

```yaml
provider:
  type: westock
  date_column: trade_date
  westock:
    start_date: "2025-01-01"
    end_date: "2026-04-08"
    market: hs                     # hs=沪深 | sh=沪市 | sz=深市
    index_codes:
      - sh000001                   # 主指数（用于量能数据）
      - sh000300
    timeout_seconds: 30
    retry_count: 3
    cache_dir: "./westock_cache"   # 建议设置，避免重复调用

weights:
  advance_decline: 1.0
  limit_up_ratio: 1.5
  limit_down_ratio: 1.5            # 特征值已取反，权重用正值即可
  limit_net_ratio: 1.3
  # ... 其余权重见示例文件

rolling_window: 20
```

### CSV 数据配置（`example_config.yaml`）

```yaml
provider:
  type: csv
  path: ./data
  date_column: trade_date
  symbol_column: ts_code

weights:
  advance_decline: 1.0
  limit_up_down: 1.0
  # ...

rolling_window: 20
```

---

## 命令行工具完整参考

```bash
# 情绪分析
ashare-sentiment analyze <config.yaml> --output <out.csv> [--advanced] [--analysis]

# westock 当日数据缓存（每日收盘后运行）
ashare-sentiment westock-cache [--config <config.yaml>] [--cache-dir ./westock_cache]

# 下载 akshare/tushare 数据
ashare-sentiment download --source akshare \
  --start-date 2024-01-01 --end-date 2024-12-31 \
  [--max-stocks 100] [--delay 1.0] [--all]

# 回测分析
ashare-sentiment backtest <backtest_config.yaml> \
  --start-date 2020-01-01 --end-date 2024-12-31 \
  --strategies ice_point momentum contrarian \
  --benchmarks sh000001 sh000300 \
  --summary
```

---

## 回测系统

### 支持策略

| 策略 | 说明 |
|------|------|
| `ice_point` | 冰点买入策略：在情绪冰点时入场，转暖信号时出场 |
| `momentum` | 情绪动量策略：跟随情绪得分方向交易 |
| `contrarian` | 逆向策略：在极度乐观时做空/回避，极度悲观时入场 |

### 绩效指标（20+）

- **收益率**：总收益率、年化收益率、累计收益率
- **风险**：夏普比率、索提诺比率、最大回撤、年化波动率
- **交易**：胜率、盈亏比、卡尔玛比率
- **对比**：与上证、深证、沪深300、中证500 的相关性

---

## 项目结构

```
ashare-sentiment/
├── src/sentiment_ashare/
│   ├── config.py                   # 配置类（SentimentConfig / WeStockConfig）
│   ├── cli.py                      # 命令行入口
│   ├── providers/
│   │   ├── westock_provider.py     # WeStock CLI 数据提供者 ⭐
│   │   ├── csv_provider.py         # CSV 文件数据提供者
│   │   └── data_loader.py          # 统一数据加载入口
│   ├── features/
│   │   ├── westock_features.py     # WeStock 专用特征计算 ⭐
│   │   ├── basic.py                # 基础特征（逐股数据）
│   │   ├── advanced.py             # 高级特征（逐股数据）
│   │   └── sentiment_classifier.py # 情绪状态分类
│   ├── scoring/
│   │   └── aggregate.py            # 情绪得分聚合（滚动Z-score）
│   └── backtest/                   # 回测引擎
├── example_westock_config.yaml     # WeStock 数据源配置示例 ⭐
├── example_config.yaml             # CSV 数据源配置示例
├── example_config_download.yaml    # 下载数据源配置示例
├── WESTOCK_DESIGN.md               # WeStock 适配技术设计文档
└── requirements.txt
```

---

## 数据流架构

```
westock-data CLI
  ├── changedist hs {date}   →  全市场涨跌停分布（5000+ 只股票）
  └── market sh000001 {range} →  指数历史行情（成交额、主力净流入）
          ↓
    WeStockProvider.fetch()
          ↓
    market-level DataFrame（每行一天）
          ↓
    compute_westock_features()
          ↓
    17 个情绪特征列（与 WeightsConfig 键名对应）
          ↓
    compute_sentiment_score()
    （滚动Z-score + 加权求和 + 情绪分类）
          ↓
    sentiment.csv（得分 + 状态 + 冰点信号）
```

---

## 注意事项

1. **westock 历史数据**：`changedist` API 仅支持当日查询，历史涨跌停数据需通过每日缓存逐步积累。建议从今天起每天收盘后运行 `westock-cache` 命令（或依赖内置定时任务自动执行）。
2. **数据量与评分质量**：滚动窗口为 20 天，至少需要 20 个交易日的数据才能获得有效情绪得分。
3. **部分特征降级**：`break_board_ratio`（破板率）、`seal_board_ratio`（封板率）、`heaven_earth_count`（地天板）无法从聚合数据计算，自动返回 NaN（评分时跳过），可在配置中将权重设为 0 显式禁用。
4. **akshare 频率限制**：使用 akshare 下载数据时建议设置 `--max-stocks 50 --delay 1.0` 避免被限速。

---

## 开发文档

- [WeStock 适配技术设计文档](WESTOCK_DESIGN.md)
- [回测使用指南](BACKTEST_GUIDE.md)
- [回测实现总结](BACKTEST_IMPLEMENTATION_SUMMARY.md)

---

## License

MIT License — 仅供学习和研究使用，不构成投资建议。
