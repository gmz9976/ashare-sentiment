"""
回测报告生成器

生成详细的回测分析报告，包括图表、统计表格和HTML报告。
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import warnings

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
warnings.filterwarnings('ignore')


class BacktestReportGenerator:
    """
    回测报告生成器
    
    负责生成详细的回测分析报告，包括：
    - 绩效摘要表格
    - 可视化图表
    - HTML格式报告
    - JSON数据导出
    """
    
    def __init__(self, output_dir: str = "./backtest_reports"):
        """
        初始化报告生成器
        
        Args:
            output_dir: 报告输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # 设置图表样式
        sns.set_style("whitegrid")
        plt.style.use('default')
        
    def generate_comprehensive_report(self, backtest_results: Dict[str, Any], 
                                    sentiment_analysis: Dict[str, Any],
                                    config: Dict[str, Any]) -> str:
        """
        生成综合回测报告
        
        Args:
            backtest_results: 回测结果字典
            sentiment_analysis: 情绪分析结果字典
            config: 配置参数字典
            
        Returns:
            str: 报告文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        print("生成回测报告...")
        
        # 1. 生成绩效摘要
        performance_summary = self._generate_performance_summary(backtest_results)
        
        # 2. 生成情绪指标有效性分析
        sentiment_effectiveness = self._generate_sentiment_effectiveness_report(sentiment_analysis)
        
        # 3. 生成图表
        chart_files = self._generate_charts(backtest_results, sentiment_analysis)
        
        # 4. 生成HTML报告
        html_report_path = self._generate_html_report(
            performance_summary, sentiment_effectiveness, chart_files, config, timestamp
        )
        
        # 5. 保存JSON数据
        json_data_path = self._save_json_data(backtest_results, sentiment_analysis, config, timestamp)
        
        print(f"回测报告生成完成:")
        print(f"  HTML报告: {html_report_path}")
        print(f"  JSON数据: {json_data_path}")
        print(f"  图表文件: {len(chart_files)} 个")
        
        return html_report_path
        
    def _generate_performance_summary(self, backtest_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成绩效摘要
        
        Args:
            backtest_results: 回测结果字典
            
        Returns:
            Dict[str, Any]: 绩效摘要字典
        """
        summary = {}
        
        for strategy_name, results in backtest_results.items():
            if isinstance(results, dict) and 'performance_metrics' in results:
                metrics = results['performance_metrics']
                summary[strategy_name] = {
                    '总收益率': f"{metrics.get('total_return', 0):.2%}",
                    '年化收益率': f"{metrics.get('annual_return', 0):.2%}",
                    '年化波动率': f"{metrics.get('annual_volatility', 0):.2%}",
                    '夏普比率': f"{metrics.get('sharpe_ratio', 0):.3f}",
                    '索提诺比率': f"{metrics.get('sortino_ratio', 0):.3f}",
                    '最大回撤': f"{metrics.get('max_drawdown', 0):.2%}",
                    '卡尔玛比率': f"{metrics.get('calmar_ratio', 0):.3f}",
                    '胜率': f"{metrics.get('win_rate', 0):.2%}",
                    '盈亏比': f"{metrics.get('profit_loss_ratio', 0):.3f}",
                    '样本数量': f"{metrics.get('sample_size', 0):,}"
                }
                
                # 添加相关性分析
                if 'correlations' in results:
                    correlations = results['correlations']
                    summary[strategy_name]['指数相关性'] = {}
                    for index_name, corr_data in correlations.items():
                        summary[strategy_name]['指数相关性'][index_name] = {
                            '相关系数': f"{corr_data.get('correlation', 0):.3f}",
                            '显著性': '是' if corr_data.get('significant', False) else '否',
                            '样本数': f"{corr_data.get('sample_size', 0):,}"
                        }
        
        return summary
        
    def _generate_sentiment_effectiveness_report(self, sentiment_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成情绪指标有效性报告
        
        Args:
            sentiment_analysis: 情绪分析结果字典
            
        Returns:
            Dict[str, Any]: 情绪有效性报告字典
        """
        effectiveness = {}
        
        # 情绪得分与市场相关性
        if 'sentiment_market_correlation' in sentiment_analysis:
            corr_data = sentiment_analysis['sentiment_market_correlation']
            effectiveness['情绪市场相关性'] = {
                '相关系数': f"{corr_data.get('correlation', 0):.3f}",
                'P值': f"{corr_data.get('p_value', 1):.3f}",
                '显著性': '是' if corr_data.get('significant', False) else '否',
                '样本数': f"{corr_data.get('sample_size', 0):,}"
            }
        
        # 预测能力分析
        if 'sentiment_predictive_power' in sentiment_analysis:
            predictive = sentiment_analysis['sentiment_predictive_power']
            effectiveness['预测能力分析'] = {}
            
            # 滞后相关性
            if 'lag_correlations' in predictive:
                effectiveness['预测能力分析']['滞后相关性'] = {}
                for lag, lag_data in predictive['lag_correlations'].items():
                    effectiveness['预测能力分析']['滞后相关性'][lag] = {
                        '相关系数': f"{lag_data.get('correlation', 0):.3f}",
                        '显著性': '是' if lag_data.get('significant', False) else '否'
                    }
            
            # 高低情绪表现
            if 'high_sentiment_performance' in predictive:
                high_perf = predictive['high_sentiment_performance']
                effectiveness['预测能力分析']['高情绪表现'] = {
                    '平均收益率': f"{high_perf.get('mean_return', 0):.2%}",
                    '正收益比例': f"{high_perf.get('positive_rate', 0):.2%}",
                    '样本数': f"{high_perf.get('sample_size', 0):,}"
                }
            
            if 'low_sentiment_performance' in predictive:
                low_perf = predictive['low_sentiment_performance']
                effectiveness['预测能力分析']['低情绪表现'] = {
                    '平均收益率': f"{low_perf.get('mean_return', 0):.2%}",
                    '正收益比例': f"{low_perf.get('positive_rate', 0):.2%}",
                    '样本数': f"{low_perf.get('sample_size', 0):,}"
                }
        
        # 冰点信号分析
        if 'ice_point_analysis' in sentiment_analysis:
            ice_point = sentiment_analysis['ice_point_analysis']
            effectiveness['冰点信号分析'] = {
                '信号数量': f"{ice_point.get('count', 0):,}",
                '信号准确性': {}
            }
            
            if 'accuracy' in ice_point:
                for period, accuracy in ice_point['accuracy'].items():
                    effectiveness['冰点信号分析']['信号准确性'][f'{period}后表现'] = {
                        '平均收益率': f"{accuracy.get('mean_return', 0):.2%}",
                        '正收益比例': f"{accuracy.get('positive_rate', 0):.2%}",
                        '样本数': f"{accuracy.get('sample_size', 0):,}"
                    }
        
        # 转暖信号分析
        if 'warming_signal_analysis' in sentiment_analysis:
            warming = sentiment_analysis['warming_signal_analysis']
            effectiveness['转暖信号分析'] = {
                '信号数量': f"{warming.get('count', 0):,}",
                '信号准确性': {}
            }
            
            if 'accuracy' in warming:
                for period, accuracy in warming['accuracy'].items():
                    effectiveness['转暖信号分析']['信号准确性'][f'{period}后表现'] = {
                        '平均收益率': f"{accuracy.get('mean_return', 0):.2%}",
                        '正收益比例': f"{accuracy.get('positive_rate', 0):.2%}",
                        '样本数': f"{accuracy.get('sample_size', 0):,}"
                    }
        
        # 情绪状态分析
        if 'sentiment_state_analysis' in sentiment_analysis:
            state_analysis = sentiment_analysis['sentiment_state_analysis']
            effectiveness['情绪状态分析'] = {}
            
            for state, state_data in state_analysis.items():
                effectiveness['情绪状态分析'][state] = {
                    '平均收益率': f"{state_data.get('mean_return', 0):.2%}",
                    '波动率': f"{state_data.get('volatility', 0):.2%}",
                    '正收益比例': f"{state_data.get('positive_rate', 0):.2%}",
                    '样本数': f"{state_data.get('sample_size', 0):,}"
                }
        
        return effectiveness
        
    def _generate_charts(self, backtest_results: Dict[str, Any], 
                        sentiment_analysis: Dict[str, Any]) -> List[str]:
        """
        生成图表
        
        Args:
            backtest_results: 回测结果字典
            sentiment_analysis: 情绪分析结果字典
            
        Returns:
            List[str]: 图表文件路径列表
        """
        chart_files = []
        
        try:
            # 1. 累计收益率对比图
            chart_files.append(self._plot_cumulative_returns(backtest_results))
            
            # 2. 回撤对比图
            chart_files.append(self._plot_drawdowns(backtest_results))
            
            # 3. 情绪得分与市场表现散点图
            chart_files.append(self._plot_sentiment_correlation(sentiment_analysis))
            
            # 4. 冰点信号效果图
            chart_files.append(self._plot_ice_point_signals(sentiment_analysis))
            
            # 5. 情绪状态分布图
            chart_files.append(self._plot_sentiment_state_distribution(sentiment_analysis))
            
            # 6. 策略绩效对比雷达图
            chart_files.append(self._plot_performance_radar(backtest_results))
            
        except Exception as e:
            print(f"图表生成过程中出现错误: {e}")
            
        return chart_files
        
    def _plot_cumulative_returns(self, backtest_results: Dict[str, Any]) -> str:
        """
        绘制累计收益率对比图
        
        Args:
            backtest_results: 回测结果字典
            
        Returns:
            str: 图表文件路径
        """
        fig, ax = plt.subplots(figsize=(14, 8))
        
        colors = plt.cm.Set1(np.linspace(0, 1, len(backtest_results)))
        
        for i, (strategy_name, results) in enumerate(backtest_results.items()):
            if 'cumulative_returns' in results:
                cumulative_returns = results['cumulative_returns']
                ax.plot(cumulative_returns.index, 
                       cumulative_returns.values, 
                       label=f'{strategy_name} 策略', 
                       linewidth=2, 
                       color=colors[i])
        
        # 添加基准指数对比（如果有的话）
        if 'benchmarks' in backtest_results:
            for benchmark_name, benchmark_data in backtest_results['benchmarks'].items():
                if isinstance(benchmark_data, pd.Series):
                    ax.plot(benchmark_data.index, 
                           benchmark_data.values, 
                           label=f'{benchmark_name} 基准', 
                           linestyle='--', 
                           alpha=0.7)
        
        ax.set_title('策略累计收益率对比', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('累计收益率', fontsize=12)
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(True, alpha=0.3)
        
        # 格式化y轴为百分比
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.1%}'))
        
        plt.tight_layout()
        
        chart_path = self.output_dir / 'cumulative_returns.png'
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(chart_path)
        
    def _plot_drawdowns(self, backtest_results: Dict[str, Any]) -> str:
        """
        绘制回撤对比图
        
        Args:
            backtest_results: 回测结果字典
            
        Returns:
            str: 图表文件路径
        """
        fig, ax = plt.subplots(figsize=(14, 8))
        
        colors = plt.cm.Set1(np.linspace(0, 1, len(backtest_results)))
        
        for i, (strategy_name, results) in enumerate(backtest_results.items()):
            if 'drawdown' in results:
                drawdown = results['drawdown']
                ax.fill_between(drawdown.index, 
                               drawdown.values, 
                               0, 
                               alpha=0.3, 
                               label=f'{strategy_name} 回撤',
                               color=colors[i])
        
        ax.set_title('策略回撤对比', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('回撤', fontsize=12)
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(True, alpha=0.3)
        
        # 格式化y轴为百分比
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.1%}'))
        
        plt.tight_layout()
        
        chart_path = self.output_dir / 'drawdowns.png'
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(chart_path)
        
    def _plot_sentiment_correlation(self, sentiment_analysis: Dict[str, Any]) -> str:
        """
        绘制情绪得分与市场表现散点图
        
        Args:
            sentiment_analysis: 情绪分析结果字典
            
        Returns:
            str: 图表文件路径
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        
        # 如果有情绪数据，绘制散点图
        if 'sentiment_data' in sentiment_analysis:
            sentiment_data = sentiment_analysis['sentiment_data']
            if 'sentiment_score' in sentiment_data.columns and 'market_return' in sentiment_data.columns:
                # 散点图
                ax1.scatter(sentiment_data['sentiment_score'], 
                           sentiment_data['market_return'], 
                           alpha=0.6, 
                           s=30)
                
                # 添加趋势线
                z = np.polyfit(sentiment_data['sentiment_score'].dropna(), 
                              sentiment_data['market_return'].dropna(), 1)
                p = np.poly1d(z)
                ax1.plot(sentiment_data['sentiment_score'], 
                        p(sentiment_data['sentiment_score']), 
                        "r--", 
                        alpha=0.8)
                
                ax1.set_xlabel('情绪得分')
                ax1.set_ylabel('市场收益率')
                ax1.set_title('情绪得分与市场收益率关系')
                ax1.grid(True, alpha=0.3)
                
                # 相关性热力图
                correlation_data = []
                correlation_labels = []
                
                if 'sentiment_market_correlation' in sentiment_analysis:
                    corr_data = sentiment_analysis['sentiment_market_correlation']
                    correlation_data.append([corr_data.get('correlation', 0)])
                    correlation_labels.append('情绪-市场')
                
                if correlation_data:
                    sns.heatmap(correlation_data, 
                              annot=True, 
                              cmap='RdBu_r', 
                              center=0,
                              xticklabels=['相关系数'],
                              yticklabels=correlation_labels,
                              ax=ax2)
                    ax2.set_title('相关性分析')
        
        plt.tight_layout()
        
        chart_path = self.output_dir / 'sentiment_correlation.png'
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(chart_path)
        
    def _plot_ice_point_signals(self, sentiment_analysis: Dict[str, Any]) -> str:
        """
        绘制冰点信号效果图
        
        Args:
            sentiment_analysis: 情绪分析结果字典
            
        Returns:
            str: 图表文件路径
        """
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        
        # 冰点信号统计
        if 'ice_point_analysis' in sentiment_analysis:
            ice_point = sentiment_analysis['ice_point_analysis']
            
            if 'accuracy' in ice_point:
                periods = list(ice_point['accuracy'].keys())
                positive_rates = [ice_point['accuracy'][p].get('positive_rate', 0) for p in periods]
                mean_returns = [ice_point['accuracy'][p].get('mean_return', 0) for p in periods]
                
                # 正收益比例
                ax1.bar(periods, positive_rates, alpha=0.7, color='skyblue')
                ax1.set_title('冰点信号后各期间正收益比例', fontsize=14, fontweight='bold')
                ax1.set_ylabel('正收益比例')
                ax1.set_ylim(0, 1)
                ax1.grid(True, alpha=0.3)
                
                # 格式化y轴为百分比
                ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.1%}'))
                
                # 平均收益率
                colors = ['green' if x > 0 else 'red' for x in mean_returns]
                ax2.bar(periods, mean_returns, alpha=0.7, color=colors)
                ax2.set_title('冰点信号后各期间平均收益率', fontsize=14, fontweight='bold')
                ax2.set_ylabel('平均收益率')
                ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
                ax2.grid(True, alpha=0.3)
                
                # 格式化y轴为百分比
                ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.1%}'))
        
        plt.tight_layout()
        
        chart_path = self.output_dir / 'ice_point_signals.png'
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(chart_path)
        
    def _plot_sentiment_state_distribution(self, sentiment_analysis: Dict[str, Any]) -> str:
        """
        绘制情绪状态分布图
        
        Args:
            sentiment_analysis: 情绪分析结果字典
            
        Returns:
            str: 图表文件路径
        """
        fig, ax = plt.subplots(figsize=(12, 8))
        
        if 'sentiment_state_analysis' in sentiment_analysis:
            state_analysis = sentiment_analysis['sentiment_state_analysis']
            
            states = list(state_analysis.keys())
            mean_returns = [state_analysis[state].get('mean_return', 0) for state in states]
            
            # 创建条形图
            colors = ['green' if x > 0 else 'red' for x in mean_returns]
            bars = ax.bar(states, mean_returns, alpha=0.7, color=colors)
            
            ax.set_title('不同情绪状态下的平均收益率', fontsize=14, fontweight='bold')
            ax.set_ylabel('平均收益率')
            ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            ax.grid(True, alpha=0.3)
            
            # 格式化y轴为百分比
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.1%}'))
            
            # 旋转x轴标签
            plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        chart_path = self.output_dir / 'sentiment_state_distribution.png'
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(chart_path)
        
    def _plot_performance_radar(self, backtest_results: Dict[str, Any]) -> str:
        """
        绘制策略绩效对比雷达图
        
        Args:
            backtest_results: 回测结果字典
            
        Returns:
            str: 图表文件路径
        """
        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))
        
        # 定义绩效指标
        metrics = ['年化收益率', '夏普比率', '索提诺比率', '卡尔玛比率', '胜率', '盈亏比']
        n_metrics = len(metrics)
        
        # 计算角度
        angles = np.linspace(0, 2 * np.pi, n_metrics, endpoint=False).tolist()
        angles += angles[:1]  # 闭合图形
        
        colors = plt.cm.Set1(np.linspace(0, 1, len(backtest_results)))
        
        for i, (strategy_name, results) in enumerate(backtest_results.items()):
            if 'performance_metrics' in results:
                metrics_data = results['performance_metrics']
                
                # 提取指标值并标准化到0-1范围
                values = [
                    min(1.0, max(0.0, metrics_data.get('annual_return', 0) + 0.2)),  # 年化收益率
                    min(1.0, max(0.0, metrics_data.get('sharpe_ratio', 0) / 2.0)),   # 夏普比率
                    min(1.0, max(0.0, metrics_data.get('sortino_ratio', 0) / 2.0)),  # 索提诺比率
                    min(1.0, max(0.0, metrics_data.get('calmar_ratio', 0) / 2.0)),   # 卡尔玛比率
                    metrics_data.get('win_rate', 0),                                  # 胜率
                    min(1.0, max(0.0, metrics_data.get('profit_loss_ratio', 0) / 2.0))  # 盈亏比
                ]
                values += values[:1]  # 闭合图形
                
                ax.plot(angles, values, 'o-', linewidth=2, label=strategy_name, color=colors[i])
                ax.fill(angles, values, alpha=0.25, color=colors[i])
        
        # 设置标签
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(metrics)
        ax.set_ylim(0, 1)
        ax.set_title('策略绩效对比雷达图', size=16, fontweight='bold', pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
        ax.grid(True)
        
        plt.tight_layout()
        
        chart_path = self.output_dir / 'performance_radar.png'
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(chart_path)
        
    def _generate_html_report(self, performance_summary: Dict[str, Any], 
                            sentiment_effectiveness: Dict[str, Any],
                            chart_files: List[str],
                            config: Dict[str, Any], 
                            timestamp: str) -> str:
        """
        生成HTML格式的详细报告
        
        Args:
            performance_summary: 绩效摘要字典
            sentiment_effectiveness: 情绪有效性分析字典
            chart_files: 图表文件路径列表
            config: 配置参数字典
            timestamp: 时间戳
            
        Returns:
            str: HTML报告文件路径
        """
        # 生成图表HTML
        chart_html = ""
        for chart_file in chart_files:
            chart_name = Path(chart_file).name
            chart_html += f'<div class="chart-section"><h3>{chart_name.replace(".png", "").replace("_", " ").title()}</h3><img src="{chart_name}" alt="{chart_name}" style="max-width: 100%; height: auto;"></div>'
        
        # 生成绩效摘要表格
        performance_table = self._generate_performance_table_html(performance_summary)
        
        # 生成情绪有效性分析表格
        sentiment_table = self._generate_sentiment_table_html(sentiment_effectiveness)
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>A股情绪回测报告</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f4f4f4;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background-color: #fff;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                }}
                .chart-section {{
                    margin-bottom: 20px;
                    text-align: center;
                }}
                .chart-section img {{
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                }}
                .section {{
                    margin: 30px 0;
                    padding: 20px;
                    background-color: #f9f9f9;
                    border-radius: 5px;
                }}
                .section h2 {{
                    color: #333;
                    border-bottom: 2px solid #007bff;
                    padding-bottom: 10px;
                }}
                .metric {{
                    display: inline-block;
                    margin: 10px;
                    padding: 15px;
                    background-color: #e8f4f8;
                    border-radius: 5px;
                    border-left: 4px solid #007bff;
                }}
                .metric h4 {{
                    margin: 0 0 5px 0;
                    color: #007bff;
                }}
                .metric .value {{
                    font-size: 18px;
                    font-weight: bold;
                    color: #333;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 20px 0;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 12px;
                    text-align: left;
                }}
                th {{
                    background-color: #f2f2f2;
                    font-weight: bold;
                }}
                .positive {{
                    color: #28a745;
                    font-weight: bold;
                }}
                .negative {{
                    color: #dc3545;
                    font-weight: bold;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    border-radius: 8px;
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 2.5em;
                }}
                .summary-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 20px;
                    margin: 20px 0;
                }}
                .summary-card {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                    border-left: 4px solid #007bff;
                }}
                .summary-card h3 {{
                    margin-top: 0;
                    color: #007bff;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 A股市场情绪回测分析报告</h1>
                    <p style="font-size: 1.2em; margin: 10px 0;">回测期间: {config.get('start_date', '')} 至 {config.get('end_date', '')}</p>
                    <p>生成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}</p>
                    <p>初始资金: ¥{config.get('initial_capital', 0):,.0f} | 交易成本: {config.get('transaction_cost', 0):.3f}</p>
                </div>
                
                <div class="section">
                    <h2>📈 策略绩效摘要</h2>
                    {performance_table}
                </div>
                
                <div class="section">
                    <h2>🧠 情绪指标有效性分析</h2>
                    {sentiment_table}
                </div>
                
                <div class="section">
                    <h2>📊 图表分析</h2>
                    {chart_html}
                </div>
                
                <div class="section">
                    <h2>📋 配置信息</h2>
                    <div class="summary-grid">
                        <div class="summary-card">
                            <h3>回测参数</h3>
                            <p><strong>开始日期:</strong> {config.get('start_date', 'N/A')}</p>
                            <p><strong>结束日期:</strong> {config.get('end_date', 'N/A')}</p>
                            <p><strong>初始资金:</strong> ¥{config.get('initial_capital', 0):,.0f}</p>
                            <p><strong>交易成本:</strong> {config.get('transaction_cost', 0):.3f}</p>
                        </div>
                        <div class="summary-card">
                            <h3>策略配置</h3>
                            <p><strong>测试策略:</strong> {', '.join(config.get('strategies', []))}</p>
                            <p><strong>基准指数:</strong> {', '.join(config.get('benchmarks', []))}</p>
                            <p><strong>高级特征:</strong> {'是' if config.get('use_advanced_features', True) else '否'}</p>
                        </div>
                    </div>
                </div>
                
                <div class="section">
                    <h2>💡 分析结论</h2>
                    <div class="summary-card">
                        <h3>主要发现</h3>
                        <ul>
                            <li>本次回测涵盖了{config.get('start_date', '')}至{config.get('end_date', '')}期间的市场数据</li>
                            <li>测试了{len(config.get('strategies', []))}种不同的情绪策略</li>
                            <li>与{len(config.get('benchmarks', []))}个主要指数进行了对比分析</li>
                            <li>详细分析了情绪指标的有效性和预测能力</li>
                        </ul>
                        <p><strong>建议:</strong> 请结合具体的绩效指标和情绪分析结果，评估各策略的表现，并根据市场环境调整策略参数。</p>
                    </div>
                </div>
                
                <div style="text-align: center; margin-top: 40px; padding: 20px; background-color: #f8f9fa; border-radius: 5px;">
                    <p style="color: #6c757d; margin: 0;">
                        📊 报告由A股情绪回测系统自动生成 | 
                        🤖 技术支持: sentiment-ashare框架 |
                        ⏰ 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        report_path = self.output_dir / f'backtest_report_{timestamp}.html'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        return str(report_path)
        
    def _generate_performance_table_html(self, performance_summary: Dict[str, Any]) -> str:
        """
        生成绩效摘要表格HTML
        
        Args:
            performance_summary: 绩效摘要字典
            
        Returns:
            str: HTML表格字符串
        """
        if not performance_summary:
            return "<p>暂无绩效数据</p>"
        
        html = '<div class="summary-grid">'
        
        for strategy_name, metrics in performance_summary.items():
            html += f'''
            <div class="summary-card">
                <h3>{strategy_name}</h3>
                <table>
                    <tr><td>总收益率</td><td class="{'positive' if float(metrics.get('总收益率', '0%').rstrip('%')) > 0 else 'negative'}">{metrics.get('总收益率', 'N/A')}</td></tr>
                    <tr><td>年化收益率</td><td class="{'positive' if float(metrics.get('年化收益率', '0%').rstrip('%')) > 0 else 'negative'}">{metrics.get('年化收益率', 'N/A')}</td></tr>
                    <tr><td>年化波动率</td><td>{metrics.get('年化波动率', 'N/A')}</td></tr>
                    <tr><td>夏普比率</td><td class="{'positive' if float(metrics.get('夏普比率', '0')) > 0 else 'negative'}">{metrics.get('夏普比率', 'N/A')}</td></tr>
                    <tr><td>索提诺比率</td><td class="{'positive' if float(metrics.get('索提诺比率', '0')) > 0 else 'negative'}">{metrics.get('索提诺比率', 'N/A')}</td></tr>
                    <tr><td>最大回撤</td><td class="negative">{metrics.get('最大回撤', 'N/A')}</td></tr>
                    <tr><td>卡尔玛比率</td><td class="{'positive' if float(metrics.get('卡尔玛比率', '0')) > 0 else 'negative'}">{metrics.get('卡尔玛比率', 'N/A')}</td></tr>
                    <tr><td>胜率</td><td class="{'positive' if float(metrics.get('胜率', '0%').rstrip('%')) > 50 else 'negative'}">{metrics.get('胜率', 'N/A')}</td></tr>
                    <tr><td>盈亏比</td><td class="{'positive' if float(metrics.get('盈亏比', '0')) > 1 else 'negative'}">{metrics.get('盈亏比', 'N/A')}</td></tr>
                    <tr><td>样本数量</td><td>{metrics.get('样本数量', 'N/A')}</td></tr>
                </table>
            </div>
            '''
        
        html += '</div>'
        return html
        
    def _generate_sentiment_table_html(self, sentiment_effectiveness: Dict[str, Any]) -> str:
        """
        生成情绪有效性分析表格HTML
        
        Args:
            sentiment_effectiveness: 情绪有效性分析字典
            
        Returns:
            str: HTML表格字符串
        """
        if not sentiment_effectiveness:
            return "<p>暂无情绪分析数据</p>"
        
        html = '<div class="summary-grid">'
        
        # 情绪市场相关性
        if '情绪市场相关性' in sentiment_effectiveness:
            corr_data = sentiment_effectiveness['情绪市场相关性']
            html += f'''
            <div class="summary-card">
                <h3>情绪市场相关性</h3>
                <table>
                    <tr><td>相关系数</td><td class="{'positive' if float(corr_data.get('相关系数', '0')) > 0 else 'negative'}">{corr_data.get('相关系数', 'N/A')}</td></tr>
                    <tr><td>P值</td><td>{corr_data.get('P值', 'N/A')}</td></tr>
                    <tr><td>显著性</td><td class="{'positive' if corr_data.get('显著性') == '是' else 'negative'}">{corr_data.get('显著性', 'N/A')}</td></tr>
                    <tr><td>样本数</td><td>{corr_data.get('样本数', 'N/A')}</td></tr>
                </table>
            </div>
            '''
        
        # 冰点信号分析
        if '冰点信号分析' in sentiment_effectiveness:
            ice_point = sentiment_effectiveness['冰点信号分析']
            html += f'''
            <div class="summary-card">
                <h3>冰点信号分析</h3>
                <p><strong>信号数量:</strong> {ice_point.get('信号数量', 'N/A')}</p>
                <table>
                    <tr><th>期间</th><th>平均收益率</th><th>正收益比例</th><th>样本数</th></tr>
            '''
            
            if '信号准确性' in ice_point:
                for period, accuracy in ice_point['信号准确性'].items():
                    html += f'''
                    <tr>
                        <td>{period}</td>
                        <td class="{'positive' if float(accuracy.get('平均收益率', '0%').rstrip('%')) > 0 else 'negative'}">{accuracy.get('平均收益率', 'N/A')}</td>
                        <td class="{'positive' if float(accuracy.get('正收益比例', '0%').rstrip('%')) > 50 else 'negative'}">{accuracy.get('正收益比例', 'N/A')}</td>
                        <td>{accuracy.get('样本数', 'N/A')}</td>
                    </tr>
                    '''
            
            html += '</table></div>'
        
        # 转暖信号分析
        if '转暖信号分析' in sentiment_effectiveness:
            warming = sentiment_effectiveness['转暖信号分析']
            html += f'''
            <div class="summary-card">
                <h3>转暖信号分析</h3>
                <p><strong>信号数量:</strong> {warming.get('信号数量', 'N/A')}</p>
                <table>
                    <tr><th>期间</th><th>平均收益率</th><th>正收益比例</th><th>样本数</th></tr>
            '''
            
            if '信号准确性' in warming:
                for period, accuracy in warming['信号准确性'].items():
                    html += f'''
                    <tr>
                        <td>{period}</td>
                        <td class="{'positive' if float(accuracy.get('平均收益率', '0%').rstrip('%')) > 0 else 'negative'}">{accuracy.get('平均收益率', 'N/A')}</td>
                        <td class="{'positive' if float(accuracy.get('正收益比例', '0%').rstrip('%')) > 50 else 'negative'}">{accuracy.get('正收益比例', 'N/A')}</td>
                        <td>{accuracy.get('样本数', 'N/A')}</td>
                    </tr>
                    '''
            
            html += '</table></div>'
        
        html += '</div>'
        return html
        
    def _save_json_data(self, backtest_results: Dict[str, Any], 
                       sentiment_analysis: Dict[str, Any], 
                       config: Dict[str, Any], 
                       timestamp: str) -> str:
        """
        保存JSON格式的原始数据
        
        Args:
            backtest_results: 回测结果字典
            sentiment_analysis: 情绪分析结果字典
            config: 配置参数字典
            timestamp: 时间戳
            
        Returns:
            str: JSON文件路径
        """
        # 准备保存的数据
        save_data = {
            'timestamp': timestamp,
            'config': config,
            'backtest_results': {},
            'sentiment_analysis': sentiment_analysis
        }
        
        # 处理回测结果中的pandas对象
        for strategy_name, results in backtest_results.items():
            if isinstance(results, dict):
                processed_results = {}
                for key, value in results.items():
                    if isinstance(value, pd.Series):
                        processed_results[key] = {
                            'data': value.tolist(),
                            'index': value.index.tolist()
                        }
                    elif isinstance(value, pd.DataFrame):
                        processed_results[key] = {
                            'data': value.to_dict('records'),
                            'columns': value.columns.tolist()
                        }
                    else:
                        processed_results[key] = value
                save_data['backtest_results'][strategy_name] = processed_results
            else:
                save_data['backtest_results'][strategy_name] = results
        
        # 保存为JSON文件
        json_path = self.output_dir / f'backtest_data_{timestamp}.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2, default=str)
        
        return str(json_path)