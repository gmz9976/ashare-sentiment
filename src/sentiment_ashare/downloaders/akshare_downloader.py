from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

try:
    import akshare as ak
except ImportError:
    ak = None


def download_akshare_data(
    start_date: str,
    end_date: str,
    output_dir: str | Path = "./data",
    *,
    stock_list: Optional[list[str]] = None,
    market: str = "A股",
    save_format: str = "csv",
) -> Path:
    """
    使用akshare下载A股市场数据
    
    akshare是一个开源的金融数据接口库，提供免费的A股数据。
    支持下载股票基本信息、日线行情、复权数据等。
    
    Args:
        start_date: 开始日期，格式为'YYYY-MM-DD'
        end_date: 结束日期，格式为'YYYY-MM-DD'
        output_dir: 输出目录路径
        stock_list: 股票代码列表，如果为None则下载所有A股
        market: 市场类型，默认为'A股'
        save_format: 保存格式，目前支持'csv'
        
    Returns:
        Path: 保存数据的文件路径
        
    Raises:
        ImportError: 当akshare未安装时抛出
        ValueError: 当参数无效时抛出
    """
    if ak is None:
        raise ImportError(
            "akshare is required for data downloading. "
            "Install it with: pip install akshare"
        )
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 验证日期格式
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        if start_dt > end_dt:
            raise ValueError("start_date must be before end_date")
    except ValueError as e:
        raise ValueError(f"Invalid date format. Use YYYY-MM-DD: {e}")
    
    print(f"正在下载A股数据: {start_date} 到 {end_date}")
    
    # 获取股票列表
    if stock_list is None:
        print("获取A股股票列表...")
        try:
            # 获取A股股票基本信息
            stock_info = ak.stock_info_a_code_name()
            stock_list = stock_info['code'].tolist()
            print(f"找到 {len(stock_list)} 只A股股票")
        except Exception as e:
            raise ValueError(f"获取股票列表失败: {e}")
    
    # 下载每只股票的数据
    all_data = []
    failed_stocks = []
    
    for i, stock_code in enumerate(stock_list):
        try:
            print(f"下载 {stock_code} 数据... ({i+1}/{len(stock_list)})")
            
            # 下载日线数据
            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust="qfq"  # 前复权
            )
            
            if not df.empty:
                # 标准化列名
                df = df.rename(columns={
                    '日期': 'trade_date',
                    '股票代码': 'ts_code',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'vol',
                    '成交额': 'amount',
                    '涨跌幅': 'pct_chg',
                    '涨跌额': 'change',
                    '换手率': 'turnover',
                    '振幅': 'amplitude',
                    '量比': 'volume_ratio',
                    '市盈率-动态': 'pe',
                    '市净率': 'pb',
                })
                
                # 添加股票代码列
                df['ts_code'] = stock_code
                
                # 确保日期格式正确
                df['trade_date'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')
                
                all_data.append(df)
            else:
                print(f"  {stock_code}: 无数据")
                
        except Exception as e:
            print(f"  {stock_code}: 下载失败 - {e}")
            failed_stocks.append(stock_code)
            continue
    
    if not all_data:
        raise ValueError("没有成功下载任何数据")
    
    # 合并所有数据
    print("合并数据...")
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # 按日期和股票代码排序
    combined_df = combined_df.sort_values(['trade_date', 'ts_code'])
    
    # 保存数据
    if save_format.lower() == "csv":
        filename = f"akshare_data_{start_date}_{end_date}.csv"
        file_path = output_path / filename
        combined_df.to_csv(file_path, index=False, encoding='utf-8')
        print(f"数据已保存到: {file_path}")
        print(f"共下载 {len(combined_df)} 条记录")
        
        if failed_stocks:
            print(f"下载失败的股票: {failed_stocks}")
        
        return file_path
    else:
        raise ValueError(f"不支持的保存格式: {save_format}")


def get_akshare_stock_list() -> list[str]:
    """
    获取A股股票代码列表
    
    Returns:
        list[str]: 股票代码列表
    """
    if ak is None:
        raise ImportError("akshare is required. Install it with: pip install akshare")
    
    try:
        stock_info = ak.stock_info_a_code_name()
        return stock_info['code'].tolist()
    except Exception as e:
        raise ValueError(f"获取股票列表失败: {e}")
