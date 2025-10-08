from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from sentiment_ashare.config import SentimentConfig
from sentiment_ashare.providers import load_market_data
from sentiment_ashare.features import compute_basic_features, compute_advanced_sentiment_features
from sentiment_ashare.scoring import compute_sentiment_score, get_detailed_sentiment_analysis


def _parse_args() -> argparse.Namespace:
    """
    解析命令行参数
    
    Returns:
        argparse.Namespace: 解析后的命令行参数对象
    """
    parser = argparse.ArgumentParser(description="A-share sentiment analysis tools")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # 情绪分析命令
    analyze_parser = subparsers.add_parser('analyze', help='Run sentiment analysis')
    analyze_parser.add_argument("config", type=str, help="Path to YAML config file")
    analyze_parser.add_argument("--output", type=str, default="sentiment.csv", help="Output CSV path")
    analyze_parser.add_argument("--advanced", action='store_true', help="Use advanced sentiment features")
    analyze_parser.add_argument("--analysis", action='store_true', help="Generate detailed analysis report")
    
    # 数据下载命令
    download_parser = subparsers.add_parser('download', help='Download market data')
    download_parser.add_argument("--source", choices=['akshare', 'tushare'], default='akshare', 
                                help="Data source")
    download_parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    download_parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    download_parser.add_argument("--output-dir", default="./data", help="Output directory")
    download_parser.add_argument("--stocks", nargs='+', help="Stock codes to download (optional)")
    download_parser.add_argument("--token", help="Tushare token (required for tushare)")
    download_parser.add_argument("--max-stocks", type=int, default=100, 
                                help="Maximum number of stocks to download (default: 100)")
    download_parser.add_argument("--use-index", action='store_true', default=True,
                                help="Use index component stocks (default: True)")
    download_parser.add_argument("--delay", type=float, default=0.5,
                                help="Request delay in seconds (default: 0.5)")
    download_parser.add_argument("--all", action='store_true',
                                help="Download all stocks (WARNING: may take hours and risk IP ban)")
    
    # 回测命令
    backtest_parser = subparsers.add_parser('backtest', help='Run sentiment backtest')
    backtest_parser.add_argument("config", type=str, help="Path to YAML config file")
    backtest_parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    backtest_parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    backtest_parser.add_argument("--output-dir", default="./backtest_reports", help="Output directory")
    backtest_parser.add_argument("--strategies", nargs='+', default=['ice_point', 'momentum'], 
                               help="Strategies to test (ice_point, momentum, contrarian)")
    backtest_parser.add_argument("--benchmarks", nargs='+', 
                               default=['sh000001', 'sh000300', 'sh000905'],
                               help="Benchmark indices")
    backtest_parser.add_argument("--initial-capital", type=float, default=1000000,
                               help="Initial capital (default: 1000000)")
    backtest_parser.add_argument("--transaction-cost", type=float, default=0.001,
                               help="Transaction cost rate (default: 0.001)")
    backtest_parser.add_argument("--advanced", action='store_true', default=True,
                               help="Use advanced sentiment features (default: True)")
    backtest_parser.add_argument("--summary", action='store_true',
                               help="Print backtest summary")
    
    return parser.parse_args()


