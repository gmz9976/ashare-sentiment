from __future__ import annotations

from typing import Dict, List, Tuple, Optional
from enum import Enum

import numpy as np
import pandas as pd


class SentimentState(Enum):
    """市场情绪状态枚举"""
    MAIN_RISE = "主升"           # 主升浪
    WEAK_DIVERGENCE = "弱分歧"   # 弱分歧
    STRONG_DIVERGENCE = "强分歧" # 强分歧
    WEAK_RECOVERY = "弱修复"     # 弱修复
    STRONG_RECOVERY = "强修复"   # 强修复
    RETREAT = "退潮"            # 退潮（连续强分歧）
    ICE_POINT = "冰点"          # 冰点
    UNKNOWN = "未知"            # 未知状态


def classify_sentiment_state(
    features: pd.DataFrame,
    *,
    date_column: str = "trade_date",
    lookback_days: int = 5,
) -> pd.DataFrame:
    """
    根据情绪特征分类市场情绪状态
    
    Args:
        features: 包含情绪特征的DataFrame
        date_column: 日期列名
        lookback_days: 回看天数用于趋势判断
        
    Returns:
        pd.DataFrame: 包含情绪状态分类的DataFrame
    """
    result = features.copy()
    result = result.sort_values(date_column)
    
    # 计算情绪状态
    sentiment_states = []
    ice_point_signals = []
    warming_signals = []
    
    for i in range(len(result)):
        current_features = result.iloc[i]
        historical_features = result.iloc[max(0, i-lookback_days):i+1]
        
        # 分类当前情绪状态
        state = _classify_single_state(current_features, historical_features)
        sentiment_states.append(state)
        
        # 冰点识别
        ice_point = _detect_ice_point(current_features, historical_features)
        ice_point_signals.append(ice_point)
        
        # 转暖信号
        warming = _detect_warming_signal(current_features, historical_features)
        warming_signals.append(warming)
    
    result["sentiment_state"] = sentiment_states
    result["is_ice_point"] = ice_point_signals
    result["warming_signal"] = warming_signals
    
    return result


def _classify_single_state(
    current: pd.Series, 
    historical: pd.DataFrame
) -> str:
    """分类单个日期的情绪状态"""
    
    # 获取关键指标
    advance_ratio = current.get("advance_ratio", 0)
    limit_up_ratio = current.get("limit_up_ratio", 0)
    limit_down_ratio = current.get("limit_down_ratio", 0)
    limit_net_ratio = current.get("limit_net_ratio", 0)
    volume_change = current.get("volume_change_ratio", 0)
    continuation_stocks = current.get("continuation_stocks", 0)
    break_board_ratio = current.get("break_board_ratio", 0)
    
    # 计算趋势指标
    trend_strength = _calculate_trend_strength(historical)
    
    # 状态判断逻辑
    if _is_main_rise(current, historical):
        return SentimentState.MAIN_RISE.value
    elif _is_strong_divergence(current, historical):
        return SentimentState.STRONG_DIVERGENCE.value
    elif _is_weak_divergence(current, historical):
        return SentimentState.WEAK_DIVERGENCE.value
    elif _is_strong_recovery(current, historical):
        return SentimentState.STRONG_RECOVERY.value
    elif _is_weak_recovery(current, historical):
        return SentimentState.WEAK_RECOVERY.value
    elif _is_retreat(current, historical):
        return SentimentState.RETREAT.value
    elif _is_ice_point(current, historical):
        return SentimentState.ICE_POINT.value
    else:
        return SentimentState.UNKNOWN.value


def _is_main_rise(current: pd.Series, historical: pd.DataFrame) -> bool:
    """判断是否为主升浪"""
    advance_ratio = current.get("advance_ratio", 0)
    limit_up_ratio = current.get("limit_up_ratio", 0)
    limit_net_ratio = current.get("limit_net_ratio", 0)
    volume_change = current.get("volume_change_ratio", 0)
    
    # 主升浪条件：上涨比例高、涨停多、量能放大
    return (
        advance_ratio > 0.7 and
        limit_up_ratio > 0.05 and
        limit_net_ratio > 0.03 and
        volume_change > 0.2
    )


def _is_strong_divergence(current: pd.Series, historical: pd.DataFrame) -> bool:
    """判断是否为强分歧"""
    advance_ratio = current.get("advance_ratio", 0)
    limit_up_ratio = current.get("limit_up_ratio", 0)
    limit_down_ratio = current.get("limit_down_ratio", 0)
    break_board_ratio = current.get("break_board_ratio", 0)
    
    # 强分歧条件：涨跌分化明显、破板率高
    return (
        advance_ratio > 0.4 and advance_ratio < 0.7 and
        limit_up_ratio > 0.02 and limit_down_ratio > 0.01 and
        break_board_ratio > 0.3
    )


def _is_weak_divergence(current: pd.Series, historical: pd.DataFrame) -> bool:
    """判断是否为弱分歧"""
    advance_ratio = current.get("advance_ratio", 0)
    limit_up_ratio = current.get("limit_up_ratio", 0)
    limit_down_ratio = current.get("limit_down_ratio", 0)
    
    # 弱分歧条件：涨跌相对平衡
    return (
        advance_ratio > 0.3 and advance_ratio < 0.6 and
        limit_up_ratio > 0.01 and limit_down_ratio > 0.005 and
        abs(limit_up_ratio - limit_down_ratio) < 0.02
    )


