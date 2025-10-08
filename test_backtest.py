#!/usr/bin/env python3
"""
A股情绪回测系统测试脚本

用于测试回测系统的基本功能是否正常工作。
"""

import sys
import os
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """测试所有模块是否能正常导入"""
    print("测试模块导入...")
    
    try:
        from sentiment_ashare.backtest import (
            BacktestEngine, BacktestConfig, DataManager, 
            StrategyEngine, PerformanceAnalyzer, BacktestReportGenerator
        )
        print("✓ 回测模块导入成功")
    except ImportError as e:
        print(f"✗ 回测模块导入失败: {e}")
        return False
    
    try:
        from sentiment_ashare.backtest.strategy_engine import (
            SentimentStrategy, IcePointStrategy, 
            SentimentMomentumStrategy, ContrarianStrategy
        )
        print("✓ 策略模块导入成功")
    except ImportError as e:
        print(f"✗ 策略模块导入失败: {e}")
        return False
    
    return True

def test_config_creation():
    """测试配置对象创建"""
    print("\n测试配置对象创建...")
    
    try:
        from sentiment_ashare.backtest import BacktestConfig
        
        config_dict = {
            'start_date': '2020-01-01',
            'end_date': '2024-12-31',
            'initial_capital': 1000000,
            'strategies': ['ice_point', 'momentum'],
            'benchmarks': ['sh000001', 'sh000300']
        }
        
        config = BacktestConfig.from_dict(config_dict)
        print("✓ 回测配置创建成功")
        print(f"  - 开始日期: {config.start_date}")
        print(f"  - 结束日期: {config.end_date}")
        print(f"  - 初始资金: {config.initial_capital}")
        print(f"  - 策略数量: {len(config.strategies)}")
        print(f"  - 基准数量: {len(config.benchmarks)}")
        
        return True
    except Exception as e:
        print(f"✗ 配置创建失败: {e}")
        return False

def test_strategy_creation():
    """测试策略创建"""
    print("\n测试策略创建...")
    
    try:
        from sentiment_ashare.backtest.strategy_engine import create_strategy
        
        # 测试冰点策略
        ice_point_strategy = create_strategy('ice_point')
        print(f"✓ 冰点策略创建成功: {ice_point_strategy.name}")
        
        # 测试动量策略
        momentum_strategy = create_strategy('momentum')
        print(f"✓ 动量策略创建成功: {momentum_strategy.name}")
        
        # 测试逆向策略
        contrarian_strategy = create_strategy('contrarian')
        print(f"✓ 逆向策略创建成功: {contrarian_strategy.name}")
        
        return True
    except Exception as e:
        print(f"✗ 策略创建失败: {e}")
        return False

def test_performance_analyzer():
    """测试绩效分析器"""
    print("\n测试绩效分析器...")
    
    try:
        import pandas as pd
        import numpy as np
        from sentiment_ashare.backtest.performance_analyzer import PerformanceAnalyzer
        
        analyzer = PerformanceAnalyzer()
        
        # 创建测试数据
        dates = pd.date_range('2020-01-01', periods=100, freq='D')
        returns = pd.Series(np.random.normal(0.001, 0.02, 100), index=dates)
        
        # 测试基本指标计算
        annual_return = analyzer.calculate_annual_return(returns)
        sharpe_ratio = analyzer.calculate_sharpe_ratio(returns)
        volatility = analyzer.calculate_annual_volatility(returns)
        
        print(f"✓ 绩效分析器测试成功")
        print(f"  - 年化收益率: {annual_return:.2%}")
        print(f"  - 夏普比率: {sharpe_ratio:.3f}")
        print(f"  - 年化波动率: {volatility:.2%}")
        
        return True
    except Exception as e:
        print(f"✗ 绩效分析器测试失败: {e}")
        return False

def test_report_generator():
    """测试报告生成器"""
    print("\n测试报告生成器...")
    
    try:
        from sentiment_ashare.backtest.report_generator import BacktestReportGenerator
        
        # 创建报告生成器
        generator = BacktestReportGenerator("./test_reports")
        print("✓ 报告生成器创建成功")
        
        # 测试报告目录创建
        if generator.output_dir.exists():
            print("✓ 报告目录创建成功")
        
        return True
    except Exception as e:
        print(f"✗ 报告生成器测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("A股情绪回测系统测试")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_config_creation,
        test_strategy_creation,
        test_performance_analyzer,
        test_report_generator
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！回测系统准备就绪。")
        print("\n使用示例:")
        print("ashare-sentiment backtest backtest_config.yaml \\")
        print("  --start-date 2020-01-01 \\")
        print("  --end-date 2024-12-31 \\")
        print("  --summary")
    else:
        print("❌ 部分测试失败，请检查依赖库安装和代码配置。")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
