# WeStock 数据源适配方案 — 完整技术设计文档

> 文档版本：v1.0  
> 编写日期：2026-04-08  
> 作者：Design Agent  
> 状态：✅ 已完成，可直接用于实现

---

## 1. 背景与目标

### 1.1 现状

当前 `ashare-sentiment` 项目支持两种数据源：
- `csv`：从本地 CSV 文件加载逐股 OHLCV 数据
- `download`：通过 akshare/tushare 下载逐股数据

两种方式的核心数据格式均为 **逐股明细 DataFrame**（每行 = 一只股票 × 一天），提供给 `features/basic.py` 和 `features/advanced.py` 做横截面特征计算。

### 1.2 westock-data CLI 能力

工具路径：`node /Users/mingzhegao/.workbuddy/skills/westock-data/scripts/index.js`

| 命令 | 说明 | 返回类型 |
|------|------|----------|
| `changedist hs [date]` | 当日沪深全市场涨跌区间分布 | 单日聚合 JSON |
| `changedist hs date1 date2` | 历史区间（注：实测仍返回单日数据） | 单日聚合 JSON |
| `market sh000001 date` | 指数单日行情 | 单日 JSON |
| `market sh000001 date1 date2` | 指数历史区间行情 | **数组 JSON** |
| `hot board N` | 热门板块 TOP N | 文本+格式化 |
| `board` | 行业资金流向 | 文本格式化 |
| `quote sh600000,sz000001` | 个股实时行情 | JSON |
| `kline sh600000 day 20 qfq` | 个股K线 | JSON |

**关键发现（实测结果）：**
1. `changedist` 返回**已聚合**的全市场统计，**不含逐股数据**
2. `market date1 date2` 返回的是**数组**（多个日期的指数行情），字段含 `turnoverValue`（总成交额）、`mainNetFlow`（主力资金净流入）
3. `board/hot board` 目前仅有文本格式，无 JSON 输出
4. **没有任何命令可以批量返回全市场逐股OHLCV数据**

---

## 2. 方案选型

### 2.1 方案A：WeStockFeatureCalculator（推荐 ✅）

**核心思路**：不模拟逐股 DataFrame，而是设计一套新的特征计算器，直接从 changedist + market 聚合数据中提取情绪特征，**绕过现有逐股计算路径**。

**优势：**
- 数据来源 100% 吻合 CLI 能力，无需额外 API 调用
- changedist 覆盖全市场 5000+ 只股票，数据代表性最强
- 单次 CLI 调用即可，延迟低
- 返回特征名称与 `WeightsConfig` 完全匹配，无需修改权重配置
- 节假日/无数据日自动以 NaN 填充，边界处理简单

**劣势：**
- 部分基础特征（如 `gap_breadth`、`reversal_breadth`）由于缺少个股开收盘数据，需重新定义或降级计算
- 与现有 `features/basic.py` 的调用路径不兼容，需新增独立特征计算函数

### 2.2 方案B：样本股批量拉取

**核心思路**：通过 `quote` 或 `kline` 接口批量拉取沪深300成分股（约300只），构造近似的逐股 DataFrame，复用现有特征函数。

**劣势（不推荐 ❌）：**
- 300只股票 × N天 = 数百次 CLI 调用，性能极差（每次约100ms+，总耗时 30秒以上）
- 成分股列表需要额外维护（akshare/tushare 依赖未消除）
- `quote` 接口返回实时行情，无法获取历史数据
- `kline` 每次只查一只股票，需300次调用获取历史数据
- 代表性差（300/5000 = 6%，而 changedist 是 100% 全市场）

### 2.3 结论

**选择方案A**，理由：
1. westock-data 的核心价值在于其**全市场聚合统计**，changedist 的数据质量远超样本股估算
2. 现有 basic.py/advanced.py 的特征定义本身就是**横截面比例统计**，完全可以从聚合数据直接计算
3. 实现复杂度更低，维护成本更小

---

## 3. 整体架构设计

### 3.1 模块关系图

```
SentimentConfig (config.py)
    └── ProviderConfig
            └── type: "westock"   ← 新增
            └── WeStockConfig     ← 新增子配置

cli.py
    └── load_market_data(config) → WeStockProvider  ← 路由新增
            └── WeStockProvider.fetch(start, end)
                    ├── _call_changedist(date) → changedist JSON
                    ├── _call_market(code, date1, date2) → market 历史 JSON
                    └── _build_sentiment_df() → pd.DataFrame (market-level行)

新增调用路径（绕过 features/basic.py 和 features/advanced.py）：
cli.py
    └── compute_westock_features(df)   ← 新增
            └── WeStockFeatureCalculator.compute(df)
                    ├── _extract_advance_decline()
                    ├── _extract_limit_stats()
                    ├── _extract_range_features()
                    └── _extract_market_flow()

保留调用路径（复用）：
WeStockFeatureCalculator → pd.DataFrame (同特征列名)
    └── compute_sentiment_score()     ← 完全复用，无需修改
```

