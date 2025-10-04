from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd


def compute_basic_features(
    df: pd.DataFrame,
    *,
    date_column: str,
    symbol_column: str,
    price_columns: Sequence[str] = ("open", "high", "low", "close"),
    turnover_column: str = "amount",
) -> pd.DataFrame:
    """
    计算A股市场的基础横截面情绪特征
    
    基于每日市场数据计算7个关键的情绪指标，用于量化市场情绪状态。
    每个特征都是基于当日所有股票的表现计算得出的比例或中位数。
    
    Args:
        df: 包含市场数据的DataFrame
        date_column: 日期列名
        symbol_column: 股票代码列名
        price_columns: 价格相关列名，默认为("open", "high", "low", "close")
        turnover_column: 成交金额列名，默认为"amount"
        
    Returns:
        pd.DataFrame: 包含每日情绪特征的DataFrame，列包括：
            - advance_decline: 上涨股票占比（基于收盘价涨跌）
            - limit_up_down: 涨跌停净占比（涨停占比 - 跌停占比）
            - gap_breadth: 跳空高开股票占比（开盘价 > 前收盘价）
            - reversal_breadth: 日内反转股票占比（跳空下跌后收涨，或跳空上涨后收跌）
            - turnover_surge: 成交量激增股票占比（超过当日中位数）
            - intraday_volatility: 日内波动率中位数（(最高价-最低价)/开盘价）
            - amount_breadth: 成交金额超中位数股票占比
            
    Note:
        如果缺少必要的列，对应特征将返回NaN值
    """
    required = set([date_column, symbol_column])
    missing_base = [c for c in required if c not in df.columns]
    if missing_base:
        raise ValueError(f"Missing base columns: {missing_base}")

    data = df.copy()
    data = data.sort_values([date_column, symbol_column])

    # Prepare previous close for gap calculation if 'close' exists
    if "close" in data.columns:
        data["prev_close"] = data.groupby(symbol_column)["close"].shift(1)

    def _daily_features(group: pd.DataFrame) -> pd.Series:
        features: dict[str, float] = {}
        n = len(group)
        if n == 0:
            return pd.Series(
                {
                    "advance_decline": np.nan,
                    "limit_up_down": np.nan,
                    "gap_breadth": np.nan,
                    "reversal_breadth": np.nan,
                    "turnover_surge": np.nan,
                    "intraday_volatility": np.nan,
                    "amount_breadth": np.nan,
                }
            )

        # advance_decline
        if "close" in group.columns and "prev_close" in group.columns:
            ret = (group["close"] - group["prev_close"]) / group["prev_close"]
            features["advance_decline"] = float((ret > 0).mean())
        elif "pct_chg" in group.columns:
            features["advance_decline"] = float((group["pct_chg"] > 0).mean())
        else:
            features["advance_decline"] = np.nan

        # limit_up_down (simplified: using pct_chg thresholds if available)
        if "pct_chg" in group.columns:
            up = (group["pct_chg"] >= 9.8).mean()
            down = (group["pct_chg"] <= -9.8).mean()
            features["limit_up_down"] = float(up - down)
        else:
            features["limit_up_down"] = np.nan

        # gap_breadth
        if "open" in group.columns and "prev_close" in group.columns:
            gap = group["open"] - group["prev_close"]
            features["gap_breadth"] = float((gap > 0).mean())
        else:
            features["gap_breadth"] = np.nan

        # reversal_breadth
        if "open" in group.columns and "close" in group.columns and "prev_close" in group.columns:
            gap = group["open"] - group["prev_close"]
            reversal = (
                ((gap < 0) & (group["close"] > group["open"]))
                | ((gap > 0) & (group["close"] < group["open"]))
            )
            features["reversal_breadth"] = float(reversal.mean())
        else:
            features["reversal_breadth"] = np.nan

        # turnover_surge and amount_breadth (use 'amount' column if available)
        if turnover_column in group.columns:
            med = group[turnover_column].median()
            features["turnover_surge"] = float((group[turnover_column] > med).mean())
            features["amount_breadth"] = float((group[turnover_column] > med).mean())
        else:
            features["turnover_surge"] = np.nan
            features["amount_breadth"] = np.nan

        # intraday_volatility
        if all(c in group.columns for c in ("high", "low", "open")):
            iv = (group["high"] - group["low"]) / group["open"].replace(0, np.nan)
            features["intraday_volatility"] = float(iv.median())
        else:
            features["intraday_volatility"] = np.nan

        return pd.Series(features)

    daily = data.groupby(date_column).apply(_daily_features).reset_index()
    return daily


