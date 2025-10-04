from __future__ import annotations

from dataclasses import asdict
from typing import Dict

import numpy as np
import pandas as pd

from sentiment_ashare.config import WeightsConfig
from sentiment_ashare.features import classify_sentiment_state, get_sentiment_analysis


def _zscore_by_rolling(series: pd.Series, window: int) -> pd.Series:
    """
    计算滚动窗口的Z分数标准化
    
    使用滚动窗口对时间序列进行标准化，消除时间趋势和季节性影响，
    使不同特征具有可比性。
    
    Args:
        series: 待标准化的时间序列
        window: 滚动窗口大小
        
    Returns:
        pd.Series: 标准化后的Z分数序列
    """
    rolling = series.rolling(window=window, min_periods=max(2, window // 4))
    mean = rolling.mean()
    std = rolling.std(ddof=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = (series - mean) / std
    return z.replace([np.inf, -np.inf], np.nan)


def compute_sentiment_score(
    features: pd.DataFrame,
    *,
    weights: WeightsConfig,
    rolling_window: int,
    date_column: str,
    enable_classification: bool = True,
) -> pd.DataFrame:
    """
    计算综合市场情绪得分和情绪状态分类
    
    将多个情绪特征聚合成单一的情绪得分，通过滚动标准化和加权平均的方式
    消除不同特征间的量纲差异，生成标准化的市场情绪指标。
    同时进行情绪状态分类和冰点识别。
    
    Args:
        features: 包含每日情绪特征的DataFrame
        weights: 特征权重配置对象
        rolling_window: 滚动标准化窗口大小
        date_column: 日期列名
        enable_classification: 是否启用情绪状态分类
        
    Returns:
        pd.DataFrame: 包含日期、情绪得分和情绪状态的DataFrame，列包括：
            - {date_column}: 日期
            - sentiment_score: 标准化后的综合情绪得分
            - sentiment_state: 情绪状态分类
            - is_ice_point: 是否为冰点
            - warming_signal: 转暖信号
            
    Note:
        情绪得分范围通常在-3到+3之间，正值表示市场情绪偏乐观，
        负值表示市场情绪偏悲观，绝对值越大表示情绪越极端。
    """
    feats = features.copy()
    feats = feats.sort_values(date_column)

    weight_map: Dict[str, float] = asdict(weights)

    z_cols = {}
    for name in weight_map.keys():
        if name in feats.columns:
            z = _zscore_by_rolling(feats[name].astype(float), rolling_window)
            feats[f"z_{name}"] = z
            z_cols[name] = f"z_{name}"

    # Align to available features only
    used_items = [(k, w) for k, w in weight_map.items() if k in z_cols]
    if not used_items:
        raise ValueError("No matching features present to compute sentiment score")

    zsum = 0.0
    wsum = 0.0
    for fname, w in used_items:
        zsum = zsum + feats[z_cols[fname]].fillna(0.0) * float(w)
        wsum = wsum + abs(float(w))

    feats["sentiment_score"] = zsum / (wsum if wsum != 0 else 1.0)

    # 情绪状态分类
    if enable_classification:
        feats = classify_sentiment_state(feats, date_column=date_column)
    
    # 选择输出列
    output_columns = [date_column, "sentiment_score"]
    if enable_classification:
        output_columns.extend(["sentiment_state", "is_ice_point", "warming_signal"])

    return feats[output_columns].reset_index(drop=True)


def get_detailed_sentiment_analysis(
    features: pd.DataFrame,
    *,
    date_column: str = "trade_date",
) -> Dict[str, Any]:
    """
    获取详细的情绪分析报告
    
    Args:
        features: 包含情绪特征的DataFrame
        date_column: 日期列名
        
    Returns:
        Dict[str, Any]: 详细的情绪分析报告
    """
    return get_sentiment_analysis(features, date_column=date_column)


