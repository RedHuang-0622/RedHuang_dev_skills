"""f07_generate_schema: Schema 生成 Filter — TC3。

职责: 对标准化后的数据自动生成 schema.json — 类型推断、统计摘要、缺失值、归一化选项、业务注释。

Author: asset-data-skill
"""

from __future__ import annotations
import dataclasses

import logging

import pandas as pd
import numpy as np

from .context import PipelineContext
from .pipeline import Filter

logger = logging.getLogger(__name__)


class SchemaGeneratorFilter:
    """Schema 生成 Filter — 自动推断并生成 schema.json。

    输出包含:
    - 每列的 type / count / null_count / unique_count
    - 数值列: mean / std / min / max / quantiles
    - 分类列: top_values / frequencies
    - 日期列: min_date / max_date
    - 从属性簇注入 business_note
    """

    name = "generate_schema"

    def apply(self, ctx: PipelineContext) -> PipelineContext:
        df = ctx.data
        if df is None:
            logger.warning(f"[{self.name}] No data to generate schema from")
            return ctx

        cluster_fields = ctx.cluster.get("fields", {})
        schema: dict[str, dict] = {}
        anomalies: list[dict] = []

        for col in df.columns:
            col_info = self._analyze_column(df[col], col, cluster_fields.get(col, {}))
            schema[col] = col_info

            # 检测异常
            col_anomalies = self._detect_anomalies(df[col], col, col_info)
            anomalies.extend(col_anomalies)

        logger.info(
            f"[{self.name}] Generated schema for {len(schema)} columns, "
            f"{len(anomalies)} anomalies detected"
        )

        return (
            dataclasses.replace(ctx, schema=schema)
            .with_metric("schema_columns", len(schema))
            .with_metric("anomaly_count", len(anomalies))
        )

    def _analyze_column(
        self, series: pd.Series, name: str, field_def: dict
    ) -> dict:
        """分析单列并返回元数据。"""
        info: dict = {
            "name": name,
            "type": self._infer_type(series),
            "count": int(series.notna().sum()),
            "null_count": int(series.isna().sum()),
            "unique_count": int(series.nunique()),
        }

        dtype = info["type"]

        if dtype in ("float", "integer"):
            info.update(self._numeric_stats(series))
            info["normalization_available"] = field_def.get(
                "normalization_available", []
            )

        elif dtype == "string":
            info.update(self._categorical_stats(series))

        elif dtype == "date":
            info.update(self._date_stats(series))

        # 注入业务注释
        if field_def.get("common_errors"):
            info["business_note"] = (
                f"常见错误: {'; '.join(field_def['common_errors'])}"
            )
        if field_def.get("unit"):
            info["unit"] = field_def["unit"]

        return info

    @staticmethod
    def _infer_type(series: pd.Series) -> str:
        """推断列类型。"""
        if pd.api.types.is_bool_dtype(series):
            return "boolean"
        if pd.api.types.is_integer_dtype(series):
            return "integer"
        if pd.api.types.is_float_dtype(series):
            return "float"
        if pd.api.types.is_datetime64_any_dtype(series):
            return "date"
        return "string"

    @staticmethod
    def _numeric_stats(series: pd.Series) -> dict:
        """数值列统计。"""
        clean = series.dropna()
        if len(clean) == 0:
            return {"mean": None, "std": None, "min": None, "max": None}
        return {
            "mean": float(clean.mean()),
            "std": float(clean.std()),
            "min": float(clean.min()),
            "max": float(clean.max()),
            "quantiles": {
                "25%": float(clean.quantile(0.25)),
                "50%": float(clean.quantile(0.50)),
                "75%": float(clean.quantile(0.75)),
            },
        }

    @staticmethod
    def _categorical_stats(series: pd.Series) -> dict:
        """分类列统计 — 高频值 Top 10。"""
        value_counts = series.value_counts().head(10)
        return {
            "top_values": {
                str(k): int(v) for k, v in value_counts.items()
            }
        }

    @staticmethod
    def _date_stats(series: pd.Series) -> dict:
        """日期列统计。"""
        clean = series.dropna()
        if len(clean) == 0:
            return {"min_date": None, "max_date": None}
        return {
            "min_date": str(clean.min()),
            "max_date": str(clean.max()),
        }

    @staticmethod
    def _detect_anomalies(
        series: pd.Series, name: str, col_info: dict
    ) -> list[dict]:
        """检测列级异常。"""
        anomalies: list[dict] = []

        # 高空值率 (>50%)
        null_rate = col_info["null_count"] / (
            col_info["count"] + col_info["null_count"]
        ) if (col_info["count"] + col_info["null_count"]) > 0 else 0
        if null_rate > 0.5:
            anomalies.append({
                "field": name,
                "description": f"缺失率 {null_rate:.1%}，超过 50%",
                "severity": "warning",
                "affected_rows": col_info["null_count"],
            })

        # 数值列：零方差
        if col_info.get("std") == 0 and col_info.get("mean") is not None:
            anomalies.append({
                "field": name,
                "description": "零方差 — 所有值相同",
                "severity": "warning",
                "affected_rows": col_info["count"],
            })

        return anomalies

    def rollback(self, ctx: PipelineContext) -> PipelineContext:
        return dataclasses.replace(ctx, schema=None)