def _is_strong_recovery(current: pd.Series, historical: pd.DataFrame) -> bool:
    """判断是否为强修复"""
    advance_ratio = current.get("advance_ratio", 0)
    limit_up_ratio = current.get("limit_up_ratio", 0)
    limit_net_ratio = current.get("limit_net_ratio", 0)
    volume_change = current.get("volume_change_ratio", 0)
    
    # 强修复条件：从低点快速反弹
    return (
        advance_ratio > 0.6 and
        limit_up_ratio > 0.03 and
        limit_net_ratio > 0.02 and
        volume_change > 0.1
    )


def _is_weak_recovery(current: pd.Series, historical: pd.DataFrame) -> bool:
    """判断是否为弱修复"""
    advance_ratio = current.get("advance_ratio", 0)
    limit_up_ratio = current.get("limit_up_ratio", 0)
    
    # 弱修复条件：小幅反弹
    return (
        advance_ratio > 0.5 and advance_ratio < 0.7 and
        limit_up_ratio > 0.01 and limit_up_ratio < 0.03
    )


def _is_retreat(current: pd.Series, historical: pd.DataFrame) -> bool:
    """判断是否为退潮"""
    advance_ratio = current.get("advance_ratio", 0)
    limit_up_ratio = current.get("limit_up_ratio", 0)
    limit_down_ratio = current.get("limit_down_ratio", 0)
    
    # 退潮条件：连续下跌、涨停减少、跌停增加
    return (
        advance_ratio < 0.4 and
        limit_up_ratio < 0.02 and
        limit_down_ratio > 0.01
    )


def _is_ice_point(current: pd.Series, historical: pd.DataFrame) -> bool:
    """判断是否为冰点"""
    advance_ratio = current.get("advance_ratio", 0)
    limit_up_ratio = current.get("limit_up_ratio", 0)
    limit_down_ratio = current.get("limit_down_ratio", 0)
    volume_change = current.get("volume_change_ratio", 0)
    
    # 冰点条件：极度悲观
    return (
        advance_ratio < 0.3 and
        limit_up_ratio < 0.01 and
        limit_down_ratio > 0.02 and
        volume_change < -0.1
    )


def _detect_ice_point(current: pd.Series, historical: pd.DataFrame) -> bool:
    """检测冰点信号"""
    return _is_ice_point(current, historical)


def _detect_warming_signal(current: pd.Series, historical: pd.DataFrame) -> bool:
    """检测转暖信号"""
    advance_ratio = current.get("advance_ratio", 0)
    limit_up_ratio = current.get("limit_up_ratio", 0)
    volume_change = current.get("volume_change_ratio", 0)
    
    # 转暖信号：从冰点开始改善
    if len(historical) > 1:
        prev_advance = historical.iloc[-2].get("advance_ratio", 0)
        prev_limit_up = historical.iloc[-2].get("limit_up_ratio", 0)
        
        return (
            advance_ratio > prev_advance + 0.1 and
            limit_up_ratio > prev_limit_up + 0.005 and
            volume_change > 0
        )
    
    return False


def _calculate_trend_strength(historical: pd.DataFrame) -> float:
    """计算趋势强度"""
    if len(historical) < 2:
        return 0.0
    
    advance_ratios = historical["advance_ratio"].dropna()
    if len(advance_ratios) < 2:
        return 0.0
    
    # 计算趋势斜率
    x = np.arange(len(advance_ratios))
    y = advance_ratios.values
    slope = np.polyfit(x, y, 1)[0]
    
    return slope


def get_sentiment_analysis(
    features: pd.DataFrame,
    *,
    date_column: str = "trade_date",
) -> Dict[str, Any]:
    """
    获取情绪分析报告
    
    Args:
        features: 包含情绪特征的DataFrame
        date_column: 日期列名
        
    Returns:
        Dict[str, Any]: 情绪分析报告
    """
    if len(features) == 0:
        return {"error": "No data available"}
    
    latest = features.iloc[-1]
    
    analysis = {
        "current_state": latest.get("sentiment_state", "未知"),
        "is_ice_point": latest.get("is_ice_point", False),
        "warming_signal": latest.get("warming_signal", False),
        "key_metrics": {
            "advance_ratio": latest.get("advance_ratio", 0),
            "limit_up_ratio": latest.get("limit_up_ratio", 0),
            "limit_down_ratio": latest.get("limit_down_ratio", 0),
            "volume_change": latest.get("volume_change_ratio", 0),
        },
        "recommendations": _get_recommendations(latest)
    }
    
    return analysis


def _get_recommendations(current: pd.Series) -> List[str]:
    """获取投资建议"""
    recommendations = []
    
    state = current.get("sentiment_state", "未知")
    is_ice_point = current.get("is_ice_point", False)
    warming_signal = current.get("warming_signal", False)
    
    if state == "主升":
        recommendations.append("市场情绪高涨，可适当参与强势股")
        recommendations.append("注意风险控制，避免追高")
    elif state == "强分歧":
        recommendations.append("市场分歧较大，谨慎操作")
        recommendations.append("关注龙头股表现")
    elif state == "弱分歧":
        recommendations.append("市场相对平衡，可适度参与")
        recommendations.append("关注板块轮动机会")
    elif state == "强修复":
        recommendations.append("市场快速修复，可积极参与")
        recommendations.append("关注超跌反弹机会")
    elif state == "弱修复":
        recommendations.append("市场缓慢修复，谨慎乐观")
        recommendations.append("可关注优质标的")
    elif state == "退潮":
        recommendations.append("市场情绪低迷，建议观望")
        recommendations.append("等待更好的入场时机")
    elif is_ice_point:
        recommendations.append("市场处于冰点，准备抄底机会")
        recommendations.append("关注转暖信号")
    elif warming_signal:
        recommendations.append("检测到转暖信号，可开始关注")
        recommendations.append("逐步建仓优质标的")
    
    return recommendations
