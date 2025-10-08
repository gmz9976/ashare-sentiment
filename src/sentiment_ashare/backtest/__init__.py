"""
A股情绪回测模块

提供完整的回测功能，用于验证情绪指标的有效性并与主要指数进行对比分析。
"""

from .backtest_engine import BacktestEngine, BacktestConfig
from .data_manager import DataManager
from .strategy_engine import StrategyEngine, SentimentStrategy, IcePointStrategy, SentimentMomentumStrategy
from .performance_analyzer import PerformanceAnalyzer
from .report_generator import BacktestReportGenerator

__all__ = [
    'BacktestEngine',
    'BacktestConfig', 
    'DataManager',
    'StrategyEngine',
    'SentimentStrategy',
    'IcePointStrategy',
    'SentimentMomentumStrategy',
    'PerformanceAnalyzer',
    'BacktestReportGenerator',
]