### 3.2 新增目录结构

```
src/sentiment_ashare/
├── config.py                      ← 修改：新增 WeStockConfig，ProviderConfig.type 支持 "westock"
├── providers/
│   ├── __init__.py                ← 修改：export WeStockProvider
│   ├── csv_provider.py            ← 不动
│   ├── data_loader.py             ← 修改：新增 westock 分支
│   └── westock_provider.py        ← 新增 ⭐
└── features/
    ├── __init__.py                ← 修改：export compute_westock_features
    ├── basic.py                   ← 不动
    ├── advanced.py                ← 不动
    ├── sentiment_classifier.py    ← 不动
    └── westock_features.py        ← 新增 ⭐
```

---

## 4. 配置类设计（config.py 修改方案）

### 4.1 新增 WeStockConfig

```python
class WeStockConfig(BaseModel):
    """
    westock-data CLI 数据源配置
    """
    cli_path: str = Field(
        default="node /Users/mingzhegao/.workbuddy/skills/westock-data/scripts/index.js",
        description="westock-data CLI 完整调用路径（含 node 前缀）"
    )
    start_date: str = Field(description="开始日期，格式: YYYY-MM-DD")
    end_date: str = Field(description="结束日期，格式: YYYY-MM-DD")
    market: str = Field(default="hs", description="市场代码: 'hs'（沪深）| 'sh' | 'sz'")
    index_codes: list[str] = Field(
        default=["sh000001", "sh000300", "sh000905"],
        description="配套指数代码，用于获取成交额和资金流向"
    )
    timeout_seconds: int = Field(default=30, description="CLI 调用超时秒数")
    retry_count: int = Field(default=3, description="失败重试次数")
    cache_dir: Optional[str] = Field(default=None, description="本地缓存目录，None 表示不缓存")
```

### 4.2 修改 ProviderConfig

```python
class ProviderConfig(BaseModel):
    """
    数据源配置类（修改版）
    """
    type: str = Field(description="provider type: 'csv' | 'download' | 'westock'")  # ← 新增 westock
    path: Optional[str] = Field(default=None, description="CSV provider 路径")
    date_column: str = Field(default="trade_date", description="日期列名")
    symbol_column: str = Field(default="ts_code", description="股票代码列名")
    download: Optional[DownloadConfig] = Field(default=None, description="download provider 配置")
    westock: Optional[WeStockConfig] = Field(default=None, description="westock provider 配置")  # ← 新增
```

### 4.3 示例配置文件

```yaml
# example_westock_config.yaml
provider:
  type: westock
  date_column: trade_date  # 输出 DataFrame 的日期列名（保持统一）
  westock:
    start_date: "2025-01-01"
    end_date: "2026-04-08"
    market: hs
    index_codes:
      - sh000001
      - sh000300
    timeout_seconds: 30
    retry_count: 3
    cache_dir: "./westock_cache"  # 可选：缓存 CLI 结果

weights:
  advance_ratio: 1.2
  limit_up_ratio: 1.5
  limit_down_ratio: 1.5
  limit_net_ratio: 1.3
  advance_decline: 1.0
  limit_up_down: 1.0
  gap_breadth: 0.8
  volume_change_ratio: 0.9

rolling_window: 20
```

---

## 5. WeStockProvider 类设计

### 5.1 文件路径

`src/sentiment_ashare/providers/westock_provider.py`

### 5.2 完整类接口

