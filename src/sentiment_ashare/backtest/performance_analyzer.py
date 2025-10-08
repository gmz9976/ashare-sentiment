"""
回测绩效分析器

提供全面的策略绩效分析功能，包括收益率计算、风险指标、相关性分析等。
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from scipy import stats
import warnings

warnings.filterwarnings('ignore')


class PerformanceAnalyzer:
    """
    绩效分析器
    
    提供全面的策略绩效分析功能，包括：
    - 收益率计算
    - 风险指标计算
    - 相关性分析
    - 情绪指标有效性分析
    """
    
    def __init__(self, risk_free_rate: float = 0.03):
        """
        初始化绩效分析器
        
        Args:
            risk_free_rate: 无风险利率，默认3%
        """
        self.risk_free_rate = risk_free_rate
        
    def calculate_returns(self, prices: pd.Series) -> pd.Series:
        """
        计算收益率
        
        Args:
            prices: 价格序列
            
        Returns:
            pd.Series: 收益率序列
        """
        return prices.pct_change().dropna()
        
    def calculate_cumulative_returns(self, returns: pd.Series) -> pd.Series:
        """
        计算累计收益率
        
        Args:
            returns: 收益率序列
            
        Returns:
            pd.Series: 累计收益率序列
        """
        return (1 + returns).cumprod() - 1
        
    def calculate_annual_return(self, returns: pd.Series) -> float:
        """
        计算年化收益率
        
        Args:
            returns: 收益率序列
            
        Returns:
            float: 年化收益率
        """
        if len(returns) == 0:
            return 0.0
            
        total_return = (1 + returns).prod() - 1
        years = len(returns) / 252  # 假设一年252个交易日
        
        if years > 0:
            return (1 + total_return) ** (1 / years) - 1
        else:
            return 0.0
            
    def calculate_annual_volatility(self, returns: pd.Series) -> float:
        """
        计算年化波动率
        
        Args:
            returns: 收益率序列
            
        Returns:
            float: 年化波动率
        """
        if len(returns) == 0:
            return 0.0
            
        return returns.std() * np.sqrt(252)
        
    def calculate_sharpe_ratio(self, returns: pd.Series) -> float:
        """
        计算夏普比率
        
        Args:
            returns: 收益率序列
            
        Returns:
            float: 夏普比率
        """
        if len(returns) == 0:
            return 0.0
            
        excess_returns = returns - self.risk_free_rate / 252
        volatility = returns.std()
        
        if volatility == 0:
            return 0.0
            
        return excess_returns.mean() / volatility * np.sqrt(252)
        
    def calculate_sortino_ratio(self, returns: pd.Series) -> float:
        """
        计算索提诺比率（下行风险调整收益率）
        
        Args:
            returns: 收益率序列
            
        Returns:
            float: 索提诺比率
        """
        if len(returns) == 0:
            return 0.0
            
        excess_returns = returns - self.risk_free_rate / 252
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0:
            return np.inf if excess_returns.mean() > 0 else 0.0
            
        downside_deviation = downside_returns.std() * np.sqrt(252)
        
        if downside_deviation == 0:
            return 0.0
            
        return excess_returns.mean() / downside_deviation * np.sqrt(252)
        
    def calculate_max_drawdown(self, cumulative_returns: pd.Series) -> Tuple[float, pd.Timestamp, pd.Timestamp]:
        """
        计算最大回撤
        
        Args:
            cumulative_returns: 累计收益率序列
            
        Returns:
            Tuple[float, pd.Timestamp, pd.Timestamp]: (最大回撤, 回撤开始日期, 回撤结束日期)
        """
        if len(cumulative_returns) == 0:
            return 0.0, None, None
            
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / (1 + running_max)
        
        max_dd = drawdown.min()
        max_dd_date = drawdown.idxmin()
        
        # 找到回撤开始日期
        peak_date = running_max.loc[max_dd_date]
        drawdown_start = cumulative_returns[cumulative_returns == peak_date].index[0]
        
        # 找到回撤结束日期（恢复到前期高点）
        recovery_data = cumulative_returns.loc[max_dd_date:]
        recovery_date = recovery_data[recovery_data >= peak_date].index
        
        if len(recovery_date) > 0:
            recovery_date = recovery_date[0]
        else:
            recovery_date = cumulative_returns.index[-1]
        
        return max_dd, drawdown_start, recovery_date
        
    def calculate_calmar_ratio(self, returns: pd.Series, max_drawdown: float) -> float:
        """
        计算卡尔玛比率（年化收益率/最大回撤）
        
        Args:
            returns: 收益率序列
            max_drawdown: 最大回撤
            
        Returns:
            float: 卡尔玛比率
        """
        if max_drawdown == 0:
            return np.inf if self.calculate_annual_return(returns) > 0 else 0.0
            
        annual_return = self.calculate_annual_return(returns)
        return annual_return / abs(max_drawdown)
        
    def calculate_win_rate(self, returns: pd.Series) -> float:
        """
        计算胜率
        
        Args:
            returns: 收益率序列
            
        Returns:
            float: 胜率（正收益率比例）
        """
        if len(returns) == 0:
            return 0.0
            
        return (returns > 0).mean()
        
    def calculate_profit_loss_ratio(self, returns: pd.Series) -> float:
        """
        计算盈亏比
        
        Args:
            returns: 收益率序列
            
        Returns:
            float: 盈亏比（平均盈利/平均亏损）
        """
        if len(returns) == 0:
            return 0.0
            
        positive_returns = returns[returns > 0]
        negative_returns = returns[returns < 0]
        
        if len(positive_returns) == 0 or len(negative_returns) == 0:
            return 0.0
            
        avg_profit = positive_returns.mean()
        avg_loss = abs(negative_returns.mean())
        
        return avg_profit / avg_loss if avg_loss != 0 else 0.0
        
    def calculate_correlation_with_indices(self, strategy_returns: pd.Series, 
                                         index_returns: Dict[str, pd.Series]) -> Dict[str, Dict[str, float]]:
        """
        计算与指数的相关性
        
        Args:
            strategy_returns: 策略收益率序列
            index_returns: 指数收益率字典
            
        Returns:
            Dict[str, Dict[str, float]]: 相关性分析结果
        """
        correlations = {}
        
        for index_name, index_ret in index_returns.items():
            # 对齐时间序列
            aligned_data = pd.concat([strategy_returns, index_ret], axis=1, join='inner').dropna()
            
            if len(aligned_data) > 10:
                strategy_ret_aligned = aligned_data.iloc[:, 0]
                index_ret_aligned = aligned_data.iloc[:, 1]
                
                # 计算相关系数和p值
                corr, p_value = stats.pearsonr(strategy_ret_aligned, index_ret_aligned)
                
                correlations[index_name] = {
                    'correlation': corr,
                    'p_value': p_value,
                    'significant': p_value < 0.05,
                    'sample_size': len(aligned_data)
                }
            else:
                correlations[index_name] = {
                    'correlation': 0.0,
                    'p_value': 1.0,
                    'significant': False,
                    'sample_size': len(aligned_data)
                }
        
        return correlations
        
    def analyze_sentiment_effectiveness(self, sentiment_data: pd.DataFrame, 
                                      market_returns: pd.Series) -> Dict[str, Any]:
        """
        分析情绪指标有效性
        
        Args:
            sentiment_data: 情绪数据DataFrame
            market_returns: 市场收益率序列
            
        Returns:
            Dict[str, Any]: 情绪指标有效性分析结果
        """
        analysis = {}
        
        # 对齐数据
        sentiment_score = sentiment_data.get('sentiment_score', pd.Series())
        aligned_data = pd.concat([sentiment_score, market_returns], axis=1, join='inner').dropna()
        
        if len(aligned_data) < 10:
            return {'error': '数据不足，无法进行分析'}
        
        sentiment_aligned = aligned_data.iloc[:, 0]
        market_aligned = aligned_data.iloc[:, 1]
        
        # 1. 情绪得分与市场收益率相关性
        corr, p_value = stats.pearsonr(sentiment_aligned, market_aligned)
        analysis['sentiment_market_correlation'] = {
            'correlation': corr,
            'p_value': p_value,
            'significant': p_value < 0.05,
            'sample_size': len(aligned_data)
        }
        
        # 2. 情绪得分预测能力分析
        analysis['sentiment_predictive_power'] = self._analyze_predictive_power(
            sentiment_aligned, market_aligned
        )
        
        # 3. 冰点信号分析
        if 'is_ice_point' in sentiment_data.columns:
            analysis['ice_point_analysis'] = self._analyze_ice_point_signals(
                sentiment_data, market_returns
            )
        
        # 4. 转暖信号分析
        if 'warming_signal' in sentiment_data.columns:
            analysis['warming_signal_analysis'] = self._analyze_warming_signals(
                sentiment_data, market_returns
            )
        
        # 5. 情绪状态分析
        if 'sentiment_state' in sentiment_data.columns:
            analysis['sentiment_state_analysis'] = self._analyze_sentiment_states(
                sentiment_data, market_returns
            )
        
        return analysis
        
    def _analyze_predictive_power(self, sentiment_score: pd.Series, 
                                market_returns: pd.Series) -> Dict[str, Any]:
        """
        分析情绪得分的预测能力
        
        Args:
            sentiment_score: 情绪得分序列
            market_returns: 市场收益率序列
            
        Returns:
            Dict[str, Any]: 预测能力分析结果
        """
        # 计算不同滞后期的相关性
        lags = [1, 3, 5, 10]
        lag_correlations = {}
        
        for lag in lags:
            if len(sentiment_score) > lag:
                sentiment_lagged = sentiment_score.shift(lag)
                aligned_data = pd.concat([sentiment_lagged, market_returns], axis=1).dropna()
                
                if len(aligned_data) > 10:
                    corr, p_value = stats.pearsonr(aligned_data.iloc[:, 0], aligned_data.iloc[:, 1])
                    lag_correlations[f'lag_{lag}'] = {
                        'correlation': corr,
                        'p_value': p_value,
                        'significant': p_value < 0.05
                    }
        
        # 分析情绪得分的极值预测能力
        high_sentiment = sentiment_score > sentiment_score.quantile(0.8)
        low_sentiment = sentiment_score < sentiment_score.quantile(0.2)
        
        high_sentiment_returns = market_returns[high_sentiment]
        low_sentiment_returns = market_returns[low_sentiment]
        
        return {
            'lag_correlations': lag_correlations,
            'high_sentiment_performance': {
                'mean_return': high_sentiment_returns.mean() if len(high_sentiment_returns) > 0 else 0,
                'positive_rate': (high_sentiment_returns > 0).mean() if len(high_sentiment_returns) > 0 else 0,
                'sample_size': len(high_sentiment_returns)
            },
            'low_sentiment_performance': {
                'mean_return': low_sentiment_returns.mean() if len(low_sentiment_returns) > 0 else 0,
                'positive_rate': (low_sentiment_returns > 0).mean() if len(low_sentiment_returns) > 0 else 0,
                'sample_size': len(low_sentiment_returns)
            }
        }
        
    def _analyze_ice_point_signals(self, sentiment_data: pd.DataFrame, 
                                 market_returns: pd.Series) -> Dict[str, Any]:
        """
        分析冰点信号的有效性
        
        Args:
            sentiment_data: 情绪数据DataFrame
            market_returns: 市场收益率序列
            
        Returns:
            Dict[str, Any]: 冰点信号分析结果
        """
        ice_point_days = sentiment_data[sentiment_data['is_ice_point'] == True].index
        
        if len(ice_point_days) == 0:
            return {'count': 0, 'message': '未检测到冰点信号'}
        
        # 分析冰点信号后的市场表现
        forward_returns = {}
        for days in [1, 3, 5, 10, 20]:
            forward_returns[f'{days}d'] = self._calculate_forward_returns(
                market_returns, ice_point_days, days
            )
        
        # 分析冰点信号的准确性
        ice_point_accuracy = {}
        for days, returns in forward_returns.items():
            if len(returns) > 0:
                ice_point_accuracy[days] = {
                    'mean_return': np.mean(returns),
                    'positive_rate': np.mean(np.array(returns) > 0),
                    'median_return': np.median(returns),
                    'sample_size': len(returns)
                }
        
        return {
            'count': len(ice_point_days),
            'forward_returns': forward_returns,
            'accuracy': ice_point_accuracy,
            'ice_point_dates': ice_point_days.tolist()
        }
        
    def _analyze_warming_signals(self, sentiment_data: pd.DataFrame, 
                               market_returns: pd.Series) -> Dict[str, Any]:
        """
        分析转暖信号的有效性
        
        Args:
            sentiment_data: 情绪数据DataFrame
            market_returns: 市场收益率序列
            
        Returns:
            Dict[str, Any]: 转暖信号分析结果
        """
        warming_days = sentiment_data[sentiment_data['warming_signal'] == True].index
        
        if len(warming_days) == 0:
            return {'count': 0, 'message': '未检测到转暖信号'}
        
        # 分析转暖信号后的市场表现
        forward_returns = {}
        for days in [1, 3, 5, 10, 20]:
            forward_returns[f'{days}d'] = self._calculate_forward_returns(
                market_returns, warming_days, days
            )
        
        # 分析转暖信号的准确性
        warming_accuracy = {}
        for days, returns in forward_returns.items():
            if len(returns) > 0:
                warming_accuracy[days] = {
                    'mean_return': np.mean(returns),
                    'positive_rate': np.mean(np.array(returns) > 0),
                    'median_return': np.median(returns),
                    'sample_size': len(returns)
                }
        
        return {
            'count': len(warming_days),
            'forward_returns': forward_returns,
            'accuracy': warming_accuracy,
            'warming_dates': warming_days.tolist()
        }
        
    def _analyze_sentiment_states(self, sentiment_data: pd.DataFrame, 
                                market_returns: pd.Series) -> Dict[str, Any]:
        """
        分析不同情绪状态下的市场表现
        
        Args:
            sentiment_data: 情绪数据DataFrame
            market_returns: 市场收益率序列
            
        Returns:
            Dict[str, Any]: 情绪状态分析结果
        """
        sentiment_states = sentiment_data['sentiment_state'].unique()
        state_analysis = {}
        
        for state in sentiment_states:
            state_mask = sentiment_data['sentiment_state'] == state
            state_returns = market_returns[state_mask]
            
            if len(state_returns) > 0:
                state_analysis[state] = {
                    'mean_return': state_returns.mean(),
                    'volatility': state_returns.std(),
                    'positive_rate': (state_returns > 0).mean(),
                    'sample_size': len(state_returns),
                    'min_return': state_returns.min(),
                    'max_return': state_returns.max()
                }
        
        return state_analysis
        
    def _calculate_forward_returns(self, returns: pd.Series, signal_dates: List[pd.Timestamp], 
                                 days: int) -> List[float]:
        """
        计算信号后N日的收益率
        
        Args:
            returns: 收益率序列
            signal_dates: 信号日期列表
            days: 向前计算天数
            
        Returns:
            List[float]: 向前收益率列表
        """
        forward_returns = []
        
        for signal_date in signal_dates:
            # 找到信号日期在收益率序列中的位置
            if signal_date in returns.index:
                signal_idx = returns.index.get_loc(signal_date)
                end_idx = min(signal_idx + days, len(returns) - 1)
                
                if end_idx > signal_idx:
                    period_returns = returns.iloc[signal_idx + 1:end_idx + 1]
                    if len(period_returns) > 0:
                        cumulative_return = (1 + period_returns).prod() - 1
                        forward_returns.append(cumulative_return)
        
        return forward_returns
        
    def generate_performance_summary(self, strategy_returns: pd.Series, 
                                   benchmark_returns: Dict[str, pd.Series]) -> Dict[str, Any]:
        """
        生成策略绩效摘要
        
        Args:
            strategy_returns: 策略收益率序列
            benchmark_returns: 基准收益率字典
            
        Returns:
            Dict[str, Any]: 绩效摘要
        """
        if len(strategy_returns) == 0:
            return {'error': '策略收益率数据为空'}
        
        # 计算策略绩效指标
        cumulative_returns = self.calculate_cumulative_returns(strategy_returns)
        max_dd, dd_start, dd_end = self.calculate_max_drawdown(cumulative_returns)
        
        performance_metrics = {
            'total_return': cumulative_returns.iloc[-1] if len(cumulative_returns) > 0 else 0,
            'annual_return': self.calculate_annual_return(strategy_returns),
            'annual_volatility': self.calculate_annual_volatility(strategy_returns),
            'sharpe_ratio': self.calculate_sharpe_ratio(strategy_returns),
            'sortino_ratio': self.calculate_sortino_ratio(strategy_returns),
            'max_drawdown': max_dd,
            'drawdown_start': dd_start,
            'drawdown_end': dd_end,
            'calmar_ratio': self.calculate_calmar_ratio(strategy_returns, max_dd),
            'win_rate': self.calculate_win_rate(strategy_returns),
            'profit_loss_ratio': self.calculate_profit_loss_ratio(strategy_returns),
            'sample_size': len(strategy_returns)
        }
        
        # 计算与基准的相关性
        correlations = self.calculate_correlation_with_indices(strategy_returns, benchmark_returns)
        
        return {
            'performance_metrics': performance_metrics,
            'correlations': correlations
        }
