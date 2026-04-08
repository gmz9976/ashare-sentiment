from __future__ import annotations

import numpy as np
import pandas as pd


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
    
    Args:
        df: WeStockProvider.fetch() 返回的 DataFrame
        date_column: 日期列名，默认 "trade_date"
        rolling_window: 量能变化率的滚动窗口（默认 20 个交易日）
        
    Returns:
        pd.DataFrame: 每日情绪特征，包含与 WeightsConfig 对应的特征列
    """
    if df.empty:
        return pd.DataFrame()
    
    df = df.copy().sort_values(date_column).reset_index(drop=True)
    
    total = df["total_stocks"].replace(0, np.nan)
    
    # ============================================================
    # 基础特征（7个）
    # ============================================================
    
    # advance_decline: 上涨股票占上涨+下跌之和的比例（排除平盘）
    active = (df["advancing"] + df["declining"]).replace(0, np.nan)
    df["advance_decline"] = df["advancing"] / active
    
    # limit_up_down: 涨停净占比
    df["limit_up_down"] = (df["limit_up"] - df["limit_down"]) / total
    
    # gap_breadth: 使用强势股比例代理（涨停 + >7% 区间占总数）
    strong = df["limit_up"] + df.get("range_gt7", pd.Series(0, index=df.index))
    df["gap_breadth"] = strong / total
    
    # reversal_breadth: 用弱势区间(-2~-5%)占比代理（反转信号候选区间）
    df["reversal_breadth"] = df.get("range_n5_n2", pd.Series(0, index=df.index)) / total
    
    # turnover_surge: 当日成交额 vs 滚动均值的比率（MA{rolling_window}）
    if "turnover_value" in df.columns:
        tv = df["turnover_value"]
        ma_tv = tv.rolling(window=rolling_window, min_periods=1).mean()
        df["turnover_surge"] = tv / ma_tv.replace(0, np.nan)
    else:
        df["turnover_surge"] = np.nan
    
    # intraday_volatility: 指数日内波动幅度 (high - low) / open
    if all(c in df.columns for c in ("index_high", "index_low", "index_open")):
        df["intraday_volatility"] = (
            (df["index_high"] - df["index_low"])
            / df["index_open"].replace(0, np.nan)
        )
    else:
        df["intraday_volatility"] = np.nan
    
    # amount_breadth: 用 advance_decline 代理（两者高度相关）
    df["amount_breadth"] = df["advance_decline"]
    
    # ============================================================
    # 高级特征（10个，部分为 NaN）
    # ============================================================
    
    # advance_ratio: 上涨股票占总数比例
    df["advance_ratio"] = df["advancing"] / total
    
    # limit_up_ratio: 涨停占总数比例
    df["limit_up_ratio"] = df["limit_up"] / total
    
    # limit_down_ratio: 跌停占总数比例（取反：跌停率越高→情绪越负向）
    # 权重配置中为正值（1.5），但跌停率高代表悲观情绪，
    # 此处取负号，使得"跌停率高→该特征值低→评分被负向拉动"语义正确。
    df["limit_down_ratio"] = -(df["limit_down"] / total)
    
    # limit_net_ratio: 涨跌停净占比
    df["limit_net_ratio"] = (df["limit_up"] - df["limit_down"]) / total
    
    # continuation_stocks: 涨停数（近似代理连板）
    df["continuation_stocks"] = df["limit_up"].astype(float)
    
    # volume_change_ratio: 日成交额变化率
    if "turnover_value" in df.columns:
        prev_tv = df["turnover_value"].shift(1)
        df["volume_change_ratio"] = (
            (df["turnover_value"] - prev_tv) / prev_tv.replace(0, np.nan)
        )
    else:
        df["volume_change_ratio"] = np.nan
    
    # break_board_ratio, seal_board_ratio: 无数据，填 NaN
    df["break_board_ratio"] = np.nan
    df["seal_board_ratio"] = np.nan
    
    # heaven_earth_count: 无数据，填 NaN
    df["heaven_earth_count"] = np.nan
    
    # abnormal_movement_count: 大幅波动股票数（涨停 + >7% + <-7% + 跌停）
    abnormal_parts = [df["limit_up"], df["limit_down"]]
    if "range_gt7" in df.columns:
        abnormal_parts.append(df["range_gt7"])
    if "range_lt_n7" in df.columns:
        abnormal_parts.append(df["range_lt_n7"])
    df["abnormal_movement_count"] = sum(abnormal_parts).astype(float)
    
    # auction_strength: 用指数涨跌幅代理（单位：百分比→小数）
    if "index_pct_chg" in df.columns:
        df["auction_strength"] = df["index_pct_chg"] / 100.0
    else:
        df["auction_strength"] = np.nan
    
    # ============================================================
    # 选取输出列
    # ============================================================
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