```python
from __future__ import annotations

import json
import subprocess
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
import pandas as pd

from sentiment_ashare.config import WeStockConfig

logger = logging.getLogger(__name__)


class WeStockProvider:
    """
    基于 westock-data CLI 的市场数据提供者
    
    返回的 DataFrame 包含 market-level 聚合数据（每行一天），
    专供 WeStockFeatureCalculator 使用。
    
    输出 DataFrame Schema:
    +------------------+----------+----------------------------------------------------+
    | 列名             | 类型     | 说明                                               |
    +------------------+----------+----------------------------------------------------+
    | trade_date       | datetime | 交易日期                                           |
    | total_stocks     | int      | 全市场股票总数                                     |
    | advancing        | int      | 上涨股票数量                                       |
    | declining        | int      | 下跌股票数量                                       |
    | unchanged        | int      | 平盘股票数量                                       |
    | limit_up         | int      | 涨停股票数量                                       |
    | limit_down       | int      | 跌停股票数量                                       |
    | range_gt7        | int      | 涨幅 >7% 股票数量（不含涨停）                      |
    | range_5_7        | int      | 涨幅 5%~7% 股票数量                                |
    | range_2_5        | int      | 涨幅 2%~5% 股票数量                                |
    | range_0_2        | int      | 涨幅 0%~2% 股票数量                                |
    | range_n2_0       | int      | 跌幅 0%~-2% 股票数量                               |
    | range_n5_n2      | int      | 跌幅 -2%~-5% 股票数量                              |
    | range_n7_n5      | int      | 跌幅 -5%~-7% 股票数量                              |
    | range_lt_n7      | int      | 跌幅 <-7% 股票数量（不含跌停）                     |
    | index_close      | float    | sh000001 收盘价（NaN 如无数据）                    |
    | index_pct_chg    | float    | sh000001 涨跌幅 %                                  |
    | turnover_value   | float    | sh000001 总成交额（元）                            |
    | main_net_flow    | float    | sh000001 主力资金净流入（元）                      |
    +------------------+----------+----------------------------------------------------+
    
    注意：symbol_column（ts_code）在此提供者中无意义，
    WeStockFeatureCalculator 不需要 symbol_column。
    """
    
    def __init__(self, config: WeStockConfig) -> None:
        """
        初始化 WeStockProvider
        
        Args:
            config: WeStockConfig 配置对象
        """
        ...
    
    def fetch(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取指定日期范围的市场聚合数据
        
        Args:
            start_date: 开始日期 YYYY-MM-DD，None 时使用 config 中的值
            end_date: 结束日期 YYYY-MM-DD，None 时使用 config 中的值
            
        Returns:
            pd.DataFrame: 市场聚合数据，Schema 见类文档
            
        Raises:
            WeStockCLIError: CLI 调用失败（重试后仍失败）
            WeStockParseError: 返回数据格式异常
        """
        ...
    
    def _call_cli(self, *args: str) -> dict:
        """
        调用 westock-data CLI 并解析 JSON 输出
        
        从 stdout 中提取最后一个完整 JSON 对象（CLI 会先打印格式化文本，最后打印 JSON）
        
        Args:
            *args: CLI 参数列表，例如 ("changedist", "hs", "2026-04-07")
            
        Returns:
            dict: 解析后的 JSON 数据（data 字段）
            
        Raises:
            WeStockCLIError: 非零返回码或无 JSON 输出
            WeStockParseError: JSON 解析失败
        """
        ...
    
    def _call_changedist(self, trade_date: str) -> Optional[dict]:
        """
        调用 changedist 命令获取单日涨跌区间数据
        
        Args:
            trade_date: 日期字符串 YYYY-MM-DD
            
        Returns:
            dict | None: changedist data 字段，交易日无数据时返回 None
        """
        ...
    
    def _call_market_range(self, index_code: str, start_date: str, end_date: str) -> list[dict]:
        """
        调用 market 命令获取指数历史区间行情
        
        Args:
            index_code: 指数代码，如 "sh000001"
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            list[dict]: 每日行情列表，字段见 westock market 输出
        """
        ...
    
    def _get_trading_dates(self, start_date: str, end_date: str) -> list[str]:
        """
        生成日期范围内的交易日列表
        
        策略：先生成全部自然日，再通过 market 接口返回的实际日期过滤（以 market 返回为准）
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            list[str]: 实际交易日列表（YYYY-MM-DD 格式）
        """
        ...
    
    def _parse_ranges(self, ranges: list[dict]) -> dict[str, int]:
        """
        解析 changedist.ranges 数组为扁平字段
        
        Args:
            ranges: changedist 返回的 ranges 数组
            
        Returns:
            dict: 包含 range_gt7, range_5_7 等字段的字典
        """
        ...
    
    def _extract_json_from_output(self, stdout: str) -> dict:
        """
        从 CLI stdout 中提取 JSON 数据
        
        CLI 会先输出格式化文本，最后输出 JSON。
        策略：找到最后一个以 '{' 开头的行，向后提取完整 JSON。
        
        Args:
            stdout: CLI 标准输出字符串
            
        Returns:
            dict: 解析后的 JSON
        """
        ...
```

### 5.3 自定义异常类

```python
# 在 westock_provider.py 中定义

class WeStockError(Exception):
    """WeStock 基础异常"""
    pass

class WeStockCLIError(WeStockError):
    """CLI 调用失败"""
    def __init__(self, cmd: str, returncode: int, stderr: str):
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"CLI failed (code={returncode}): {cmd}\n{stderr}")

class WeStockParseError(WeStockError):
    """数据解析失败"""
    pass
```

---

## 6. WeStockFeatureCalculator 设计

### 6.1 文件路径

`src/sentiment_ashare/features/westock_features.py`

### 6.2 特征映射表

