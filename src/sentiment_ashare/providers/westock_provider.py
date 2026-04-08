from __future__ import annotations

import json
import logging
import subprocess
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

from sentiment_ashare.config import WeStockConfig

logger = logging.getLogger(__name__)


class WeStockError(Exception):
    """WeStock 基础异常"""
    pass


class WeStockCLIError(WeStockError):
    """CLI 调用失败"""
    def __init__(self, cmd: str, returncode: int, stderr: str):
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"CLI failed (code={returncode}): {cmd}\n{stderr}")


class WeStockParseError(WeStockError):
    """数据解析失败"""
    pass


class WeStockProvider:
    """
    基于 westock-data CLI 的市场数据提供者
    
    返回的 DataFrame 包含 market-level 聚合数据（每行一天），
    专供 WeStockFeatureCalculator 使用。
    
    输出 DataFrame 列：
      trade_date, total_stocks, advancing, declining, unchanged,
      limit_up, limit_down, range_gt7, range_5_7, range_2_5, range_0_2,
      range_n2_0, range_n5_n2, range_n7_n5, range_lt_n7,
      index_close, index_pct_chg, turnover_value, main_net_flow,
      index_high, index_low, index_open
    """
    
    def __init__(self, config: WeStockConfig) -> None:
        self.config = config
        # 解析 cli_path，支持 "node /path/to/script.js" 形式
        parts = config.cli_path.split(" ", 1)
        self._node = parts[0]  # "node"
        self._script = parts[1] if len(parts) > 1 else ""
        
        self._cache_dir: Optional[Path] = None
        if config.cache_dir:
            self._cache_dir = Path(config.cache_dir)
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            (self._cache_dir / "changedist").mkdir(exist_ok=True)
            (self._cache_dir / "market").mkdir(exist_ok=True)
    
    def fetch(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取指定日期范围的市场聚合数据
        
        Returns:
            pd.DataFrame 包含每日市场聚合行情
        """
        s = start_date or self.config.start_date
        e = end_date or self.config.end_date
        
        logger.info(f"Fetching WeStock market data: {s} ~ {e}")
        
        # Step 1: 获取主指数历史行情（用于交易日历 + 量能数据）
        primary_index = self.config.index_codes[0] if self.config.index_codes else "sh000001"
        market_list = self._call_market_range(primary_index, s, e)
        
        # 构建以 date 为键的 market 字典
        market_by_date: dict[str, dict] = {}
        for item in market_list:
            d = item.get("date") or item.get("time", "")
            if d:
                # 有些返回格式带时间，截取日期部分
                d = str(d)[:10]
                market_by_date[d] = item
        
        trading_dates = sorted(market_by_date.keys())
        logger.info(f"Found {len(trading_dates)} trading days")
        
        if not trading_dates:
            logger.warning("No trading dates found, returning empty DataFrame")
            return pd.DataFrame()
        
        # Step 2: 逐日获取 changedist 数据
        # 注意：changedist 仅支持当日数据，历史日期会返回 None
        # 历史日期的涨跌停分布字段将设为 NaN（由 compute_westock_features 处理）
        changedist_by_date: dict[str, dict] = {}
        
        # 先尝试获取当日 changedist（不耗时）
        from datetime import date as date_type
        today_str = date_type.today().isoformat()
        if today_str in trading_dates:
            cd_today = self._call_changedist(today_str)
            if cd_today is not None:
                changedist_by_date[today_str] = cd_today
        
        # 对其他日期，逐日尝试（有缓存的走缓存，否则跳过）
        for td in trading_dates:
            if td == today_str:
                continue
            # 只走缓存，不发起无效的 CLI 调用
            cache_key = f"changedist/{td}"
            cached = self._load_cache(cache_key)
            if cached is not None:
                changedist_by_date[td] = cached
        
        changedist_available = len(changedist_by_date)
        logger.info(
            f"changedist data available for {changedist_available}/{len(trading_dates)} days "
            f"(changedist only supports current-day data; historical data requires cache)"
        )
        
        # Step 3: 构建每日记录（market 数据 + changedist 数据）
        records = []
        for td in trading_dates:
            row: dict = {"trade_date": td}
            
            # 合并 market 数据
            mrow = market_by_date.get(td, {})
            row["index_close"] = mrow.get("closePrice") or mrow.get("close") or mrow.get("last")
            row["index_pct_chg"] = mrow.get("changePct") or mrow.get("change") or mrow.get("pctChg")
            row["turnover_value"] = mrow.get("turnoverValue") or mrow.get("amount") or mrow.get("turnover")
            row["main_net_flow"] = mrow.get("mainNetFlow") or mrow.get("mainNetInflow")
            row["index_high"] = mrow.get("highPrice") or mrow.get("high")
            row["index_low"] = mrow.get("lowPrice") or mrow.get("low")
            row["index_open"] = mrow.get("openPrice") or mrow.get("open")
            
            # 合并 changedist 数据（若无，设为 NaN）
            cd_data = changedist_by_date.get(td)
            if cd_data is not None:
                row["total_stocks"] = cd_data.get("totalStocks", 0)
                row["advancing"] = cd_data.get("advancing", 0)
                row["declining"] = cd_data.get("declining", 0)
                row["unchanged"] = cd_data.get("unchanged", 0)
                row["limit_up"] = cd_data.get("limitUp", 0)
                row["limit_down"] = cd_data.get("limitDown", 0)
                ranges_data = cd_data.get("ranges", [])
                row.update(self._parse_ranges(ranges_data))
            else:
                # 无 changedist 数据，设为 NaN（特征计算时会处理）
                for col in ["total_stocks", "advancing", "declining", "unchanged",
                            "limit_up", "limit_down", "range_gt7", "range_5_7",
                            "range_2_5", "range_0_2", "range_n2_0", "range_n5_n2",
                            "range_n7_n5", "range_lt_n7"]:
                    row[col] = float("nan")
            
            records.append(row)
        
        if not records:
            return pd.DataFrame()
        
        df = pd.DataFrame(records)
        
        # 类型转换
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        
        # changedist 整型字段：若有 NaN（历史日期无数据），保留为 float NaN
        # 使用 float64 以便 NaN 与实际计数共存（下游特征计算已处理 NaN）
        int_as_float_cols = ["total_stocks", "advancing", "declining", "unchanged",
                    "limit_up", "limit_down", "range_gt7", "range_5_7",
                    "range_2_5", "range_0_2", "range_n2_0", "range_n5_n2",
                    "range_n7_n5", "range_lt_n7"]
        for col in int_as_float_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")  # NaN stays NaN
        
        float_cols = ["index_close", "index_pct_chg", "turnover_value", 
                      "main_net_flow", "index_high", "index_low", "index_open"]
        for col in float_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        df = df.sort_values("trade_date").reset_index(drop=True)
        
        logger.info(f"WeStockProvider.fetch() returned {len(df)} rows")
        return df
    
    def _call_cli(self, *args: str) -> dict:
        """
        调用 westock-data CLI 并解析 JSON 输出
        """
        if self._script:
            cmd = [self._node, self._script, *args]
        else:
            cmd = [self._node, *args]
        
        cmd_str = " ".join(cmd)
        logger.debug(f"Running CLI: {cmd_str}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
                encoding="utf-8",
            )
        except subprocess.TimeoutExpired:
            raise WeStockCLIError(cmd_str, -1, "Timeout expired")
        except Exception as e:
            raise WeStockCLIError(cmd_str, -1, str(e))
        
        if result.returncode != 0:
            raise WeStockCLIError(cmd_str, result.returncode, result.stderr)
        
        if not result.stdout.strip():
            raise WeStockCLIError(cmd_str, result.returncode, "Empty stdout")
        
        return self._extract_json_from_output(result.stdout)
    
    def _call_cli_with_retry(self, *args: str) -> dict:
        """带重试的 CLI 调用（指数退避）"""
        last_error: Optional[Exception] = None
        for attempt in range(self.config.retry_count):
            try:
                return self._call_cli(*args)
            except (WeStockCLIError, WeStockParseError) as e:
                last_error = e
                if attempt < self.config.retry_count - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        f"CLI attempt {attempt + 1}/{self.config.retry_count} failed, "
                        f"retrying in {wait}s: {e}"
                    )
                    time.sleep(wait)
        raise last_error  # type: ignore[misc]
    
    def _call_changedist(self, trade_date: str) -> Optional[dict]:
        """
        调用 changedist 命令获取单日涨跌区间数据
        
        注意：westock-data changedist 命令不支持历史日期查询，
        无论传入哪个日期，始终返回最新交易日的数据。
        
        Returns:
            dict | None: changedist data 字段，若请求日期与返回日期不符则返回 None
        """
        cache_key = f"changedist/{trade_date}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached
        
        try:
            response = self._call_cli_with_retry("changedist", self.config.market, trade_date)
        except WeStockError as e:
            logger.warning(f"changedist failed for {trade_date}: {e}")
            return None
        
        # 提取 data 字段
        if not response.get("success"):
            logger.warning(f"changedist returned success=false for {trade_date}")
            return None
        
        data = response.get("data", response)
        
        # 检查返回的 date 是否与请求日期一致（历史日期支持检测）
        returned_date = data.get("date", "")
        if returned_date and returned_date[:10] != trade_date:
            # changedist 不支持历史查询，返回的是当日数据而非请求的历史数据
            # 只缓存当日数据（以返回的实际日期为 key）
            actual_date = returned_date[:10]
            logger.debug(
                f"changedist: requested {trade_date} but received {actual_date} "
                "(changedist does not support historical queries)"
            )
            # 缓存当日实际数据（避免重复调用）
            self._save_cache(f"changedist/{actual_date}", data)
            # 对历史日期请求返回 None：无历史数据可用
            return None
        
        self._save_cache(cache_key, data)
        return data
    
    def _call_market_range(self, index_code: str, start_date: str, end_date: str) -> list[dict]:
        """
        调用 market 命令获取指数历史区间行情
        
        Returns:
            list[dict]: 每日行情列表
        """
        cache_key = f"market/{index_code}_{start_date}_{end_date}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            if isinstance(cached, list):
                return cached
            # 缓存是 dict，里面可能有 history 字段
            if isinstance(cached, dict):
                return cached.get("history", [cached])
        
        try:
            response = self._call_cli_with_retry("market", index_code, start_date, end_date)
        except WeStockError as e:
            logger.warning(f"market range failed: {e}")
            return []
        
        if not response.get("success"):
            return []
        
        data = response.get("data", {})
        
        # market 区间查询真实返回结构（实测）：
        # {"success": true, "data": {"code": "sh000001", "name": "上证指数", "items": [...]}}
        # 兼容历史可能的格式：data[index_code].history[], data.history[], data 是 list
        history = []
        if isinstance(data, dict):
            # 优先：实测格式 data.items[]
            if "items" in data:
                history = data["items"]
            # 次选：data[index_code].history[]
            elif index_code in data:
                index_data = data[index_code]
                if isinstance(index_data, dict):
                    history = index_data.get("history", index_data.get("items", []))
                elif isinstance(index_data, list):
                    history = index_data
            # 再次选：data.history[]
            elif "history" in data:
                history = data["history"]
            else:
                # 最后：把 data 本身当列表（兼容单日格式）
                logger.warning(
                    f"market range: unexpected data structure for {index_code}, "
                    f"keys={list(data.keys())}"
                )
        elif isinstance(data, list):
            history = data
        
        self._save_cache(cache_key, history)
        return history
    
    def _parse_ranges(self, ranges: list[dict]) -> dict[str, int]:
        """
        解析 changedist.ranges 数组为扁平字段
        
        westock-data changedist 返回 11 个区间：
        涨停、>7%、5-7%、2-5%、0-2%、平、0~-2%、-2~-5%、-5~-7%、<-7%、跌停
        
        实测 JSON 结构：每个区间含 label(str)、count(int)、min(int|None)、max(int|None)
        实测 labels：涨停、>7%、5%~7%、2%~5%、0%~2%、平、0%~-2%、-2%~-5%、-5%~-7%、<-7%、跌停
        """
        result = {
            "range_gt7": 0,     # 涨幅 >7%（不含涨停）
            "range_5_7": 0,     # 涨幅 5%~7%
            "range_2_5": 0,     # 涨幅 2%~5%
            "range_0_2": 0,     # 涨幅 0%~2%
            "range_n2_0": 0,    # 跌幅 0%~-2%
            "range_n5_n2": 0,   # 跌幅 -2%~-5%
            "range_n7_n5": 0,   # 跌幅 -5%~-7%
            "range_lt_n7": 0,   # 跌幅 <-7%（不含跌停）
        }
        
        if not ranges:
            return result
        
        # 优先方案：利用 min/max 字段进行精确数值匹配（避免字符串冲突）
        # 区间定义：涨停(limitUp), >7%(min=7,max=None), 5-7%(min=5,max=7), 2-5%(min=2,max=5),
        #           0-2%(min=0,max=2), 平(min=0,max=0), 0--2%(min=-2,max=0), -2--5%(min=-5,max=-2),
        #           -5--7%(min=-7,max=-5), <-7%(min=None,max=-7), 跌停(limitDown)
        matched_by_numeric = False
        for r in ranges:
            count = r.get("count", r.get("value", 0)) or 0
            rtype = r.get("type", "")
            min_val = r.get("min")
            max_val = r.get("max")
            
            # 跳过涨停、跌停（type 字段标记）
            if rtype in ("limitUp", "limitDown"):
                continue
            
            # 利用 min/max 精确匹配
            if min_val is not None or max_val is not None:
                matched_by_numeric = True
                if min_val == 7 and max_val is None:
                    result["range_gt7"] = int(count)
                elif min_val == 5 and max_val == 7:
                    result["range_5_7"] = int(count)
                elif min_val == 2 and max_val == 5:
                    result["range_2_5"] = int(count)
                elif min_val == 0 and max_val == 2:
                    result["range_0_2"] = int(count)
                elif min_val == -2 and max_val == 0:
                    result["range_n2_0"] = int(count)
                elif min_val == -5 and max_val == -2:
                    result["range_n5_n2"] = int(count)
                elif min_val == -7 and max_val == -5:
                    result["range_n7_n5"] = int(count)
                elif min_val is None and max_val == -7:
                    result["range_lt_n7"] = int(count)
                # 跳过 "平" (min=0, max=0)
        
        # 如果 min/max 方案失败（所有结果仍为0），回退到 label 匹配
        if not matched_by_numeric or all(v == 0 for v in result.values()):
            # label 匹配（注意顺序：先处理含多个数字的区间，避免冲突）
            for r in ranges:
                count = r.get("count", r.get("value", 0)) or 0
                label = r.get("label", r.get("range", r.get("key", "")))
                label_str = str(label).strip()
                
                # 跳过涨停、跌停
                if "涨停" in label_str or "跌停" in label_str:
                    continue
                
                # 精确 label 匹配（基于实测 label 格式）
                if label_str in (">7%", ">7"):
                    result["range_gt7"] = int(count)
                elif label_str in ("5%~7%", "5~7%", "5%-7%", "5-7%"):
                    result["range_5_7"] = int(count)
                elif label_str in ("2%~5%", "2~5%", "2%-5%", "2-5%"):
                    result["range_2_5"] = int(count)
                elif label_str in ("0%~2%", "0~2%", "0%-2%", "0-2%"):
                    result["range_0_2"] = int(count)
                elif label_str in ("0%~-2%", "0~-2%", "-2%~0%", "-2~0%"):
                    result["range_n2_0"] = int(count)
                elif label_str in ("-2%~-5%", "-2~-5%", "-5%~-2%", "-5~-2%"):
                    result["range_n5_n2"] = int(count)
                elif label_str in ("-5%~-7%", "-5~-7%", "-7%~-5%", "-7~-5%"):
                    result["range_n7_n5"] = int(count)
                elif label_str in ("<-7%", "<-7", "lt-7%", "lt-7"):
                    result["range_lt_n7"] = int(count)
            
            # 如果 label 精确匹配也失败，按索引位置匹配（fallback）
            # 预期顺序：涨停[0], >7%[1], 5-7%[2], 2-5%[3], 0-2%[4], 平[5], 0~-2%[6], -2~-5%[7], -5~-7%[8], <-7%[9], 跌停[10]
            if all(v == 0 for v in result.values()) and len(ranges) >= 10:
                idx_map = {1: "range_gt7", 2: "range_5_7", 3: "range_2_5", 4: "range_0_2",
                           6: "range_n2_0", 7: "range_n5_n2", 8: "range_n7_n5", 9: "range_lt_n7"}
                for idx, key in idx_map.items():
                    if idx < len(ranges):
                        result[key] = int(ranges[idx].get("count", ranges[idx].get("value", 0)) or 0)
        
        return result
    
    def _extract_json_from_output(self, stdout: str) -> dict:
        """
        从 CLI stdout 中提取 JSON 数据
        CLI 会先输出格式化文本，最后输出 JSON
        """
        # 替换 Windows 换行
        stdout = stdout.replace("\r\n", "\n").replace("\r", "\n")
        
        # 策略1：找最后一个独立行上的 { 
        lines = stdout.split("\n")
        json_start_idx = -1
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if line.startswith("{"):
                json_start_idx = i
                break
        
        if json_start_idx >= 0:
            json_str = "\n".join(lines[json_start_idx:]).strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        
        # 策略2：直接找最后一个 { 位置
        last_brace = stdout.rfind("\n{")
        if last_brace != -1:
            json_str = stdout[last_brace:].strip()
        else:
            last_brace = stdout.find("{")
            if last_brace == -1:
                raise WeStockParseError(f"No JSON found in output: {stdout[:200]}")
            json_str = stdout[last_brace:].strip()
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise WeStockParseError(f"JSON parse error: {e}\nOutput: {stdout[:500]}")
    
    def cache_today(self) -> Optional[str]:
        """
        主动缓存当日 changedist 数据。
        
        设计用于每个交易日收盘后调用（如 15:30 以后），将当日全市场涨跌停分布
        写入缓存文件，供后续历史分析使用。
        
        Returns:
            str | None: 成功返回实际缓存的日期（YYYY-MM-DD），失败返回 None
            
        Note:
            若未设置 cache_dir，数据仍可获取但不持久化（函数返回获取到的日期）。
        """
        try:
            response = self._call_cli_with_retry("changedist", self.config.market)
        except WeStockError as e:
            logger.error(f"cache_today: changedist failed: {e}")
            return None

        if not response.get("success"):
            logger.error(f"cache_today: changedist returned success=false")
            return None

        data = response.get("data", response)
        actual_date = str(data.get("date", ""))[:10]
        if not actual_date:
            logger.error("cache_today: no date field in changedist response")
            return None

        self._save_cache(f"changedist/{actual_date}", data)
        logger.info(f"cache_today: cached changedist for {actual_date}")
        return actual_date

    def _load_cache(self, cache_key: str) -> Optional[dict | list]:
        """读缓存"""
        if self._cache_dir is None:
            return None
        cache_file = self._cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Cache read error {cache_file}: {e}")
        return None
    
    def _save_cache(self, cache_key: str, data: dict | list) -> None:
        """写缓存"""
        if self._cache_dir is None:
            return
        cache_file = self._cache_dir / f"{cache_key}.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Cache write error {cache_file}: {e}")
