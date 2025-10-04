from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

try:
    import tushare as ts
except ImportError:
    ts = None


def download_tushare_data(
    start_date: str,
    end_date: str,
    output_dir: str | Path = "./data",
    *,
    token: Optional[str] = None,
    stock_list: Optional[list[str]] = None,
    save_format: str = "csv",
) -> Path:
    """
    使用tushare下载A股市场数据
    
    tushare是一个专业的金融数据接口库，提供高质量的A股数据。
    需要注册获取token才能使用。
    
    Args:
        start_date: 开始日期，格式为'YYYY-MM-DD'
        end_date: 结束日期，格式为'YYYY-MM-DD'
        output_dir: 输出目录路径
        token: tushare token，如果为None则尝试从环境变量获取
        stock_list: 股票代码列表，如果为None则下载所有A股
        save_format: 保存格式，目前支持'csv'
        
    Returns:
        Path: 保存数据的文件路径
        
    Raises:
        ImportError: 当tushare未安装时抛出
        ValueError: 当参数无效时抛出
    """
    if ts is None:
        raise ImportError(
            "tushare is required for data downloading. "
            "Install it with: pip install tushare"
        )
    
    # 设置token
    if token is None:
        import os
        token = os.getenv('TUSHARE_TOKEN')
        if not token:
            raise ValueError(
                "tushare token is required. "
                "Set TUSHARE_TOKEN environment variable or pass token parameter. "
                "Get token from: https://tushare.pro/register"
            )
    
    ts.set_token(token)
    pro = ts.pro_api()
    
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
            stock_info = pro.stock_basic(
                exchange='',
                list_status='L',
                fields='ts_code,symbol,name,area,industry,list_date'
            )
            stock_list = stock_info['ts_code'].tolist()
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
            df = pro.daily(
                ts_code=stock_code,
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                fields='ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount'
            )
            
            if not df.empty:
                # 标准化列名
                df = df.rename(columns={
                    'trade_date': 'trade_date',
                    'ts_code': 'ts_code',
                    'open': 'open',
                    'close': 'close',
                    'high': 'high',
                    'low': 'low',
                    'vol': 'vol',
                    'amount': 'amount',
                    'pct_chg': 'pct_chg',
                    'change': 'change',
                    'pre_close': 'pre_close',
                })
                
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
        filename = f"tushare_data_{start_date}_{end_date}.csv"
        file_path = output_path / filename
        combined_df.to_csv(file_path, index=False, encoding='utf-8')
        print(f"数据已保存到: {file_path}")
        print(f"共下载 {len(combined_df)} 条记录")
        
        if failed_stocks:
            print(f"下载失败的股票: {failed_stocks}")
        
        return file_path
    else:
        raise ValueError(f"不支持的保存格式: {save_format}")


def get_tushare_stock_list(token: Optional[str] = None) -> list[str]:
    """
    获取A股股票代码列表
    
    Args:
        token: tushare token，如果为None则尝试从环境变量获取
        
    Returns:
        list[str]: 股票代码列表
    """
    if ts is None:
        raise ImportError("tushare is required. Install it with: pip install tushare")
    
    if token is None:
        import os
        token = os.getenv('TUSHARE_TOKEN')
        if not token:
            raise ValueError("tushare token is required")
    
    ts.set_token(token)
    pro = ts.pro_api()
    
    try:
        stock_info = pro.stock_basic(
            exchange='',
            list_status='L',
            fields='ts_code'
        )
        return stock_info['ts_code'].tolist()
    except Exception as e:
        raise ValueError(f"获取股票列表失败: {e}")