| 特征名称 | 权重配置键 | 计算公式 | 来源 API 字段 |
|----------|-----------|----------|--------------|
| `advance_ratio` | `advance_ratio` | `advancing / total_stocks` | changedist.advancing / totalStocks |
| `limit_up_ratio` | `limit_up_ratio` | `limit_up / total_stocks` | changedist.limitUp / totalStocks |
| `limit_down_ratio` | `limit_down_ratio` | `limit_down / total_stocks` | changedist.limitDown / totalStocks |
| `limit_net_ratio` | `limit_net_ratio` | `(limit_up - limit_down) / total_stocks` | changedist.(limitUp-limitDown) / totalStocks |
| `advance_decline` | `advance_decline` | `advancing / (advancing + declining)` | changedist.advancing / (advancing+declining) |
| `limit_up_down` | `limit_up_down` | `limit_up_ratio - limit_down_ratio` | 同 limit_net_ratio |
| `gap_breadth` | `gap_breadth` | `(range_gt7 + limit_up) / total_stocks` | 使用高涨幅区间作为代理 |
| `reversal_breadth` | `reversal_breadth` | 暂时降级：`range_5_7 / total_stocks` | 无法直接计算，用强势区间代理 |
| `turnover_surge` | `turnover_surge` | `turnover_value / MA20_turnover_value`（滚动均值比）| market.turnoverValue |
| `intraday_volatility` | `intraday_volatility` | `index_range_pct`（= (high-low)/open） | market.(highPrice-lowPrice)/openPrice |
| `amount_breadth` | `amount_breadth` | `advance_ratio`（代理，与涨跌比高度相关）| changedist.advancing / totalStocks |
| `volume_change_ratio` | `volume_change_ratio` | `(turnover_value - prev_turnover_value) / prev_turnover_value` | market.turnoverValue 日变化率 |
| `amount_change_ratio` | *(advanced)*  | 同 volume_change_ratio | market.turnoverValue |
| `continuation_stocks` | `continuation_stocks` | `limit_up`（近似：只统计涨停数作为连板代理）| changedist.limitUp |
| `break_board_ratio` | `break_board_ratio` | 暂时降级：`NaN`（CLI无数据）| 无对应数据，输出 NaN |
| `seal_board_ratio` | `seal_board_ratio` | 暂时降级：`NaN`（CLI无数据）| 无对应数据，输出 NaN |
| `heaven_earth_count` | `heaven_earth_count` | 暂时降级：`NaN` | 无对应数据 |
| `abnormal_movement_count` | `abnormal_movement_count` | `range_gt7 + limit_up`（大幅波动计数）| changedist 各区间 |
| `auction_strength` | `auction_strength` | `index_pct_chg`（用指数当日涨跌幅代理开盘强度）| market.changePct |
| `main_net_flow_ratio` | *(新增)*  | `main_net_flow / turnover_value`（主力净流入比例）| market.mainNetFlow / turnoverValue |

**注**：`break_board_ratio`、`seal_board_ratio`、`heaven_earth_count` 返回 NaN，scoring.py 会自动跳过无效特征（已验证代码逻辑）。

### 6.3 compute_westock_features 函数签名

```python
def compute_westock_features(
    df: pd.DataFrame,
    *,
    date_column: str = "trade_date",
    rolling_window: int = 20,
) -> pd.DataFrame:
    """
    从 WeStockProvider 输出的市场聚合 DataFrame 计算情绪特征
    
    与 compute_basic_features / compute_advanced_sentiment_features 的区别：
    - 输入是 market-level 数据（每行一天），不是逐股数据
    - 无需 symbol_column 参数
    - 直接计算比例指标，无需横截面 groupby
    - 涨跌停、区间分布等指标精度更高（全市场覆盖）
    
    Args:
        df: WeStockProvider.fetch() 返回的 DataFrame
        date_column: 日期列名，默认 "trade_date"
        rolling_window: 量能变化率的滚动窗口（默认 20 个交易日）
        
    Returns:
        pd.DataFrame: 每日情绪特征，包含所有 WeightsConfig 对应的特征列。
        列清单（与 WeightsConfig 键名完全对应）：
            基础特征（7个）：
            - advance_decline, limit_up_down, gap_breadth, reversal_breadth
            - turnover_surge, intraday_volatility, amount_breadth
            高级特征（10个，部分为 NaN）：
            - advance_ratio, limit_up_ratio, limit_down_ratio, limit_net_ratio
            - continuation_stocks, volume_change_ratio
            - break_board_ratio (NaN), seal_board_ratio (NaN)
            - heaven_earth_count (NaN), abnormal_movement_count
            - auction_strength
            
    Note:
        NaN 特征不影响 compute_sentiment_score，scoring 会自动跳过
    """
    ...
```

---

## 7. data_loader.py 修改方案

### 7.1 修改位置

在 `load_market_data` 函数中新增 `elif config.type.lower() == "westock":` 分支。

### 7.2 修改后的函数（完整版）

