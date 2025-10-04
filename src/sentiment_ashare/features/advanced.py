from __future__ import annotations

from typing import Sequence, Optional, Dict, Any
import warnings

import numpy as np
import pandas as pd


def compute_advanced_sentiment_features(
    df: pd.DataFrame,
    *,
    date_column: str,
    symbol_column: str,
    price_columns: Sequence[str] = ("open", "high", "low", "close"),
    turnover_column: str = "amount",
    volume_column: str = "vol",
) -> pd.DataFrame:
    """
    计算高级市场情绪特征
    
    基于每日市场数据计算详细的市场情绪指标，包括涨跌停、连板高度、
    破板率、量能变化、地天板等关键情绪指标。
    
    Args:
        df: 包含市场数据的DataFrame
        date_column: 日期列名
        symbol_column: 股票代码列名
        price_columns: 价格相关列名
        turnover_column: 成交金额列名
        volume_column: 成交量列名
        
    Returns:
        pd.DataFrame: 包含每日高级情绪特征的DataFrame
    """
    required = set([date_column, symbol_column])
    missing_base = [c for c in required if c not in df.columns]
    if missing_base:
        raise ValueError(f"Missing base columns: {missing_base}")

    data = df.copy()
    data = data.sort_values([date_column, symbol_column])
    
    # 准备前一日数据用于计算
    if "close" in data.columns:
        data["prev_close"] = data.groupby(symbol_column)["close"].shift(1)
    if volume_column in data.columns:
        data["prev_vol"] = data.groupby(symbol_column)[volume_column].shift(1)
    if turnover_column in data.columns:
        data["prev_amount"] = data.groupby(symbol_column)[turnover_column].shift(1)

    def _daily_advanced_features(group: pd.DataFrame) -> pd.Series:
        features: Dict[str, float] = {}
        n = len(group)
        if n == 0:
            return _get_empty_features()
        
        # 1. 基础涨跌统计
        features.update(_compute_basic_stats(group))
        
        # 2. 涨跌停统计
        features.update(_compute_limit_stats(group))
        
        # 3. 连板高度分析
        features.update(_compute_continuation_stats(group))
        
        # 4. 破板率、封板率
        features.update(_compute_board_stats(group))
        
        # 5. 昨日打板表现
        features.update(_compute_yesterday_board_performance(group))
        
        # 6. 高位、中位股票表现
        features.update(_compute_position_performance(group))
        
        # 7. 量能变化
        features.update(_compute_volume_changes(group))
        
        # 8. 地天板统计
        features.update(_compute_heaven_earth_boards(group))
        
        # 9. 异动股票统计
        features.update(_compute_abnormal_movement(group))
        
        # 10. 集合竞价分析
        features.update(_compute_auction_analysis(group))
        
        return pd.Series(features)

    daily = data.groupby(date_column).apply(_daily_advanced_features).reset_index()
    return daily


def _get_empty_features() -> pd.Series:
    """返回空特征字典"""
    return pd.Series({
        # 基础统计
        "advance_count": np.nan,
        "decline_count": np.nan,
        "advance_ratio": np.nan,
        "decline_ratio": np.nan,
        
        # 涨跌停统计
        "limit_up_count": np.nan,
        "limit_down_count": np.nan,
        "limit_up_ratio": np.nan,
        "limit_down_ratio": np.nan,
        "limit_net_ratio": np.nan,
        
        # 连板高度
        "max_continuation": np.nan,
        "avg_continuation": np.nan,
        "continuation_stocks": np.nan,
        
        # 破板率
        "break_board_ratio": np.nan,
        "seal_board_ratio": np.nan,
        
        # 昨日打板表现
        "yesterday_first_board_performance": np.nan,
        "yesterday_high_board_performance": np.nan,
        "high_low_switch": np.nan,
        
        # 高位中位表现
        "high_position_performance": np.nan,
        "mid_position_performance": np.nan,
        
        # 量能变化
        "volume_change_ratio": np.nan,
        "amount_change_ratio": np.nan,
        
        # 地天板
        "heaven_earth_count": np.nan,
        "heaven_earth_premium": np.nan,
        
        # 异动股票
        "abnormal_movement_count": np.nan,
        "challenge_regulation": np.nan,
        
        # 集合竞价
        "auction_strength": np.nan,
        "auction_volume_change": np.nan,
    })


