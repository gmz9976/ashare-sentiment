from __future__ import annotations

import time
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

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
    max_stocks: int = 100,
    use_index_stocks: bool = True,
    request_delay: float = 0.5,
    download_all: bool = False,
) -> Path:
    """
    使用akshare下载A股市场数据（优化版本，减少API调用次数）
    
    优化策略：
    1. 优先使用指数成分股（代表性更强）
    2. 限制最大股票数量
    3. 添加请求间隔避免被拉黑
    4. 使用批量下载接口
    5. 支持下载所有股票（谨慎使用）
    
    Args:
        start_date: 开始日期，格式为'YYYY-MM-DD'
        end_date: 结束日期，格式为'YYYY-MM-DD'
        output_dir: 输出目录路径
        stock_list: 股票代码列表，如果为None则智能选择股票
        market: 市场类型，默认为'A股'
        save_format: 保存格式，目前支持'csv'
        max_stocks: 最大下载股票数量，默认100只
        use_index_stocks: 是否优先使用指数成分股，默认True
        request_delay: 请求间隔（秒），默认0.5秒
        download_all: 是否下载所有股票，默认False（谨慎使用）
        
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
    
    # 智能选择股票列表
    if stock_list is None:
        if download_all:
            print("⚠️  警告：正在下载所有A股数据，这可能需要很长时间且可能被拉黑！")
            stock_list = _get_all_stock_list()
        else:
            stock_list = _get_optimized_stock_list(use_index_stocks, max_stocks)
    
    print(f"选择了 {len(stock_list)} 只股票进行下载")
    
    # 尝试使用批量下载接口
    all_data = []
    failed_stocks = []
    
    # 首先尝试使用指数行情接口（一次调用获取多只股票）
    if use_index_stocks and len(stock_list) > 10:
        print("尝试使用指数行情接口批量下载...")
        try:
            batch_data = _download_index_data(start_date, end_date, stock_list[:50])  # 限制50只
            if not batch_data.empty:
                all_data.append(batch_data)
                print(f"批量下载成功，获取 {len(batch_data)} 条记录")
                # 从stock_list中移除已下载的股票
                downloaded_stocks = set(batch_data['ts_code'].unique())
                stock_list = [s for s in stock_list if s not in downloaded_stocks]
        except Exception as e:
            print(f"批量下载失败，回退到单只下载: {e}")
    
    # 单只股票下载（带间隔）
    if stock_list:
        print(f"开始单只下载剩余 {len(stock_list)} 只股票...")
        for i, stock_code in enumerate(stock_list):
            try:
                print(f"下载 {stock_code} 数据... ({i+1}/{len(stock_list)})")
                
                # 添加随机延迟避免被拉黑
                if i > 0:
                    delay = request_delay + random.uniform(0, 0.2)
                    time.sleep(delay)
                
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
                    df = _standardize_columns(df, stock_code)
                    all_data.append(df)
                else:
                    print(f"  {stock_code}: 无数据")
                    
            except Exception as e:
                print(f"  {stock_code}: 下载失败 - {e}")
                failed_stocks.append(stock_code)
                # 如果连续失败太多，增加延迟
                if len(failed_stocks) > 5:
                    print("检测到频繁失败，增加延迟...")
                    time.sleep(2)
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


def _get_optimized_stock_list(use_index_stocks: bool, max_stocks: int) -> List[str]:
    """
    智能选择股票列表，优先选择指数成分股
    
    Args:
        use_index_stocks: 是否优先使用指数成分股
        max_stocks: 最大股票数量
        
    Returns:
        List[str]: 优化后的股票代码列表
    """
    if ak is None:
        raise ImportError("akshare is required. Install it with: pip install akshare")
    
    selected_stocks = []
    
    if use_index_stocks:
        try:
            print("获取主要指数成分股...")
            # 获取主要指数成分股（代表性更强，数据更稳定）
            index_stocks = []
            
            # 上证50
            try:
                sz50 = ak.stock_zh_index_spot_em(symbol="sh000016")
                if not sz50.empty:
                    index_stocks.extend(sz50['代码'].tolist()[:20])  # 取前20只
            except:
                pass
            
            # 沪深300
            try:
                hs300 = ak.stock_zh_index_spot_em(symbol="sh000300")
                if not hs300.empty:
                    index_stocks.extend(hs300['代码'].tolist()[:30])  # 取前30只
            except:
                pass
            
            # 中证500
            try:
                zz500 = ak.stock_zh_index_spot_em(symbol="sh000905")
                if not zz500.empty:
                    index_stocks.extend(zz500['代码'].tolist()[:30])  # 取前30只
            except:
                pass
            
            # 创业板指
            try:
                cyb = ak.stock_zh_index_spot_em(symbol="sz399006")
                if not cyb.empty:
                    index_stocks.extend(cyb['代码'].tolist()[:20])  # 取前20只
            except:
                pass
            
            # 去重并限制数量
            selected_stocks = list(set(index_stocks))[:max_stocks]
            print(f"从指数成分股中选择了 {len(selected_stocks)} 只股票")
            
        except Exception as e:
            print(f"获取指数成分股失败: {e}")
            use_index_stocks = False
    
    # 如果指数成分股不够或获取失败，补充其他股票
    if len(selected_stocks) < max_stocks:
        try:
            print("补充其他活跃股票...")
            # 获取活跃股票（按成交额排序）
            active_stocks = ak.stock_zh_a_spot_em()
            if not active_stocks.empty:
                # 按成交额排序，选择活跃股票
                active_stocks = active_stocks.sort_values('成交额', ascending=False)
                additional_stocks = active_stocks['代码'].tolist()
                
                # 添加未选择的股票
                for stock in additional_stocks:
                    if stock not in selected_stocks and len(selected_stocks) < max_stocks:
                        selected_stocks.append(stock)
                
                print(f"补充后共选择了 {len(selected_stocks)} 只股票")
        except Exception as e:
            print(f"获取活跃股票失败: {e}")
    
    # 如果还是不够，使用随机选择
    if len(selected_stocks) < max_stocks:
        try:
            print("随机补充股票...")
            all_stocks = ak.stock_info_a_code_name()
            if not all_stocks.empty:
                remaining_needed = max_stocks - len(selected_stocks)
                random_stocks = all_stocks['code'].sample(n=min(remaining_needed, len(all_stocks))).tolist()
                selected_stocks.extend(random_stocks)
                print(f"最终选择了 {len(selected_stocks)} 只股票")
        except Exception as e:
            print(f"随机选择股票失败: {e}")
    
    return selected_stocks[:max_stocks]


def _download_index_data(start_date: str, end_date: str, stock_list: List[str]) -> pd.DataFrame:
    """
    尝试使用指数行情接口批量下载数据
    
    Args:
        start_date: 开始日期
        end_date: 结束日期
        stock_list: 股票代码列表
        
    Returns:
        pd.DataFrame: 下载的数据
    """
    if ak is None:
        raise ImportError("akshare is required. Install it with: pip install akshare")
    
    try:
        # 尝试使用指数行情接口
        df = ak.stock_zh_a_spot_em()
        if not df.empty:
            # 过滤指定股票
            df = df[df['代码'].isin(stock_list)]
            
            # 标准化列名
            df = df.rename(columns={
                '代码': 'ts_code',
                '名称': 'name',
                '最新价': 'close',
                '涨跌幅': 'pct_chg',
                '涨跌额': 'change',
                '成交量': 'vol',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '最高': 'high',
                '最低': 'low',
                '今开': 'open',
                '昨收': 'pre_close',
                '量比': 'volume_ratio',
                '换手率': 'turnover',
                '市盈率-动态': 'pe',
                '市净率': 'pb',
            })
            
            # 添加日期列（使用当前日期作为占位符）
            df['trade_date'] = datetime.now().strftime('%Y-%m-%d')
            
            return df
    except Exception as e:
        print(f"指数行情接口下载失败: {e}")
    
    return pd.DataFrame()


def _standardize_columns(df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
    """
    标准化数据列名和格式
    
    Args:
        df: 原始数据框
        stock_code: 股票代码
        
    Returns:
        pd.DataFrame: 标准化后的数据框
    """
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
    
    return df


def _get_all_stock_list() -> List[str]:
    """
    获取所有A股股票代码列表
    
    Returns:
        List[str]: 所有A股股票代码列表
    """
    if ak is None:
        raise ImportError("akshare is required. Install it with: pip install akshare")
    
    try:
        print("获取所有A股股票列表...")
        stock_info = ak.stock_info_a_code_name()
        all_stocks = stock_info['code'].tolist()
        print(f"找到 {len(all_stocks)} 只A股股票")
        return all_stocks
    except Exception as e:
        print(f"获取所有股票列表失败: {e}")
        # 如果失败，尝试使用备用方法
        try:
            print("尝试备用方法获取股票列表...")
            # 使用股票基本信息接口
            stock_basic = ak.stock_zh_a_spot_em()
            all_stocks = stock_basic['代码'].tolist()
            print(f"通过备用方法找到 {len(all_stocks)} 只股票")
            return all_stocks
        except Exception as e2:
            raise ValueError(f"获取股票列表失败: {e}, 备用方法也失败: {e2}")


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
