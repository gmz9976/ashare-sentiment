from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

import pandas as pd

from sentiment_ashare.config import ProviderConfig
from sentiment_ashare.downloaders import download_akshare_data, download_tushare_data
from .csv_provider import load_csv_data


def load_market_data(
    config: ProviderConfig,
    *,
    required_columns: Optional[Sequence[str]] = None,
    universe_filter: Optional[str] = None,
) -> pd.DataFrame:
    """
    根据配置加载市场数据
    
    支持从CSV文件加载或从开源数据源下载数据。
    
    Args:
        config: 数据源配置对象
        required_columns: 必需列名列表，用于验证数据完整性
        universe_filter: pandas查询表达式，用于过滤股票池
        
    Returns:
        pd.DataFrame: 加载并预处理后的市场数据
        
    Raises:
        ValueError: 当配置无效或数据加载失败时抛出
    """
    if config.type.lower() == "csv":
        # 从CSV文件加载数据
        if config.path is None:
            raise ValueError("CSV provider requires 'path' to be specified")
        
        return load_csv_data(
            config.path,
            date_column=config.date_column,
            symbol_column=config.symbol_column,
            required_columns=required_columns,
            universe_filter=universe_filter,
        )
    
    elif config.type.lower() == "download":
        # 从开源数据源下载数据
        if config.download is None:
            raise ValueError("Download provider requires 'download' config to be specified")
        
        download_config = config.download
        
        # 下载数据
        if download_config.source.lower() == "akshare":
            data_path = download_akshare_data(
                start_date=download_config.start_date,
                end_date=download_config.end_date,
                output_dir=download_config.output_dir,
                stock_list=download_config.stock_list,
            )
        elif download_config.source.lower() == "tushare":
            data_path = download_tushare_data(
                start_date=download_config.start_date,
                end_date=download_config.end_date,
                output_dir=download_config.output_dir,
                token=download_config.token,
                stock_list=download_config.stock_list,
            )
        else:
            raise ValueError(f"Unsupported download source: {download_config.source}")
        
        # 加载下载的数据
        return load_csv_data(
            data_path,
            date_column=config.date_column,
            symbol_column=config.symbol_column,
            required_columns=required_columns,
            universe_filter=universe_filter,
        )
    
    elif config.type.lower() == "westock":
        from sentiment_ashare.providers.westock_provider import WeStockProvider
        
        if config.westock is None:
            raise ValueError("WeStock provider requires 'westock' config to be specified")
        
        provider = WeStockProvider(config.westock)
        df = provider.fetch()
        
        # westock 返回 market-level 数据，不支持 universe_filter
        if universe_filter:
            import warnings
            warnings.warn(
                "universe_filter is not supported for westock provider, ignoring.",
                UserWarning,
                stacklevel=2,
            )
        
        # 宽松验证：仅警告（market-level 无 symbol_column 等逐股列）
        if required_columns:
            missing = [c for c in required_columns if c not in df.columns]
            if missing:
                import warnings
                warnings.warn(
                    f"WeStock provider missing columns: {missing} "
                    "(may be unsupported for market-level data)",
                    UserWarning,
                    stacklevel=2,
                )
        
        return df
    
    else:
        raise ValueError(f"Unsupported provider type: {config.type}")