```python
from sentiment_ashare.providers.westock_provider import WeStockProvider

def load_market_data(
    config: ProviderConfig,
    *,
    required_columns: Optional[Sequence[str]] = None,
    universe_filter: Optional[str] = None,
) -> pd.DataFrame:
    if config.type.lower() == "csv":
        # ... 不动
        
    elif config.type.lower() == "download":
        # ... 不动
    
    elif config.type.lower() == "westock":  # ← 新增分支
        if config.westock is None:
            raise ValueError("WeStock provider requires 'westock' config to be specified")
        
        provider = WeStockProvider(config.westock)
        df = provider.fetch()
        
        # westock 数据不支持 universe_filter（market-level 数据无股票维度）
        if universe_filter:
            import warnings
            warnings.warn(
                "universe_filter is not supported for westock provider, ignoring.",
                UserWarning,
                stacklevel=2,
            )
        
        # required_columns 验证（仅验证 market-level 列，不含 symbol_column）
        if required_columns:
            missing = [c for c in required_columns if c not in df.columns]
            if missing:
                import warnings
                warnings.warn(
                    f"WeStock provider missing columns: {missing} (may be unsupported for market-level data)",
                    UserWarning,
                    stacklevel=2,
                )
        
        return df
    
    else:
        raise ValueError(f"Unsupported provider type: {config.type}")
```

---

## 8. cli.py 修改方案

### 8.1 修改 _run_analysis 函数

```python
from sentiment_ashare.features import (
    compute_basic_features, 
    compute_advanced_sentiment_features,
    compute_westock_features,  # ← 新增 import
)

def _run_analysis(config_path: str, output_path: str, advanced: bool = False, analysis: bool = False) -> None:
    cfg = SentimentConfig.load(config_path)
    df = load_market_data(cfg.provider, universe_filter=cfg.universe_filter)
    
    # ← 新增：westock 数据走专用特征计算路径
    if cfg.provider.type.lower() == "westock":
        print("使用 WeStock 市场聚合特征计算...")
        feats = compute_westock_features(
            df,
            date_column=cfg.provider.date_column,
            rolling_window=cfg.rolling_window,
        )
    elif advanced:
        # ... 不动
    else:
        # ... 不动
    
    # 以下 compute_sentiment_score 完全不动
    score = compute_sentiment_score(...)
```

---

## 9. 核心实现逻辑详解

### 9.1 WeStockProvider.fetch() 实现逻辑

```
fetch(start_date, end_date):
  1. 获取交易日历：调用 market sh000001 start_date end_date
     → 提取 data.sh000001.history[].date 作为实际交易日列表
  
  2. 批量获取 changedist：
     for each trade_date in trading_dates:
         row = _call_changedist(trade_date)
         if row is None: 跳过（非交易日）
         else: 解析并追加到 records 列表
  
  3. 获取主指数历史行情：
     market_data = _call_market_range("sh000001", start_date, end_date)
     → 转为以 date 为键的字典
  
  4. 合并数据：
     for each record in records:
         合并对应日期的 market 数据（index_close, turnover_value, main_net_flow 等）
  
  5. 构建 DataFrame 并返回
```

### 9.2 changedist 历史日期的注意事项

**实测发现**：`changedist hs date1 date2` 传入日期区间时，仍只返回**单日**数据（返回的是当前最新日，忽略 date1 参数）。

**解决方案**：逐日调用 `changedist hs {date}`，每次获取单日数据。这意味着获取 N 天数据需要 N 次 CLI 调用。对于常见的 20-250 交易日范围，调用次数为 20-250 次。

**性能优化**：
- 利用缓存目录（`cache_dir`），已获取的日期不重复调用
- 如果 changedist 对历史日期返回当日数据，需要检测并跳过（通过比对 response.date 与请求 date）

**实测验证逻辑（必须在实现时确认）**：
```python
# 验证 changedist 是否支持历史日期
result = _call_cli("changedist", "hs", "2026-01-02")
returned_date = result["date"]  # 检查返回的 date 是否等于 "2026-01-02"
# 如果不等，说明不支持历史查询，需要逐日调用
```

### 9.3 JSON 提取策略

CLI 的 stdout 格式如下：
```
\n════...════\n
  📊 沪深涨跌区间分布
  ...文本格式化...
════...════\n
\n
{"success": true, "data": {...}}
```

提取策略：
```python
def _extract_json_from_output(stdout: str) -> dict:
    # 找最后一个 { 开始的位置
    last_brace = stdout.rfind('\n{')
    if last_brace == -1:
        last_brace = stdout.find('{')
    json_str = stdout[last_brace:].strip()
    return json.loads(json_str)
```

---

## 10. 边界条件处理

### 10.1 节假日 / 非交易日

| 情况 | 处理方式 |
|------|----------|
| 请求的 date 是节假日 | changedist 返回当日数据（最近交易日），通过比对 `response.date != request_date` 检测并跳过 |
| market 范围内含节假日 | market 本身只返回交易日，自动过滤 |
| date 范围内无数据 | 返回空 DataFrame，外层代码需处理 |

