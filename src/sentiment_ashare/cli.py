from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from sentiment_ashare.config import SentimentConfig
from sentiment_ashare.providers import load_market_data
from sentiment_ashare.features import compute_basic_features
from sentiment_ashare.scoring import compute_sentiment_score


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
    
    # 数据下载命令
    download_parser = subparsers.add_parser('download', help='Download market data')
    download_parser.add_argument("--source", choices=['akshare', 'tushare'], default='akshare', 
                                help="Data source")
    download_parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    download_parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    download_parser.add_argument("--output-dir", default="./data", help="Output directory")
    download_parser.add_argument("--stocks", nargs='+', help="Stock codes to download (optional)")
    download_parser.add_argument("--token", help="Tushare token (required for tushare)")
    
    return parser.parse_args()


def _run_analysis(config_path: str, output_path: str) -> None:
    """
    运行情绪分析
    
    Args:
        config_path: 配置文件路径
        output_path: 输出文件路径
    """
    cfg = SentimentConfig.load(config_path)

    # 加载市场数据
    df = load_market_data(
        cfg.provider,
        universe_filter=cfg.universe_filter,
    )

    # 计算情绪特征
    feats = compute_basic_features(
        df,
        date_column=cfg.provider.date_column,
        symbol_column=cfg.provider.symbol_column,
    )

    # 生成综合情绪得分
    score = compute_sentiment_score(
        feats,
        weights=cfg.weights,
        rolling_window=cfg.rolling_window,
        date_column=cfg.provider.date_column,
    )

    # 保存结果
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    score.to_csv(out_path, index=False)
    print(f"Saved sentiment scores to {out_path}")


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
    
    支持两种模式：
    1. analyze: 运行情绪分析
    2. download: 下载市场数据
    """
    args = _parse_args()
    
    if args.command == 'analyze':
        _run_analysis(args.config, args.output)
    elif args.command == 'download':
        _download_data(args)
    else:
        print("Please specify a command: 'analyze' or 'download'")
        print("Use --help for more information.")


if __name__ == "__main__":
    main()


