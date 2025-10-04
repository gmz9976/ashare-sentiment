from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

import pandas as pd


def _read_one_csv(file_path: Path) -> pd.DataFrame:
    """
    读取单个CSV文件的内部辅助函数
    
    Args:
        file_path: CSV文件路径
        
    Returns:
        pd.DataFrame: 读取的数据框
    """
    return pd.read_csv(file_path)


def load_csv_data(
    path: str | Path,
    *,
    date_column: str = "trade_date",
    symbol_column: str = "ts_code",
    required_columns: Optional[Sequence[str]] = None,
    universe_filter: Optional[str] = None,
) -> pd.DataFrame:
    """
    从CSV文件或目录加载A股市场数据
    
    支持从单个CSV文件或包含多个CSV文件的目录加载数据，并进行必要的数据验证和预处理。
    
    Args:
        path: CSV文件路径或包含CSV文件的目录路径
        date_column: 日期列名，默认为"trade_date"
        symbol_column: 股票代码列名，默认为"ts_code"
        required_columns: 必需列名列表，用于验证数据完整性
        universe_filter: pandas查询表达式，用于过滤股票池
        
    Returns:
        pd.DataFrame: 加载并预处理后的市场数据
        
    Raises:
        ValueError: 当路径不存在、缺少必需列或过滤表达式无效时抛出
    """
    p = Path(path)
    if p.is_dir():
        csv_files = sorted(p.glob("*.csv"))
        if not csv_files:
            raise ValueError(f"No CSV files found in directory: {p}")
        frames = [_read_one_csv(f) for f in csv_files]
        df = pd.concat(frames, ignore_index=True)
    elif p.is_file():
        df = _read_one_csv(p)
    else:
        raise ValueError(f"Path not found: {p}")

    if date_column not in df.columns or symbol_column not in df.columns:
        raise ValueError(
            f"Input data must contain columns '{date_column}' and '{symbol_column}'."
        )

    # Normalize date column to datetime
    df[date_column] = pd.to_datetime(df[date_column])

    if universe_filter:
        try:
            df = df.query(universe_filter)
        except Exception as exc:
            raise ValueError(f"Invalid universe_filter expression: {universe_filter}") from exc

    if required_columns:
        missing = [c for c in required_columns if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

    return df