### 10.2 API 失败重试

```python
def _call_cli_with_retry(self, *args: str) -> dict:
    last_error = None
    for attempt in range(self.config.retry_count):
        try:
            return self._call_cli(*args)
        except WeStockCLIError as e:
            last_error = e
            wait = 2 ** attempt  # 指数退避：1s, 2s, 4s
            logger.warning(f"CLI attempt {attempt+1} failed, retrying in {wait}s: {e}")
            time.sleep(wait)
    raise last_error
```

### 10.3 部分数据缺失

| 情况 | 处理方式 |
|------|----------|
| changedist 无数据 | 该日所有特征设为 NaN |
| market 无对应日数据 | index_close / turnover_value 等设为 NaN |
| ranges 数组缺少某区间 | 对应 range_xxx 设为 0 |
| main_net_flow 字段不存在 | 设为 NaN |

### 10.4 数据类型保证

```python
# fetch() 返回前的类型清理
df["trade_date"] = pd.to_datetime(df["trade_date"])
int_cols = ["total_stocks", "advancing", "declining", "unchanged", 
            "limit_up", "limit_down", ...]
float_cols = ["index_close", "index_pct_chg", "turnover_value", "main_net_flow"]

for col in int_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
for col in float_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")  # 保留 NaN
```

### 10.5 缓存机制

```
cache_dir/
├── changedist/
│   ├── 2026-01-02.json
│   ├── 2026-01-03.json
│   └── ...
└── market/
    ├── sh000001_2026-01-02_2026-04-08.json
    └── ...
```

缓存逻辑：
1. 对 changedist 按日期缓存单文件
2. 对 market 按 `{code}_{start}_{end}` 缓存
3. 命中缓存时直接读取 JSON，不调用 CLI

---

## 11. WeStockFeatureCalculator 核心计算逻辑

### 11.1 compute_westock_features 完整实现伪代码

```python
def compute_westock_features(df, *, date_column="trade_date", rolling_window=20):
    df = df.copy().sort_values(date_column)
    n = len(df)
    
    total = df["total_stocks"]
    
    # === 基础特征 ===
    
    # advance_decline: 上涨股票占上涨+下跌之和的比例（排除平盘）
    active = df["advancing"] + df["declining"]
    df["advance_decline"] = df["advancing"] / active.replace(0, np.nan)
    
    # limit_up_down: 涨停净占比（正=市场强势）
    df["limit_up_down"] = (df["limit_up"] - df["limit_down"]) / total
    
    # gap_breadth: 使用强势股比例代理（涨停 + >7% 区间）
    df["gap_breadth"] = (df["limit_up"] + df["range_gt7"]) / total
    
    # reversal_breadth: 无原始数据，用弱势区间(-2到-5%)比例代理（反转信号）
    # 注：弱势区间越大，潜在反转机会越多
    df["reversal_breadth"] = df["range_n5_n2"] / total
    
    # turnover_surge: 当日成交额 vs 滚动均值的比率（MA20）
    ma = df["turnover_value"].rolling(window=rolling_window, min_periods=1).mean()
    df["turnover_surge"] = df["turnover_value"] / ma.replace(0, np.nan)
    
    # intraday_volatility: 指数日内波动幅度
    # 需要 market 数据中的 high/low/open，在 fetch 时需补充
    # 如无数据则为 NaN
    
    # amount_breadth: 用 advance_decline 的同质代理
    df["amount_breadth"] = df["advance_decline"]
    
    # === 高级特征 ===
    
    # advance_ratio
    df["advance_ratio"] = df["advancing"] / total
    
    # limit_up_ratio
    df["limit_up_ratio"] = df["limit_up"] / total
    
    # limit_down_ratio
    df["limit_down_ratio"] = df["limit_down"] / total
    
    # limit_net_ratio
    df["limit_net_ratio"] = (df["limit_up"] - df["limit_down"]) / total
    
    # continuation_stocks: 涨停数（近似连板代理）
    df["continuation_stocks"] = df["limit_up"].astype(float)
    
    # volume_change_ratio: 日成交额变化率
    prev = df["turnover_value"].shift(1)
    df["volume_change_ratio"] = (df["turnover_value"] - prev) / prev.replace(0, np.nan)
    
    # break_board_ratio, seal_board_ratio: 无数据，NaN
    df["break_board_ratio"] = np.nan
    df["seal_board_ratio"] = np.nan
    
    # heaven_earth_count: 无数据，NaN
    df["heaven_earth_count"] = np.nan
    
    # abnormal_movement_count: 大幅波动股票数（涨停 + >7% + <-7% + 跌停）
    df["abnormal_movement_count"] = (
        df["limit_up"] + df["range_gt7"] + df["range_lt_n7"] + df["limit_down"]
    ).astype(float)
    
    # auction_strength: 用当日指数涨跌幅代理（集合竞价强度无法直接获取）
    df["auction_strength"] = df["index_pct_chg"] / 100.0  # 转为小数
    
    feature_columns = [
        date_column,
        # 基础特征
        "advance_decline", "limit_up_down", "gap_breadth", "reversal_breadth",
        "turnover_surge", "intraday_volatility", "amount_breadth",
        # 高级特征
        "advance_ratio", "limit_up_ratio", "limit_down_ratio", "limit_net_ratio",
        "continuation_stocks", "volume_change_ratio",
        "break_board_ratio", "seal_board_ratio",
        "heaven_earth_count", "abnormal_movement_count", "auction_strength",
    ]
    
    available = [c for c in feature_columns if c in df.columns]
    return df[available].reset_index(drop=True)
```

