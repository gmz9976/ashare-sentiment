"""
主回测引擎

整合所有回测模块，提供完整的回测流程管理。
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from sentiment_ashare.config import SentimentConfig
from .data_manager import DataManager
from .strategy_engine import StrategyEngine, create_strategy
from .performance_analyzer import PerformanceAnalyzer
from .report_generator import BacktestReportGenerator


@dataclass
class BacktestConfig:
    """
    回测配置类
    
    包含回测所需的所有配置参数。
    """
    # 基础配置
    start_date: str
    end_date: str
    initial_capital: float = 1000000.0
    transaction_cost: float = 0.001
    
    # 策略配置
    strategies: List[str] = field(default_factory=lambda: ['ice_point', 'momentum'])
    strategy_params: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # 基准配置
    benchmarks: List[str] = field(default_factory=lambda: ['sh000001', 'sh000300', 'sh000905'])
    
    # 数据配置
    use_advanced_features: bool = True
    
    # 输出配置
    output_dir: str = "./backtest_reports"
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'BacktestConfig':
        """
        从字典创建配置对象
        
        Args:
            config_dict: 配置字典
            
        Returns:
            BacktestConfig: 配置对象
        """
        return cls(**config_dict)


class BacktestEngine:
    """
    主回测引擎
    
    整合所有回测模块，提供完整的回测流程管理。
    """
    
    def __init__(self, sentiment_config: SentimentConfig, backtest_config: BacktestConfig):
        """
        初始化回测引擎
        
        Args:
            sentiment_config: 情绪评分配置
            backtest_config: 回测配置
        """
        self.sentiment_config = sentiment_config
        self.backtest_config = backtest_config
        
        # 初始化各个模块
        self.data_manager = DataManager(sentiment_config)
        self.performance_analyzer = PerformanceAnalyzer()
        self.report_generator = BacktestReportGenerator(backtest_config.output_dir)
        
        # 初始化策略引擎
        strategies = self._initialize_strategies()
        self.strategy_engine = StrategyEngine(strategies)
        
    def _initialize_strategies(self) -> List:
        """
        初始化策略列表
        
        Returns:
            List: 策略对象列表
        """
        strategies = []
        
        for strategy_type in self.backtest_config.strategies:
            strategy_params = self.backtest_config.strategy_params.get(strategy_type, {})
            strategy = create_strategy(strategy_type, params=strategy_params)
            strategies.append(strategy)
            
        return strategies
        
    def run_backtest(self) -> Dict[str, Any]:
        """
        运行完整回测
        
        Returns:
            Dict[str, Any]: 回测结果字典
        """
        print("=" * 60)
        print("A股情绪回测系统启动")
        print("=" * 60)
        
        start_time = datetime.now()
        
        try:
            # 1. 加载数据
            print("\n1. 加载数据...")
            self._load_all_data()
            
            # 2. 数据对齐
            print("\n2. 数据对齐...")
            self._align_data()
            
            # 3. 运行策略回测
            print("\n3. 运行策略回测...")
            strategy_results = self._run_strategy_backtests()
            
            # 4. 绩效分析
            print("\n4. 进行绩效分析...")
            performance_results = self._analyze_performance(strategy_results)
            
            # 5. 情绪指标有效性分析
            print("\n5. 分析情绪指标有效性...")
            sentiment_effectiveness = self._analyze_sentiment_effectiveness()
            
            # 6. 生成报告
            print("\n6. 生成回测报告...")
            report_path = self._generate_reports(performance_results, sentiment_effectiveness)
            
            # 7. 汇总结果
            end_time = datetime.now()
            duration = end_time - start_time
            
            results = {
                'strategy_results': strategy_results,
                'performance_results': performance_results,
                'sentiment_effectiveness': sentiment_effectiveness,
                'report_path': report_path,
                'backtest_config': self.backtest_config,
                'duration': duration.total_seconds(),
                'start_time': start_time,
                'end_time': end_time
            }
            
            print("\n" + "=" * 60)
            print("回测完成!")
            print(f"耗时: {duration.total_seconds():.2f} 秒")
            print(f"报告路径: {report_path}")
            print("=" * 60)
            
            return results
            
        except Exception as e:
            print(f"\n回测过程中出现错误: {e}")
            raise
            
    def _load_all_data(self) -> None:
        """加载所有数据"""
        print("  加载市场数据...")
        self.data_manager.load_market_data(
            self.backtest_config.start_date,
            self.backtest_config.end_date
        )
        
        print("  加载指数数据...")
        self.data_manager.load_index_data(
            self.backtest_config.start_date,
            self.backtest_config.end_date
        )
        
        print("  计算情绪数据...")
        self.data_manager.load_sentiment_data(
            self.backtest_config.start_date,
            self.backtest_config.end_date,
            advanced=self.backtest_config.use_advanced_features
        )
        
    def _align_data(self) -> None:
        """对齐所有数据"""
        self.data_manager.align_data()
        
    def _run_strategy_backtests(self) -> Dict[str, pd.DataFrame]:
        """
        运行策略回测
        
        Returns:
            Dict[str, pd.DataFrame]: 策略回测结果
        """
        # 获取对齐后的数据
        market_data, index_data, sentiment_data = self.data_manager.aligned_data
        
        # 运行策略回测
        strategy_results = self.strategy_engine.run_backtest(
            sentiment_data=sentiment_data,
            market_data=market_data,
            index_data=index_data,
            initial_capital=self.backtest_config.initial_capital,
            transaction_cost=self.backtest_config.transaction_cost
        )
        
        # 添加基准数据
        benchmark_data = {}
        for benchmark_code in self.backtest_config.benchmarks:
            if benchmark_code in index_data:
                benchmark_returns = self.data_manager.get_index_returns(benchmark_code)
                benchmark_cumulative = (1 + benchmark_returns).cumprod() - 1
                benchmark_data[f"{benchmark_code}_基准"] = benchmark_cumulative
        
        strategy_results['benchmarks'] = benchmark_data
        
        return strategy_results
        
    def _analyze_performance(self, strategy_results: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        分析策略绩效
        
        Args:
            strategy_results: 策略回测结果
            
        Returns:
            Dict[str, Any]: 绩效分析结果
        """
        performance_results = {}
        
        # 获取市场收益率作为基准
        market_returns = self.data_manager.get_market_returns()
        
        # 获取基准指数收益率
        benchmark_returns = {}
        for benchmark_code in self.backtest_config.benchmarks:
            if benchmark_code in self.data_manager.index_data:
                benchmark_returns[f"{benchmark_code}_基准"] = self.data_manager.get_index_returns(benchmark_code)
        
        for strategy_name, results in strategy_results.items():
            if strategy_name == 'benchmarks':
                continue
                
            print(f"  分析策略: {strategy_name}")
            
            if 'strategy_return' in results:
                strategy_returns = results['strategy_return'].dropna()
                
                if len(strategy_returns) > 0:
                    # 计算绩效指标
                    performance_summary = self.performance_analyzer.generate_performance_summary(
                        strategy_returns, benchmark_returns
                    )
                    
                    performance_results[strategy_name] = {
                        'performance_metrics': performance_summary['performance_metrics'],
                        'correlations': performance_summary['correlations'],
                        'strategy_returns': strategy_returns,
                        'cumulative_returns': results.get('cumulative_return', pd.Series()),
                        'signals': results.get('signal', pd.Series()),
                        'positions': results.get('position', pd.Series())
                    }
        
        return performance_results
        
    def _analyze_sentiment_effectiveness(self) -> Dict[str, Any]:
        """
        分析情绪指标有效性
        
        Returns:
            Dict[str, Any]: 情绪指标有效性分析结果
        """
        # 获取情绪数据
        sentiment_data = self.data_manager.get_sentiment_series()
        
        # 获取市场收益率
        market_returns = self.data_manager.get_market_returns()
        
        # 进行情绪指标有效性分析
        sentiment_effectiveness = self.performance_analyzer.analyze_sentiment_effectiveness(
            sentiment_data, market_returns
        )
        
        # 添加原始数据供报告使用
        sentiment_effectiveness['sentiment_data'] = sentiment_data
        sentiment_effectiveness['market_returns'] = market_returns
        
        return sentiment_effectiveness
        
    def _generate_reports(self, performance_results: Dict[str, Any], 
                         sentiment_effectiveness: Dict[str, Any]) -> str:
        """
        生成回测报告
        
        Args:
            performance_results: 绩效分析结果
            sentiment_effectiveness: 情绪指标有效性分析结果
            
        Returns:
            str: 报告文件路径
        """
        # 准备配置信息
        config_info = {
            'start_date': self.backtest_config.start_date,
            'end_date': self.backtest_config.end_date,
            'initial_capital': self.backtest_config.initial_capital,
            'transaction_cost': self.backtest_config.transaction_cost,
            'strategies': self.backtest_config.strategies,
            'benchmarks': self.backtest_config.benchmarks,
            'use_advanced_features': self.backtest_config.use_advanced_features
        }
        
        # 生成综合报告
        report_path = self.report_generator.generate_comprehensive_report(
            backtest_results=performance_results,
            sentiment_analysis=sentiment_effectiveness,
            config=config_info
        )
        
        return report_path
        
    def get_backtest_summary(self, results: Dict[str, Any]) -> None:
        """
        打印回测摘要
        
        Args:
            results: 回测结果字典
        """
        print("\n" + "=" * 60)
        print("回测结果摘要")
        print("=" * 60)
        
        performance_results = results.get('performance_results', {})
        
        if not performance_results:
            print("没有可用的绩效结果")
            return
            
        print(f"\n回测期间: {self.backtest_config.start_date} 至 {self.backtest_config.end_date}")
        print(f"初始资金: {self.backtest_config.initial_capital:,.0f}")
        print(f"交易成本: {self.backtest_config.transaction_cost:.3f}")
        
        print(f"\n策略绩效对比:")
        print("-" * 60)
        
        # 创建对比表格
        summary_data = []
        for strategy_name, performance in performance_results.items():
            metrics = performance.get('performance_metrics', {})
            summary_data.append({
                '策略名称': strategy_name,
                '总收益率': f"{metrics.get('total_return', 0):.2%}",
                '年化收益率': f"{metrics.get('annual_return', 0):.2%}",
                '年化波动率': f"{metrics.get('annual_volatility', 0):.2%}",
                '夏普比率': f"{metrics.get('sharpe_ratio', 0):.3f}",
                '最大回撤': f"{metrics.get('max_drawdown', 0):.2%}",
                '胜率': f"{metrics.get('win_rate', 0):.2%}"
            })
        
        # 打印表格
        if summary_data:
            df_summary = pd.DataFrame(summary_data)
            print(df_summary.to_string(index=False))
        
        # 打印情绪指标有效性摘要
        sentiment_effectiveness = results.get('sentiment_effectiveness', {})
        if sentiment_effectiveness:
            print(f"\n情绪指标有效性摘要:")
            print("-" * 60)
            
            if 'sentiment_market_correlation' in sentiment_effectiveness:
                corr_data = sentiment_effectiveness['sentiment_market_correlation']
                print(f"情绪-市场相关性: {corr_data.get('correlation', 0):.3f}")
                print(f"显著性: {'是' if corr_data.get('significant', False) else '否'}")
            
            if 'ice_point_analysis' in sentiment_effectiveness:
                ice_point = sentiment_effectiveness['ice_point_analysis']
                print(f"冰点信号数量: {ice_point.get('count', 0)}")
                
                if 'accuracy' in ice_point and '1d' in ice_point['accuracy']:
                    accuracy_1d = ice_point['accuracy']['1d']
                    print(f"冰点信号1日后正收益比例: {accuracy_1d.get('positive_rate', 0):.2%}")
            
            if 'warming_signal_analysis' in sentiment_effectiveness:
                warming = sentiment_effectiveness['warming_signal_analysis']
                print(f"转暖信号数量: {warming.get('count', 0)}")
                
                if 'accuracy' in warming and '1d' in warming['accuracy']:
                    accuracy_1d = warming['accuracy']['1d']
                    print(f"转暖信号1日后正收益比例: {accuracy_1d.get('positive_rate', 0):.2%}")
        
        print("\n" + "=" * 60)
        
    def save_results(self, results: Dict[str, Any], output_path: str = None) -> str:
        """
        保存回测结果
        
        Args:
            results: 回测结果字典
            output_path: 输出文件路径
            
        Returns:
            str: 保存的文件路径
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.backtest_config.output_dir / f"backtest_results_{timestamp}.pkl"
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 保存为pickle文件
        import pickle
        with open(output_path, 'wb') as f:
            pickle.dump(results, f)
        
        print(f"回测结果已保存到: {output_path}")
        return str(output_path)
        
    def load_results(self, file_path: str) -> Dict[str, Any]:
        """
        加载回测结果
        
        Args:
            file_path: 结果文件路径
            
        Returns:
            Dict[str, Any]: 回测结果字典
        """
        import pickle
        with open(file_path, 'rb') as f:
            results = pickle.load(f)
        
        print(f"回测结果已从 {file_path} 加载")
        return results