def _compute_basic_stats(group: pd.DataFrame) -> Dict[str, float]:
    """计算基础涨跌统计"""
    features = {}
    
    if "pct_chg" in group.columns:
        advance_mask = group["pct_chg"] > 0
        decline_mask = group["pct_chg"] < 0
        
        features["advance_count"] = float(advance_mask.sum())
        features["decline_count"] = float(decline_mask.sum())
        features["advance_ratio"] = float(advance_mask.mean())
        features["decline_ratio"] = float(decline_mask.mean())
    else:
        features.update({
            "advance_count": np.nan,
            "decline_count": np.nan,
            "advance_ratio": np.nan,
            "decline_ratio": np.nan,
        })
    
    return features


def _compute_limit_stats(group: pd.DataFrame) -> Dict[str, float]:
    """计算涨跌停统计"""
    features = {}
    
    if "pct_chg" in group.columns:
        limit_up_mask = group["pct_chg"] >= 9.8
        limit_down_mask = group["pct_chg"] <= -9.8
        
        features["limit_up_count"] = float(limit_up_mask.sum())
        features["limit_down_count"] = float(limit_down_mask.sum())
        features["limit_up_ratio"] = float(limit_up_mask.mean())
        features["limit_down_ratio"] = float(limit_down_mask.mean())
        features["limit_net_ratio"] = float(limit_up_mask.mean() - limit_down_mask.mean())
    else:
        features.update({
            "limit_up_count": np.nan,
            "limit_down_count": np.nan,
            "limit_up_ratio": np.nan,
            "limit_down_ratio": np.nan,
            "limit_net_ratio": np.nan,
        })
    
    return features


def _compute_continuation_stats(group: pd.DataFrame) -> Dict[str, float]:
    """计算连板高度统计"""
    features = {}
    
    # 这里需要连板数据，暂时用涨跌幅模拟
    if "pct_chg" in group.columns:
        # 简化版：连续涨停的股票数量
        continuation_mask = group["pct_chg"] >= 9.8
        features["continuation_stocks"] = float(continuation_mask.sum())
        features["max_continuation"] = float(continuation_mask.sum())  # 简化
        features["avg_continuation"] = float(continuation_mask.mean())
    else:
        features.update({
            "max_continuation": np.nan,
            "avg_continuation": np.nan,
            "continuation_stocks": np.nan,
        })
    
    return features


def _compute_board_stats(group: pd.DataFrame) -> Dict[str, float]:
    """计算破板率、封板率"""
    features = {}
    
    if "pct_chg" in group.columns and "high" in group.columns and "close" in group.columns:
        # 简化版：涨停但未封板的股票比例
        limit_up_mask = group["pct_chg"] >= 9.8
        not_sealed_mask = (group["high"] > group["close"]) & limit_up_mask
        
        if limit_up_mask.sum() > 0:
            features["break_board_ratio"] = float(not_sealed_mask.sum() / limit_up_mask.sum())
            features["seal_board_ratio"] = float(1 - not_sealed_mask.sum() / limit_up_mask.sum())
        else:
            features["break_board_ratio"] = 0.0
            features["seal_board_ratio"] = 0.0
    else:
        features.update({
            "break_board_ratio": np.nan,
            "seal_board_ratio": np.nan,
        })
    
    return features


def _compute_yesterday_board_performance(group: pd.DataFrame) -> Dict[str, float]:
    """计算昨日打板表现"""
    features = {}
    
    # 这里需要前一日数据，暂时用当前数据模拟
    if "pct_chg" in group.columns:
        # 简化版：当前涨停股票的表现
        limit_up_mask = group["pct_chg"] >= 9.8
        if limit_up_mask.sum() > 0:
            features["yesterday_first_board_performance"] = float(limit_up_mask.mean())
            features["yesterday_high_board_performance"] = float(limit_up_mask.mean())
            features["high_low_switch"] = 0.0  # 简化
        else:
            features.update({
                "yesterday_first_board_performance": 0.0,
                "yesterday_high_board_performance": 0.0,
                "high_low_switch": 0.0,
            })
    else:
        features.update({
            "yesterday_first_board_performance": np.nan,
            "yesterday_high_board_performance": np.nan,
            "high_low_switch": np.nan,
        })
    
    return features


