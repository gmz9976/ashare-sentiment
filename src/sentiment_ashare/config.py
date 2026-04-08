from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, ValidationError


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
        default_factory=lambda: ["sh000001", "sh000300", "sh000905"],
        description="配套指数代码，用于获取成交额和资金流向"
    )
    timeout_seconds: int = Field(default=30, description="CLI 调用超时秒数")
    retry_count: int = Field(default=3, description="失败重试次数")
    cache_dir: Optional[str] = Field(default=None, description="本地缓存目录，None 表示不缓存")


class DownloadConfig(BaseModel):
    """
    数据下载配置类
    
    用于配置从开源数据源下载数据的相关参数。
    """
    source: str = Field(default="akshare", description="数据源类型: 'akshare' 或 'tushare'")
    start_date: str = Field(description="开始日期，格式: YYYY-MM-DD")
    end_date: str = Field(description="结束日期，格式: YYYY-MM-DD")
    output_dir: str = Field(default="./data", description="数据保存目录")
    stock_list: Optional[list[str]] = Field(default=None, description="指定股票代码列表，None表示下载所有A股")
    token: Optional[str] = Field(default=None, description="tushare token（仅tushare需要）")


class ProviderConfig(BaseModel):
    """
    数据源配置类
    
    用于配置数据提供者的相关参数，包括数据源类型、路径、列名等。
    支持CSV格式的数据源和数据下载功能。
    """
    type: str = Field(description="provider type: 'csv' | 'download' | 'westock'")
    path: Optional[str] = Field(default=None, description="data file or directory path for CSV provider")
    date_column: str = Field(default="trade_date", description="date column name in source data")
    symbol_column: str = Field(default="ts_code", description="symbol column name in source data")
    download: Optional[DownloadConfig] = Field(default=None, description="数据下载配置（当type为download时使用）")
    westock: Optional[WeStockConfig] = Field(default=None, description="westock provider 配置")


class WeightsConfig(BaseModel):
    """
    特征权重配置类
    
    定义各个情绪特征在最终评分中的权重。权重越高，该特征对最终情绪得分的影响越大。
    默认权重基于特征的重要性和稳定性进行设置。
    """
    # 基础特征权重
    advance_decline: float = 1.0  # 涨跌比权重
    limit_up_down: float = 1.0    # 涨跌停净比权重
    gap_breadth: float = 0.8      # 跳空广度权重
    reversal_breadth: float = 0.8 # 反转广度权重
    turnover_surge: float = 0.8   # 成交量激增权重
    intraday_volatility: float = 0.6  # 日内波动率权重
    amount_breadth: float = 0.6   # 成交金额广度权重
    
    # 高级特征权重
    advance_ratio: float = 1.2    # 上涨比例权重
    limit_up_ratio: float = 1.5   # 涨停比例权重
    limit_down_ratio: float = 1.5 # 跌停比例权重
    limit_net_ratio: float = 1.3  # 涨跌停净比权重
    continuation_stocks: float = 1.0  # 连板股票数量权重
    break_board_ratio: float = 0.8    # 破板率权重
    seal_board_ratio: float = 0.8     # 封板率权重
    volume_change_ratio: float = 0.9  # 量能变化权重
    heaven_earth_count: float = 1.2   # 地天板数量权重
    abnormal_movement_count: float = 0.7  # 异动股票数量权重
    auction_strength: float = 0.6     # 集合竞价强度权重


class SentimentConfig(BaseModel):
    """
    情绪评分主配置类
    
    整合数据源配置、特征权重配置和其他运行参数，是整个情绪评分系统的核心配置。
    """
    provider: ProviderConfig  # 数据源配置
    weights: WeightsConfig = Field(default_factory=WeightsConfig)  # 特征权重配置
    rolling_window: int = Field(default=20, ge=5, description="rolling window days for normalization")  # 滚动窗口大小
    universe_filter: Optional[str] = Field(default=None, description="optional expression to filter universe")  # 股票池过滤条件

    @staticmethod
    def load(path: str | Path) -> "SentimentConfig":
        """
        从YAML配置文件加载配置
        
        Args:
            path: YAML配置文件路径
            
        Returns:
            SentimentConfig: 解析后的配置对象
            
        Raises:
            ValueError: 配置文件格式错误或验证失败
        """
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        try:
            return SentimentConfig.model_validate(data)
        except ValidationError as e:
            raise ValueError(f"Invalid config: {e}")
