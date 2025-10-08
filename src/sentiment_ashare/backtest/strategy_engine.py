"""
回测策略引擎

实现基于情绪指标的各种交易策略，包括冰点策略、情绪动量策略等。
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass


@dataclass
class StrategyParams:
    """策略参数基类"""
    name: str
    params: Dict[str, Any]


class SentimentStrategy(ABC):
    """
    情绪策略基类
    
    所有基于情绪指标的交易策略都应该继承此类并实现generate_signals方法。
    """
    
    def __init__(self, name: str, params: Dict[str, Any] = None):
        """
        初始化策略
        
        Args:
            name: 策略名称
            params: 策略参数字典
        """
        self.name = name
        self.params = params or {}
        
    @abstractmethod
    def generate_signals(self, sentiment_data: pd.DataFrame, 
                        market_data: pd.DataFrame,
                        index_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        生成交易信号
        
        Args:
            sentiment_data: 情绪数据DataFrame
            market_data: 市场数据DataFrame
            index_data: 指数数据字典
            
        Returns:
            pd.DataFrame: 包含交易信号的DataFrame，必须包含以下列：
                - signal: 交易信号 (1=买入, -1=卖出, 0=持有)
                - position: 持仓比例 (0-1)
        """
        pass
        
    def calculate_position(self, signals: pd.DataFrame) -> pd.DataFrame:
        """
        根据信号计算持仓比例
        
        Args:
            signals: 包含signal列的DataFrame
            
        Returns:
            pd.DataFrame: 添加了position列的DataFrame
        """
        result = signals.copy()
        
        # 简单的持仓计算：信号为1时满仓，信号为-1时空仓
        position = np.where(result['signal'] == 1, 1.0,
                           np.where(result['signal'] == -1, 0.0, np.nan))
        
        # 前向填充持仓
        position = pd.Series(position, index=result.index).fillna(method='ffill').fillna(0.0)
        result['position'] = position
        
        return result