def _compute_position_performance(group: pd.DataFrame) -> Dict[str, float]:
    """计算高位、中位股票表现"""
    features = {}
    
    if "pct_chg" in group.columns:
        # 简化版：按涨跌幅分位
        pct_chg = group["pct_chg"].dropna()
        if len(pct_chg) > 0:
            high_threshold = pct_chg.quantile(0.8)  # 前20%
            mid_threshold = pct_chg.quantile(0.4)   # 中间40%
            
            high_mask = group["pct_chg"] >= high_threshold
            mid_mask = (group["pct_chg"] >= mid_threshold) & (group["pct_chg"] < high_threshold)
            
            features["high_position_performance"] = float(high_mask.mean())
            features["mid_position_performance"] = float(mid_mask.mean())
        else:
            features.update({
                "high_position_performance": np.nan,
                "mid_position_performance": np.nan,
            })
    else:
        features.update({
            "high_position_performance": np.nan,
            "mid_position_performance": np.nan,
        })
    
    return features


def _compute_volume_changes(group: pd.DataFrame) -> Dict[str, float]:
    """计算量能变化"""
    features = {}
    
    if "vol" in group.columns and "prev_vol" in group.columns:
        vol_change = (group["vol"] - group["prev_vol"]) / group["prev_vol"].replace(0, np.nan)
        features["volume_change_ratio"] = float(vol_change.median())
    else:
        features["volume_change_ratio"] = np.nan
    
    if "amount" in group.columns and "prev_amount" in group.columns:
        amount_change = (group["amount"] - group["prev_amount"]) / group["prev_amount"].replace(0, np.nan)
        features["amount_change_ratio"] = float(amount_change.median())
    else:
        features["amount_change_ratio"] = np.nan
    
    return features


def _compute_heaven_earth_boards(group: pd.DataFrame) -> Dict[str, float]:
    """计算地天板统计"""
    features = {}
    
    if "pct_chg" in group.columns and "low" in group.columns and "high" in group.columns:
        # 地天板：从跌停到涨停
        heaven_earth_mask = (group["low"] <= group["low"] * 0.9) & (group["pct_chg"] >= 9.8)
        features["heaven_earth_count"] = float(heaven_earth_mask.sum())
        
        if heaven_earth_mask.sum() > 0:
            features["heaven_earth_premium"] = float(group[heaven_earth_mask]["pct_chg"].mean())
        else:
            features["heaven_earth_premium"] = 0.0
    else:
        features.update({
            "heaven_earth_count": np.nan,
            "heaven_earth_premium": np.nan,
        })
    
    return features


def _compute_abnormal_movement(group: pd.DataFrame) -> Dict[str, float]:
    """计算异动股票统计"""
    features = {}
    
    if "pct_chg" in group.columns and "amount" in group.columns:
        # 异动：涨跌幅超过7%且成交额异常
        abnormal_mask = (abs(group["pct_chg"]) >= 7.0) & (group["amount"] > group["amount"].quantile(0.8))
        features["abnormal_movement_count"] = float(abnormal_mask.sum())
        
        # 挑战监管：连续异动
        features["challenge_regulation"] = 0.0  # 简化
    else:
        features.update({
            "abnormal_movement_count": np.nan,
            "challenge_regulation": np.nan,
        })
    
    return features


def _compute_auction_analysis(group: pd.DataFrame) -> Dict[str, float]:
    """计算集合竞价分析"""
    features = {}
    
    if "open" in group.columns and "prev_close" in group.columns and "amount" in group.columns:
        # 集合竞价强度：开盘涨幅
        auction_strength = (group["open"] - group["prev_close"]) / group["prev_close"]
        features["auction_strength"] = float(auction_strength.median())
        
        # 集合竞价量能变化
        if "prev_amount" in group.columns:
            auction_volume_change = (group["amount"] - group["prev_amount"]) / group["prev_amount"].replace(0, np.nan)
            features["auction_volume_change"] = float(auction_volume_change.median())
        else:
            features["auction_volume_change"] = np.nan
    else:
        features.update({
            "auction_strength": np.nan,
            "auction_volume_change": np.nan,
        })
    
    return features
