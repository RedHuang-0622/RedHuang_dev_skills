"""f05_normalize_structure: 结构归一化 Filter — TC3。

职责: 列名别名匹配、日期标准化、布尔值统一、数值清洗（去除非数字字符）。

Author: asset-data-skill
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

import pandas as pd

from .context import PipelineContext
from .pipeline import Filter

logger = logging.getLogger(__name__)

DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日",
    "%d/%m/%Y", "%m/%d/%Y",
    "%Y%m%d",
]


class StructureNormalizerFilter:
    """结构归一化 Filter — 将异构列名和格式统一为属性簇标准。

    处理流程:
    1. 列名别名匹配 → 重命名为属性簇字段名
    2. 日期列 → 统一为 ISO 8601 (YYYY-MM-DD)
    3. 布尔列 → True/False
    4. 数值列 → 去除空格、千分位、单位字符、转换中文数字
    """

    name = "normalize_structure"

    def apply(self, ctx: PipelineContext) -> PipelineContext:
        df = ctx.data
        if df is None:
            # 从 entries 构建 DataFrame
            entries = ctx.entries
            if entries:
                df = self._entries_to_dataframe(entries, ctx.cluster)
            else:
                logger.warning(f"[{self.name}] No data to normalize")
                return ctx

        cluster = ctx.cluster
        fields = cluster.get("fields", {})

        # 1. 列名别名匹配
        df = self._match_aliases(df, fields)

        # 2. 日期标准化
        df = self._normalize_dates(df, fields)

        # 3. 布尔标准化
        df = self._normalize_booleans(df, fields)

        # 4. 数值清洗
        df = self._normalize_numerics(df, fields)

        logger.info(
            f"[{self.name}] Normalized {len(df)} rows x {len(df.columns)} columns"
        )

        return ctx.with_data(df).with_metric("row_count", len(df)).with_metric(
            "column_count", len(df.columns)
        )

    def _entries_to_dataframe(self, entries: list[dict], cluster: dict) -> pd.DataFrame:
        """将 raw_entries.json 转换为 DataFrame。"""
        rows = []
        for entry in entries:
            row = entry.get("fields", {})
            row["_confidence"] = entry.get("confidence")
            row["_needs_review"] = entry.get("needs_review", False)
            rows.append(row)
        return pd.DataFrame(rows)

    def _match_aliases(self, df: pd.DataFrame, fields: dict) -> pd.DataFrame:
        """列名别名匹配：将异构列名映射到属性簇标准字段名。"""
        alias_map: dict[str, str] = {}
        for fname, fdef in fields.items():
            for alias in fdef.get("aliases", []):
                alias_map[alias] = fname
            alias_map[fname] = fname  # 自身也是映射

        rename_map: dict[str, str] = {}
        for col in df.columns:
            if col in alias_map:
                rename_map[col] = alias_map[col]

        if rename_map:
            df = df.rename(columns=rename_map)
            logger.debug(f"[{self.name}] Renamed columns: {rename_map}")

        return df

    def _normalize_dates(self, df: pd.DataFrame, fields: dict) -> pd.DataFrame:
        """日期标准化：统一为 YYYY-MM-DD 格式。"""
        for fname, fdef in fields.items():
            if fdef.get("type") != "date":
                continue
            if fname not in df.columns:
                continue

            df[fname] = df[fname].apply(
                lambda x: self._parse_date(x) if pd.notna(x) else x
            )

        return df

    def _parse_date(self, value) -> str | None:
        """尝试多种格式解析日期。"""
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, (int, float)):
            # 整数 → 尝试 Excel serial number 或 YYYYMMDD
            val_str = str(int(value))
            if len(val_str) == 8:
                try:
                    return datetime.strptime(val_str, "%Y%m%d").strftime("%Y-%m-%d")
                except ValueError:
                    pass

        if not isinstance(value, str):
            return str(value) if value else None

        value = value.strip()
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue

        logger.debug(f"Cannot parse date: {value}")
        return value

    def _normalize_booleans(self, df: pd.DataFrame, fields: dict) -> pd.DataFrame:
        """布尔标准化：统一为 bool 类型。"""
        for fname, fdef in fields.items():
            if fdef.get("type") != "boolean":
                continue
            if fname not in df.columns:
                continue

            df[fname] = df[fname].apply(self._parse_bool)
        return df

    @staticmethod
    def _parse_bool(value) -> bool | None:
        if isinstance(value, bool):
            return value
        if pd.isna(value):
            return None
        if isinstance(value, str):
            return value.strip().lower() in ("true", "yes", "是", "1", "y")
        if isinstance(value, (int, float)):
            return bool(value)
        return None

    def _normalize_numerics(self, df: pd.DataFrame, fields: dict) -> pd.DataFrame:
        """数值清洗：去除空格、千分位、单位字符、中文数字。"""
        for fname, fdef in fields.items():
            if fdef.get("type") not in ("float", "integer"):
                continue
            if fname not in df.columns:
                continue

            df[fname] = df[fname].apply(
                lambda x: self._clean_number(x, fdef) if pd.notna(x) else x
            )

        return df

    @staticmethod
    def _clean_number(value, fdef: dict) -> float | int | None:
        """清洗数值：处理中文单位、千分位、常见错误。"""
        if isinstance(value, (int, float)):
            return value

        if not isinstance(value, str):
            return None

        s = value.strip()

        # 检测包含汉字"万"
        if "万" in s:
            has_wan = True
            s = s.replace("万", "")
        else:
            has_wan = False

        # 去除常见分隔符和非数字字符（保留小数点、负号）
        s = re.sub(r'[,\s，￥$€¥元]', '', s)
        s = re.sub(r'[^0-9.\-]', '', s)

        if not s or s == '-':
            return None

        try:
            num = float(s)
            if has_wan:
                num *= 10000
            target_type = fdef.get("type", "float")
            if target_type == "integer":
                return int(num)
            return num
        except ValueError:
            return None

    def rollback(self, ctx: PipelineContext) -> PipelineContext:
        return ctx.with_data(None)