---

## 12. market 数据的 intraday_volatility 字段

`market sh000001` 返回的字段包含 `highPrice`、`lowPrice`、`openPrice`，因此：

```python
# 在 WeStockProvider._build_df() 中计算
df["intraday_volatility"] = (
    (market_row["highPrice"] - market_row["lowPrice"]) 
    / market_row["openPrice"].replace(0, np.nan)
)
```

这需要在 `fetch()` 合并 market 数据时同步计算，纳入输出 DataFrame 的字段。

---

## 13. providers/__init__.py 修改

```python
from __future__ import annotations

from .csv_provider import load_csv_data
from .data_loader import load_market_data
from .westock_provider import WeStockProvider  # ← 新增

__all__ = [
    "load_csv_data",
    "load_market_data",
    "WeStockProvider",  # ← 新增
]
```

---

## 14. features/__init__.py 修改

```python
from __future__ import annotations

from .basic import compute_basic_features
from .advanced import compute_advanced_sentiment_features
from .sentiment_classifier import classify_sentiment_state, get_sentiment_analysis
from .westock_features import compute_westock_features  # ← 新增

__all__ = [
    "compute_basic_features",
    "compute_advanced_sentiment_features",
    "classify_sentiment_state",
    "get_sentiment_analysis",
    "compute_westock_features",  # ← 新增
]
```

---

## 15. 实现 Agent 交接清单

### 15.1 需要新建的文件（2个）

#### 文件 1：`src/sentiment_ashare/providers/westock_provider.py`

需要实现的类和方法：
```
WeStockError(Exception)
WeStockCLIError(WeStockError)
WeStockParseError(WeStockError)

WeStockProvider:
  __init__(self, config: WeStockConfig) -> None
  fetch(start_date, end_date) -> pd.DataFrame          # 主入口，返回 Schema 见第5节
  _call_cli(*args) -> dict                              # 调用 CLI，从 stdout 提取 JSON
  _call_cli_with_retry(*args) -> dict                  # 带重试
  _call_changedist(trade_date: str) -> Optional[dict]  # 单日 changedist
  _call_market_range(code, start, end) -> list[dict]   # 指数历史区间
  _get_trading_dates(start, end) -> list[str]          # 从 market 接口获取实际交易日
  _parse_ranges(ranges: list) -> dict                  # 解析 ranges 数组
  _extract_json_from_output(stdout: str) -> dict        # 提取 JSON
  _load_cache(cache_key: str) -> Optional[dict]        # 读缓存
  _save_cache(cache_key: str, data: dict) -> None      # 写缓存
```

**关键实现注意事项**：
1. CLI 命令拼接方式：`["node", cli_path, *args]`（cli_path 含 `node ` 前缀需拆分）
2. stdout 中 JSON 可能以 `\r\n` 分隔，需处理 Windows 换行
3. 必须验证 `changedist` 是否支持历史日期（通过比对 response.date）
4. `turnoverValue` 字段单位是元，`mainNetFlow` 单位也是元

#### 文件 2：`src/sentiment_ashare/features/westock_features.py`

需要实现的函数：
```
compute_westock_features(
    df: pd.DataFrame,
    *,
    date_column: str = "trade_date",
    rolling_window: int = 20,
) -> pd.DataFrame
```

**关键实现注意事项**：
1. 所有除法操作需处理除以 0（用 `.replace(0, np.nan)`）
2. 需要保证输出 DataFrame 的列名与 `WeightsConfig` 的字段名完全一致（参见第6.2节映射表）
3. NaN 特征不需要特殊处理，`compute_sentiment_score` 已有 `used_items` 过滤

### 15.2 需要修改的文件（4个）