def _run_analysis(config_path: str, output_path: str, advanced: bool = False, analysis: bool = False) -> None:
    """
    运行情绪分析
    
    Args:
        config_path: 配置文件路径
        output_path: 输出文件路径
        advanced: 是否使用高级特征
        analysis: 是否生成详细分析报告
    """
    cfg = SentimentConfig.load(config_path)

    # 加载市场数据
    df = load_market_data(
        cfg.provider,
        universe_filter=cfg.universe_filter,
    )

    # 计算情绪特征
    if advanced:
        print("使用高级情绪特征计算...")
        feats = compute_advanced_sentiment_features(
            df,
            date_column=cfg.provider.date_column,
            symbol_column=cfg.provider.symbol_column,
        )
    else:
        print("使用基础情绪特征计算...")
        feats = compute_basic_features(
            df,
            date_column=cfg.provider.date_column,
            symbol_column=cfg.provider.symbol_column,
        )

    # 生成综合情绪得分和状态分类
    score = compute_sentiment_score(
        feats,
        weights=cfg.weights,
        rolling_window=cfg.rolling_window,
        date_column=cfg.provider.date_column,
        enable_classification=True,
    )

    # 保存结果
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    score.to_csv(out_path, index=False)
    print(f"Saved sentiment analysis to {out_path}")
    
    # 显示最新状态
    if len(score) > 0:
        latest = score.iloc[-1]
        print(f"\n最新市场情绪状态:")
        print(f"  日期: {latest[cfg.provider.date_column]}")
        print(f"  情绪得分: {latest['sentiment_score']:.3f}")
        print(f"  情绪状态: {latest['sentiment_state']}")
        if latest.get('is_ice_point', False):
            print(f"  🧊 冰点信号: 是")
        if latest.get('warming_signal', False):
            print(f"  🔥 转暖信号: 是")
    
    # 生成详细分析报告
    if analysis:
        print("\n生成详细分析报告...")
        analysis_report = get_detailed_sentiment_analysis(
            feats,
            date_column=cfg.provider.date_column,
        )
        
        print(f"\n📊 详细分析报告:")
        print(f"  当前状态: {analysis_report.get('current_state', '未知')}")
        print(f"  冰点信号: {'是' if analysis_report.get('is_ice_point', False) else '否'}")
        print(f"  转暖信号: {'是' if analysis_report.get('warming_signal', False) else '否'}")
        
        key_metrics = analysis_report.get('key_metrics', {})
        print(f"\n📈 关键指标:")
        for metric, value in key_metrics.items():
            if isinstance(value, (int, float)):
                print(f"  {metric}: {value:.3f}")
        
        recommendations = analysis_report.get('recommendations', [])
        if recommendations:
            print(f"\n💡 投资建议:")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")
        
        # 保存分析报告
        report_path = out_path.parent / f"analysis_report_{out_path.stem}.json"
        import json
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(analysis_report, f, ensure_ascii=False, indent=2)
        print(f"\n分析报告已保存到: {report_path}")


def _download_data(args) -> None:
    """
    下载市场数据
    
    Args:
        args: 命令行参数
    """
    from sentiment_ashare.downloaders import download_akshare_data, download_tushare_data
    
    if args.source == 'akshare':
        download_akshare_data(
            start_date=args.start_date,
            end_date=args.end_date,
            output_dir=args.output_dir,
            stock_list=args.stocks,
            max_stocks=args.max_stocks,
            use_index_stocks=args.use_index,
            request_delay=args.delay,
        download_all=args.all,
    )


def _run_backtest(args) -> None:
    """
    运行回测
    
    Args:
        args: 命令行参数
    """
    from sentiment_ashare.backtest import BacktestEngine, BacktestConfig
    
    # 加载情绪评分配置
    sentiment_config = SentimentConfig.load(args.config)
    
    # 创建回测配置
    backtest_config_dict = {
        'start_date': args.start_date,
        'end_date': args.end_date,
        'initial_capital': args.initial_capital,
        'transaction_cost': args.transaction_cost,
        'strategies': args.strategies,
        'benchmarks': args.benchmarks,
        'use_advanced_features': args.advanced,
        'output_dir': args.output_dir
    }
    
    backtest_config = BacktestConfig.from_dict(backtest_config_dict)
    
    # 创建并运行回测引擎
    engine = BacktestEngine(sentiment_config, backtest_config)
    results = engine.run_backtest()
    
    # 打印摘要
    if args.summary:
        engine.get_backtest_summary(results)
    
    print(f"\n回测完成！详细报告请查看: {results['report_path']}")


def _download_data(args) -> None:
    """
    下载市场数据
    
    Args:
        args: 命令行参数
    """
    from sentiment_ashare.downloaders import download_akshare_data, download_tushare_data
    
    if args.source == 'akshare':
        download_akshare_data(
            start_date=args.start_date,
            end_date=args.end_date,
            output_dir=args.output_dir,
            stock_list=args.stocks,
            max_stocks=args.max_stocks,
            use_index_stocks=args.use_index,
            request_delay=args.delay,
            download_all=args.all,
        )
    elif args.source == 'tushare':
        if not args.token:
            print("Error: Tushare token is required. Use --token parameter or set TUSHARE_TOKEN environment variable.")
            return
        download_tushare_data(
            start_date=args.start_date,
            end_date=args.end_date,
            output_dir=args.output_dir,
            token=args.token,
            stock_list=args.stocks,
        )


def main() -> None:
    """
    A股情绪分析工具主程序入口
    
    支持三种模式：
    1. analyze: 运行情绪分析
    2. download: 下载市场数据
    3. backtest: 运行回测分析
    """
    args = _parse_args()
    
    if args.command == 'analyze':
        _run_analysis(args.config, args.output, args.advanced, args.analysis)
    elif args.command == 'download':
        _download_data(args)
    elif args.command == 'backtest':
        _run_backtest(args)
    else:
        print("Please specify a command: 'analyze', 'download', or 'backtest'")
        print("Use --help for more information.")


if __name__ == "__main__":
    main()


