"""
回测数据管理器

负责加载和管理回测所需的各种数据，包括市场数据、指数数据、情绪数据等。
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

try:
    import akshare as ak
except ImportError:
    ak = None

from sentiment_ashare.config import SentimentConfig
from sentiment_ashare.providers import load_market_data
from sentiment_ashare.features import compute_basic_features, compute_advanced_sentiment_features
from sentiment_ashare.scoring import compute_sentiment_score


class DataManager:
    """
    回测数据管理器
    
    负责加载和管理回测所需的各种数据，包括：
    - 市场数据（股票价格、成交量等）
    - 指数数据（上证、深证、中证等主要指数）
    - 情绪数据（情绪得分、情绪状态等）
    - 数据时间序列对齐
    """
    
    def __init__(self, config: SentimentConfig):
        """
        初始化数据管理器
        
        Args:
            config: 情绪评分配置对象
        """
        self.config = config
        self.market_data: Optional[pd.DataFrame] = None
        self.index_data: Dict[str, pd.DataFrame] = {}
        self.sentiment_data: Optional[pd.DataFrame] = None
        self.aligned_data: Optional[Tuple[pd.DataFrame, Dict[str, pd.DataFrame], pd.DataFrame]] = None
        
    def load_market_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        加载市场数据
        
        Args:
            start_date: 开始日期，格式为'YYYY-MM-DD'
            end_date: 结束日期，格式为'YYYY-MM-DD'
            
        Returns:
            pd.DataFrame: 包含市场数据的DataFrame
        """
        print(f"加载市场数据: {start_date} 到 {end_date}")
        
        # 使用现有的数据加载逻辑
        df = load_market_data(
            self.config.provider,
            universe_filter=self.config.universe_filter,
        )
        
        # 过滤日期范围
        if self.config.provider.date_column in df.columns:
            df[self.config.provider.date_column] = pd.to_datetime(df[self.config.provider.date_column])
            df = df[(df[self.config.provider.date_column] >= start_date) & 
                   (df[self.config.provider.date_column] <= end_date)]
        
        self.market_data = df
        print(f"市场数据加载完成，共 {len(df)} 条记录")
        return df
        
    def load_index_data(self, start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
        """
        加载指数数据
        
        Args:
            start_date: 开始日期，格式为'YYYY-MM-DD'
            end_date: 结束日期，格式为'YYYY-MM-DD'
            
        Returns:
            Dict[str, pd.DataFrame]: 指数数据字典，键为指数代码，值为价格数据
        """
        if ak is None:
            raise ImportError("akshare is required for index data downloading. Install it with: pip install akshare")
            
        print(f"加载指数数据: {start_date} 到 {end_date}")
        
        # 主要指数配置
        indices = {
            'sh000001': '上证指数',
            'sz399001': '深证成指', 
            'sh000300': '沪深300',
            'sh000905': '中证500',
            'sz399006': '创业板指'
        }
        
        index_data = {}
        
        for index_code, index_name in indices.items():
            try:
                print(f"  下载 {index_name} ({index_code}) 数据...")
                
                # 使用akshare下载指数数据
                df = ak.stock_zh_index_daily(symbol=index_code)
                
                if not df.empty:
                    # 标准化列名
                    df = df.rename(columns={
                        'date': 'trade_date',
                        'close': 'close',
                        'open': 'open',
                        'high': 'high',
                        'low': 'low',
                        'volume': 'vol',
                        'amount': 'amount',
                        'pctChg': 'pct_chg'
                    })
                    
                    # 过滤日期范围
                    df['trade_date'] = pd.to_datetime(df['trade_date'])
                    df = df[(df['trade_date'] >= start_date) & 
                           (df['trade_date'] <= end_date)]
                    
                    if not df.empty:
                        index_data[index_code] = df
                        print(f"    {index_name}: {len(df)} 条记录")
                    else:
                        print(f"    {index_name}: 无数据")
                else:
                    print(f"    {index_name}: 下载失败")
                    
            except Exception as e:
                print(f"    {index_name}: 下载失败 - {e}")
                
        self.index_data = index_data
        print(f"指数数据加载完成，共 {len(index_data)} 个指数")
        return index_data
        
    def load_sentiment_data(self, start_date: str, end_date: str, 
                          advanced: bool = True) -> pd.DataFrame:
        """
        加载情绪数据
        
        Args:
            start_date: 开始日期，格式为'YYYY-MM-DD'
            end_date: 结束日期，格式为'YYYY-MM-DD'
            advanced: 是否使用高级特征
            
        Returns:
            pd.DataFrame: 包含情绪数据的DataFrame
        """
        print(f"计算情绪数据: {start_date} 到 {end_date}")
        
        if self.market_data is None:
            self.load_market_data(start_date, end_date)
            
        # 计算情绪特征
        if advanced:
            print("使用高级情绪特征计算...")
            features = compute_advanced_sentiment_features(
                self.market_data,
                date_column=self.config.provider.date_column,
                symbol_column=self.config.provider.symbol_column,
            )
        else:
            print("使用基础情绪特征计算...")
            features = compute_basic_features(
                self.market_data,
                date_column=self.config.provider.date_column,
                symbol_column=self.config.provider.symbol_column,
            )
        
        # 计算情绪得分
        sentiment_score = compute_sentiment_score(
            features,
            weights=self.config.weights,
            rolling_window=self.config.rolling_window,
            date_column=self.config.provider.date_column,
            enable_classification=True,
        )
        
        self.sentiment_data = sentiment_score
        print(f"情绪数据计算完成，共 {len(sentiment_score)} 条记录")
        return sentiment_score
        
    def align_data(self) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame], pd.DataFrame]:
        """
        对齐所有数据的时间序列
        
        Returns:
            Tuple[pd.DataFrame, Dict[str, pd.DataFrame], pd.DataFrame]: 
            对齐后的(市场数据, 指数数据字典, 情绪数据)
        """
        print("对齐数据时间序列...")
        
        if self.market_data is None or self.sentiment_data is None:
            raise ValueError("请先加载市场数据和情绪数据")
            
        # 获取情绪数据的时间范围
        sentiment_dates = pd.to_datetime(self.sentiment_data[self.config.provider.date_column])
        min_date = sentiment_dates.min()
        max_date = sentiment_dates.max()
        
        # 对齐市场数据
        aligned_market_data = self.market_data.copy()
        aligned_market_data[self.config.provider.date_column] = pd.to_datetime(aligned_market_data[self.config.provider.date_column])
        aligned_market_data = aligned_market_data[
            (aligned_market_data[self.config.provider.date_column] >= min_date) &
            (aligned_market_data[self.config.provider.date_column] <= max_date)
        ]
        
        # 对齐指数数据
        aligned_index_data = {}
        for index_code, index_df in self.index_data.items():
            aligned_df = index_df.copy()
            aligned_df['trade_date'] = pd.to_datetime(aligned_df['trade_date'])
            aligned_df = aligned_df[
                (aligned_df['trade_date'] >= min_date) &
                (aligned_df['trade_date'] <= max_date)
            ]
            if not aligned_df.empty:
                aligned_index_data[index_code] = aligned_df
        
        # 对齐情绪数据
        aligned_sentiment_data = self.sentiment_data.copy()
        aligned_sentiment_data[self.config.provider.date_column] = pd.to_datetime(aligned_sentiment_data[self.config.provider.date_column])
        
        self.aligned_data = (aligned_market_data, aligned_index_data, aligned_sentiment_data)
        print(f"数据对齐完成，时间范围: {min_date.date()} 到 {max_date.date()}")
        
        return self.aligned_data
        
    def get_index_returns(self, index_code: str) -> pd.Series:
        """
        获取指定指数的收益率序列
        
        Args:
            index_code: 指数代码
            
        Returns:
            pd.Series: 收益率序列
        """
        if not self.aligned_data:
            raise ValueError("请先对齐数据")
            
        _, aligned_index_data, _ = self.aligned_data
        
        if index_code not in aligned_index_data:
            raise ValueError(f"未找到指数数据: {index_code}")
            
        index_df = aligned_index_data[index_code]
        returns = index_df.set_index('trade_date')['close'].pct_change().dropna()
        
        return returns
        
    def get_market_returns(self) -> pd.Series:
        """
        获取市场整体收益率序列（使用所有股票的等权重平均）
        
        Returns:
            pd.Series: 市场收益率序列
        """
        if not self.aligned_data:
            raise ValueError("请先对齐数据")
            
        aligned_market_data, _, _ = self.aligned_data
        
        # 计算每日市场收益率（等权重平均）
        daily_returns = []
        
        for date in aligned_market_data[self.config.provider.date_column].unique():
            date_data = aligned_market_data[
                aligned_market_data[self.config.provider.date_column] == date
            ]
            
            if 'pct_chg' in date_data.columns:
                # 使用涨跌幅数据
                daily_return = date_data['pct_chg'].mean()
            elif all(col in date_data.columns for col in ['close', 'prev_close']):
                # 计算收益率
                daily_return = ((date_data['close'] / date_data['prev_close']) - 1).mean()
            else:
                continue
                
            daily_returns.append({
                self.config.provider.date_column: date,
                'market_return': daily_return
            })
        
        market_returns_df = pd.DataFrame(daily_returns)
        market_returns_df[self.config.provider.date_column] = pd.to_datetime(market_returns_df[self.config.provider.date_column])
        market_returns = market_returns_df.set_index(self.config.provider.date_column)['market_return']
        
        return market_returns
        
    def get_sentiment_series(self) -> pd.DataFrame:
        """
        获取情绪数据序列
        
        Returns:
            pd.DataFrame: 情绪数据DataFrame
        """
        if not self.aligned_data:
            raise ValueError("请先对齐数据")
            
        _, _, aligned_sentiment_data = self.aligned_data
        
        sentiment_df = aligned_sentiment_data.copy()
        sentiment_df[self.config.provider.date_column] = pd.to_datetime(sentiment_df[self.config.provider.date_column])
        sentiment_df = sentiment_df.set_index(self.config.provider.date_column)
        
        return sentiment_df
