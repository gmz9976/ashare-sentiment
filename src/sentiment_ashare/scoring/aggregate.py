from __future__ import annotations

from dataclasses import asdict
from typing import Dict

import numpy as np
import pandas as pd

from sentiment_ashare.config import WeightsConfig


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
) -> pd.DataFrame:
    """
    计算综合市场情绪得分
    
    将多个情绪特征聚合成单一的情绪得分，通过滚动标准化和加权平均的方式
    消除不同特征间的量纲差异，生成标准化的市场情绪指标。
    
    Args:
        features: 包含每日情绪特征的DataFrame
        weights: 特征权重配置对象
        rolling_window: 滚动标准化窗口大小
        date_column: 日期列名
        
    Returns:
        pd.DataFrame: 包含日期和情绪得分的DataFrame，列包括：
            - {date_column}: 日期
            - sentiment_score: 标准化后的综合情绪得分
            
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

    return feats[[date_column, "sentiment_score"]].reset_index(drop=True)