class IcePointStrategy(SentimentStrategy):
    """
    冰点策略
    
    在检测到市场冰点时买入，在转暖信号出现时卖出。
    基于情绪指标中的冰点识别和转暖信号。
    """
    
    def __init__(self, name: str = "冰点策略", params: Dict[str, Any] = None):
        """
        初始化冰点策略
        
        Args:
            name: 策略名称
            params: 策略参数字典，可包含：
                - holding_days: 最大持有天数，默认10天
                - stop_loss: 止损比例，默认0.05 (5%)
                - min_ice_point_score: 最小冰点得分阈值，默认-2.0
        """
        default_params = {
            'holding_days': 10,
            'stop_loss': 0.05,
            'min_ice_point_score': -2.0
        }
        if params:
            default_params.update(params)
        
        super().__init__(name, default_params)
        
    def generate_signals(self, sentiment_data: pd.DataFrame, 
                        market_data: pd.DataFrame,
                        index_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        生成冰点策略交易信号
        
        策略逻辑：
        1. 当检测到冰点信号且情绪得分低于阈值时，产生买入信号
        2. 当检测到转暖信号时，产生卖出信号
        3. 持有时间超过最大持有天数时，强制卖出
        """
        signals = pd.DataFrame(index=sentiment_data.index)
        signals['signal'] = 0
        signals['position'] = 0.0
        
        # 获取冰点和转暖信号
        ice_point_mask = sentiment_data.get('is_ice_point', False)
        warming_mask = sentiment_data.get('warming_signal', False)
        sentiment_score = sentiment_data.get('sentiment_score', 0)
        
        # 买入条件：冰点信号且情绪得分低于阈值
        buy_condition = (
            ice_point_mask == True
        ) & (
            sentiment_score <= self.params['min_ice_point_score']
        )
        
        # 卖出条件：转暖信号
        sell_condition = warming_mask == True
        
        # 生成信号
        signals.loc[buy_condition, 'signal'] = 1  # 买入信号
        signals.loc[sell_condition, 'signal'] = -1  # 卖出信号
        
        # 处理持有时间限制
        signals = self._handle_holding_period(signals)
        
        # 计算持仓比例
        signals = self.calculate_position(signals)
        
        return signals
        
    def _handle_holding_period(self, signals: pd.DataFrame) -> pd.DataFrame:
        """
        处理持有时间限制
        
        Args:
            signals: 包含signal列的DataFrame
            
        Returns:
            pd.DataFrame: 处理后的信号DataFrame
        """
        result = signals.copy()
        holding_days = self.params['holding_days']
        
        # 找到所有买入信号
        buy_signals = result[result['signal'] == 1]
        
        for buy_date in buy_signals.index:
            # 找到该买入信号后的卖出信号
            future_signals = result.loc[buy_date:]
            
            # 检查是否有卖出信号
            sell_signals = future_signals[future_signals['signal'] == -1]
            
            if sell_signals.empty:
                # 没有卖出信号，检查是否超过持有期限
                max_hold_date = buy_date + pd.Timedelta(days=holding_days)
                if max_hold_date in result.index:
                    result.loc[max_hold_date, 'signal'] = -1  # 强制卖出
        
        return result


class SentimentMomentumStrategy(SentimentStrategy):
    """
    情绪动量策略
    
    基于情绪得分的动量变化进行交易。
    当情绪得分呈现上升趋势时买入，下降趋势时卖出。
    """
    
    def __init__(self, name: str = "情绪动量策略", params: Dict[str, Any] = None):
        """
        初始化情绪动量策略
        
        Args:
            name: 策略名称
            params: 策略参数字典，可包含：
                - lookback_days: 动量计算回看天数，默认5天
                - threshold: 动量阈值，默认0.5
                - min_sentiment_score: 最小情绪得分阈值，默认-1.0
                - max_sentiment_score: 最大情绪得分阈值，默认1.0
        """
        default_params = {
            'lookback_days': 5,
            'threshold': 0.5,
            'min_sentiment_score': -1.0,
            'max_sentiment_score': 1.0
        }
        if params:
            default_params.update(params)
        
        super().__init__(name, default_params)
        
    def generate_signals(self, sentiment_data: pd.DataFrame, 
                        market_data: pd.DataFrame,
                        index_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        生成情绪动量策略交易信号
        
        策略逻辑：
        1. 计算情绪得分的动量（变化率）
        2. 当动量超过正阈值时买入
        3. 当动量低于负阈值时卖出
        4. 考虑情绪得分的绝对值范围
        """
        signals = pd.DataFrame(index=sentiment_data.index)
        signals['signal'] = 0
        signals['position'] = 0.0
        
        sentiment_score = sentiment_data.get('sentiment_score', 0)
        
        # 计算情绪得分动量
        momentum = sentiment_score.diff(self.params['lookback_days'])
        
        # 买入条件：动量超过正阈值且情绪得分在合理范围内
        buy_condition = (
            momentum > self.params['threshold']
        ) & (
            sentiment_score >= self.params['min_sentiment_score']
        ) & (
            sentiment_score <= self.params['max_sentiment_score']
        )
        
        # 卖出条件：动量低于负阈值
        sell_condition = momentum < -self.params['threshold']
        
        # 生成信号
        signals.loc[buy_condition, 'signal'] = 1  # 买入信号
        signals.loc[sell_condition, 'signal'] = -1  # 卖出信号
        
        # 计算持仓比例
        signals = self.calculate_position(signals)
        
        return signals


class ContrarianStrategy(SentimentStrategy):
    """
    逆向策略
    
    在市场极度悲观时买入，极度乐观时卖出。
    基于情绪得分的极值进行逆向操作。
    """
    
    def __init__(self, name: str = "逆向策略", params: Dict[str, Any] = None):
        """
        初始化逆向策略
        
        Args:
            name: 策略名称
            params: 策略参数字典，可包含：
                - extreme_low_threshold: 极端悲观阈值，默认-2.5
                - extreme_high_threshold: 极端乐观阈值，默认2.5
                - holding_days: 最大持有天数，默认15天
        """
        default_params = {
            'extreme_low_threshold': -2.5,
            'extreme_high_threshold': 2.5,
            'holding_days': 15
        }
        if params:
            default_params.update(params)
        
        super().__init__(name, default_params)
        
    def generate_signals(self, sentiment_data: pd.DataFrame, 
                        market_data: pd.DataFrame,
                        index_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        生成逆向策略交易信号
        
        策略逻辑：
        1. 当情绪得分低于极端悲观阈值时买入
        2. 当情绪得分高于极端乐观阈值时卖出
        3. 基于均值回归假设
        """
        signals = pd.DataFrame(index=sentiment_data.index)
        signals['signal'] = 0
        signals['position'] = 0.0
        
        sentiment_score = sentiment_data.get('sentiment_score', 0)
        
        # 买入条件：情绪得分低于极端悲观阈值
        buy_condition = sentiment_score <= self.params['extreme_low_threshold']
        
        # 卖出条件：情绪得分高于极端乐观阈值
        sell_condition = sentiment_score >= self.params['extreme_high_threshold']
        
        # 生成信号
        signals.loc[buy_condition, 'signal'] = 1  # 买入信号
        signals.loc[sell_condition, 'signal'] = -1  # 卖出信号
        
        # 处理持有时间限制
        signals = self._handle_holding_period(signals)
        
        # 计算持仓比例
        signals = self.calculate_position(signals)
        
        return signals
        
    def _handle_holding_period(self, signals: pd.DataFrame) -> pd.DataFrame:
        """处理持有时间限制"""
        result = signals.copy()
        holding_days = self.params['holding_days']
        
        # 找到所有买入信号
        buy_signals = result[result['signal'] == 1]
        
        for buy_date in buy_signals.index:
            # 找到该买入信号后的卖出信号
            future_signals = result.loc[buy_date:]
            
            # 检查是否有卖出信号
            sell_signals = future_signals[future_signals['signal'] == -1]
            
            if sell_signals.empty:
                # 没有卖出信号，检查是否超过持有期限
                max_hold_date = buy_date + pd.Timedelta(days=holding_days)
                if max_hold_date in result.index:
                    result.loc[max_hold_date, 'signal'] = -1  # 强制卖出
        
        return result


class StrategyEngine:
    """
    策略引擎
    
    负责管理和执行多个策略，进行回测计算。
    """
    
    def __init__(self, strategies: List[SentimentStrategy]):
        """
        初始化策略引擎
        
        Args:
            strategies: 策略列表
        """
        self.strategies = strategies
        
    def run_backtest(self, sentiment_data: pd.DataFrame, 
                    market_data: pd.DataFrame,
                    index_data: Dict[str, pd.DataFrame],
                    initial_capital: float = 1000000,
                    transaction_cost: float = 0.001) -> Dict[str, pd.DataFrame]:
        """
        运行策略回测
        
        Args:
            sentiment_data: 情绪数据DataFrame
            market_data: 市场数据DataFrame
            index_data: 指数数据字典
            initial_capital: 初始资金
            transaction_cost: 交易成本比例
            
        Returns:
            Dict[str, pd.DataFrame]: 各策略的回测结果
        """
        results = {}
        
        for strategy in self.strategies:
            print(f"运行策略: {strategy.name}")
            
            # 生成交易信号
            signals = strategy.generate_signals(sentiment_data, market_data, index_data)
            
            # 计算策略绩效
            performance = self._calculate_performance(
                signals, sentiment_data, market_data, index_data,
                initial_capital, transaction_cost
            )
            
            results[strategy.name] = performance
            
        return results
        
    def _calculate_performance(self, signals: pd.DataFrame, 
                             sentiment_data: pd.DataFrame,
                             market_data: pd.DataFrame,
                             index_data: Dict[str, pd.DataFrame],
                             initial_capital: float,
                             transaction_cost: float) -> pd.DataFrame:
        """
        计算策略绩效
        
        Args:
            signals: 交易信号DataFrame
            sentiment_data: 情绪数据DataFrame
            market_data: 市场数据DataFrame
            index_data: 指数数据字典
            initial_capital: 初始资金
            transaction_cost: 交易成本比例
            
        Returns:
            pd.DataFrame: 包含绩效指标的DataFrame
        """
        # 这里简化实现，实际应该包含更复杂的绩效计算
        # 包括收益率、回撤、夏普比率等
        
        result = signals.copy()
        
        # 计算简单的收益率（这里需要根据实际的市场数据来计算）
        # 暂时使用情绪得分作为代理收益率
        sentiment_score = sentiment_data.get('sentiment_score', 0)
        
        # 计算策略收益率（简化版）
        strategy_returns = sentiment_score * result['position'] * 0.01  # 简化的收益率计算
        
        result['strategy_return'] = strategy_returns
        result['cumulative_return'] = (1 + strategy_returns).cumprod() - 1
        
        return result


def create_strategy(strategy_type: str, name: str = None, params: Dict[str, Any] = None) -> SentimentStrategy:
    """
    创建策略实例的工厂函数
    
    Args:
        strategy_type: 策略类型 ('ice_point', 'momentum', 'contrarian')
        name: 策略名称
        params: 策略参数
        
    Returns:
        SentimentStrategy: 策略实例
    """
    strategy_map = {
        'ice_point': IcePointStrategy,
        'momentum': SentimentMomentumStrategy,
        'contrarian': ContrarianStrategy
    }
    
    if strategy_type not in strategy_map:
        raise ValueError(f"Unknown strategy type: {strategy_type}")
    
    strategy_class = strategy_map[strategy_type]
    strategy_name = name or strategy_class.__name__
    
    return strategy_class(name=strategy_name, params=params or {})