| 文件 | 修改类型 | 修改内容 |
|------|---------|---------|
| `src/sentiment_ashare/config.py` | 新增类+修改类 | 新增 `WeStockConfig`；`ProviderConfig` 新增 `westock` 字段 |
| `src/sentiment_ashare/providers/__init__.py` | 新增 export | 导出 `WeStockProvider` |
| `src/sentiment_ashare/providers/data_loader.py` | 新增分支 | `elif westock` 分支 |
| `src/sentiment_ashare/features/__init__.py` | 新增 export | 导出 `compute_westock_features` |
| `src/sentiment_ashare/cli.py` | 新增分支 | `_run_analysis` 中 westock 路径 |

### 15.3 不需要修改的文件

- `features/basic.py`：完全不动
- `features/advanced.py`：完全不动
- `features/sentiment_classifier.py`：完全不动
- `scoring/aggregate.py`：完全不动
- `providers/csv_provider.py`：完全不动
- `config.py` 中的 `WeightsConfig`、`SentimentConfig`：不动

### 15.4 测试验证清单

实现完成后需要验证：

```python
# 1. 基本配置加载测试
from sentiment_ashare.config import SentimentConfig
cfg = SentimentConfig.load("example_westock_config.yaml")
assert cfg.provider.type == "westock"
assert cfg.provider.westock is not None

# 2. Provider 数据获取测试
from sentiment_ashare.providers import WeStockProvider
provider = WeStockProvider(cfg.provider.westock)
df = provider.fetch("2026-03-01", "2026-04-07")
assert "trade_date" in df.columns
assert "advancing" in df.columns
assert "limit_up" in df.columns
assert len(df) > 0

# 3. 特征计算测试
from sentiment_ashare.features import compute_westock_features
feats = compute_westock_features(df)
assert "advance_ratio" in feats.columns
assert "limit_up_ratio" in feats.columns
assert "advance_decline" in feats.columns

# 4. 评分计算测试（复用现有）
from sentiment_ashare.scoring import compute_sentiment_score
score = compute_sentiment_score(
    feats,
    weights=cfg.weights,
    rolling_window=cfg.rolling_window,
    date_column="trade_date",
)
assert "sentiment_score" in score.columns
assert not score["sentiment_score"].isna().all()
```

---

## 16. 潜在风险与降级策略

### 风险1：changedist 不支持历史日期查询

**风险说明**：实测中传入历史日期时仍返回当日数据。如此一来，获取 250 天历史数据需 250 次 CLI 调用，耗时约 3-5 分钟。

**降级策略**：
- 强制使用缓存（设置 `cache_dir`），首次运行慢，后续增量更新
- 提供 `--westock-prefetch` 命令行选项，预先批量下载历史数据

### 风险2：CLI 路径硬编码

**风险说明**：`cli_path` 默认值包含绝对路径，跨机器不可用。

**降级策略**：
- 支持通过环境变量 `WESTOCK_CLI_PATH` 覆盖
- 在 `WeStockConfig` 中，`cli_path` 为可选，实现时需搜索 PATH 中的 `westock-data`

### 风险3：部分特征退化

**风险说明**：`gap_breadth`（跳空广度）、`reversal_breadth`（日内反转）、`break_board_ratio`（破板率）等特征无法从聚合数据精确计算，只能降级为代理指标或 NaN。

**影响评估**：这些特征对应的权重合计约占总权重的 20%，降级不影响核心情绪判断，但会降低精度。

**降级策略**：
- 在 `WeightsConfig` 中，可通过配置将退化特征的权重设为 0 来禁用
- 长期方案：如 westock-data 增加日内数据接口，可直接接入

### 风险4：量能指标代理精度

**风险说明**：`turnover_surge` 和 `volume_change_ratio` 使用指数成交额代理全市场量能，上证指数仅覆盖上市公司，与全市场成交可能有偏差。

**降级策略**：使用 `sh000001 + sh000300 + sh000905` 三指数成交额加权求和，提升代表性。

---

## 17. 整体调用流程总结

```
用户执行: sentiment_ashare analyze example_westock_config.yaml --output result.csv

→ cli.py: _run_analysis()
→ SentimentConfig.load() 加载配置，provider.type == "westock"
→ load_market_data(cfg.provider)
→ WeStockProvider(cfg.provider.westock).fetch(start, end)
    → 逐日调用 changedist hs {date} → 全市场涨跌停分布
    → 调用 market sh000001 {start} {end} → 指数历史行情
    → 合并数据 → 返回 market-level DataFrame
→ compute_westock_features(df)
    → 直接从聚合数据计算比例特征
    → 返回特征 DataFrame（列名匹配 WeightsConfig）
→ compute_sentiment_score(feats, weights=cfg.weights, ...)
    → 滚动 Z-score 标准化
    → 加权求和
    → classify_sentiment_state
    → 返回含 sentiment_score 的 DataFrame
→ 保存为 result.csv
```

---

*设计文档完。实现 Agent 可直接照此实现，如有疑问请参考各节中的详细说明。*
