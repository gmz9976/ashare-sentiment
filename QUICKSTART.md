# 快速开始指南

## 🚀 5分钟快速上手

### 1. 安装项目
```bash
cd /Users/mingzhegao/ashare-sentiment
pip install -e .
```

### 2. 快速测试（推荐）
```bash
# 下载少量数据测试（20只股票，最近一个月）
ashare-sentiment download --source akshare --start-date 2024-11-01 --end-date 2024-11-30 --max-stocks 20 --delay 1.0
```

### 3. 配置分析
```bash
# 复制配置模板
cp example_config_download.yaml config.yaml
```

### 4. 运行情绪分析
```bash
# 运行分析
ashare-sentiment analyze config.yaml --output test_sentiment.csv

# 查看结果
head test_sentiment.csv
```

## 📊 生产环境使用

### 安全下载（推荐设置）
```bash
# 下载50只指数成分股，延迟1秒
ashare-sentiment download --source akshare --start-date 2024-01-01 --end-date 2024-12-31 --max-stocks 50 --delay 1.0
```

### 运行完整分析
```bash
# 使用下载的数据进行分析
ashare-sentiment analyze config.yaml --output sentiment_2024.csv
```

## ⚠️ 重要提醒

1. **避免被拉黑**：使用`--max-stocks 50`和`--delay 1.0`参数
2. **测试先行**：先用少量数据测试
3. **耐心等待**：下载需要时间，不要中断
4. **网络稳定**：确保网络连接稳定

## 🔧 参数说明

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `--max-stocks` | 最大下载股票数量 | 50-100 |
| `--delay` | 请求延迟（秒） | 1.0 |
| `--start-date` | 开始日期 | 2024-01-01 |
| `--end-date` | 结束日期 | 2024-12-31 |

## 📈 结果解读

生成的`sentiment.csv`包含：
- `trade_date`: 交易日期
- `sentiment_score`: 情绪得分

情绪得分含义：
- **正值**: 市场情绪偏乐观
- **负值**: 市场情绪偏悲观
- **绝对值越大**: 情绪越极端
