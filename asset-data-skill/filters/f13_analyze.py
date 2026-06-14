"""f13_analyze: 数据分析 Filter — TC4 处理逻辑。

职责: 描述统计、分布分析、相关性矩阵、异常值检测。
生成结构化分析结果，写入 ctx.meta["analysis_result"]。

Author: asset-data-skill
"""

from __future__ import annotations

import logging

import pandas as pd
import numpy as np

from ..context import PipelineContext
from ..pipeline import Filter

logger = logging.getLogger(__name__)


class AnalyzerFilter:
    """数据分析 Filter — 多维度统计分析。

    分析维度:
    1. 描述性统计（均值/中位数/标准差/偏度/峰度）
    2. 分布分析（直方图 bin 统计）
    3. 相关性矩阵（Pearson/Spearman）
    4. 异常值检测（IQR 方法）
    """

    name = "analyze"

    def apply(self, ctx: PipelineContext) -> PipelineContext:
        df = ctx.data
        if df is None:
            logger.warning(f"[{self.name}] No data to analyze")
            return ctx

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not numeric_cols:
            logger.info(f"[{self.name}] No numeric columns to analyze")
            return ctx

        analysis: dict = {
            "numeric_columns": numeric_cols,
            "descriptive": {},
            "outliers": {},
            "correlation": {},
        }

        # 1. 描述性统计
        for col in numeric_cols:
            series = df[col].dropna()
            if len(series) < 2:
                continue
            analysis["descriptive"][col] = {
                "mean": float(series.mean()),
                "median": float(series.median()),
                "std": float(series.std()),
                "skew": float(series.skew()),
                "kurtosis": float(series.kurtosis()),
                "missing_rate": round(
                    1 - len(series) / len(df), 4
                ),
            }

        # 2. 异常值检测 (IQR)
        for col in numeric_cols:
            series = df[col].dropna()
            if len(series) < 4:
                continue
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            outlier_mask = (series < lower) | (series > upper)
            if outlier_mask.any():
                analysis["outliers"][col] = {
                    "count": int(outlier_mask.sum()),
                    "rate": round(outlier_mask.sum() / len(series), 4),
                    "lower_bound": float(lower),
                    "upper_bound": float(upper),
                    "extreme_min": float(series[outlier_mask].min()),
                    "extreme_max": float(series[outlier_mask].max()),
                }

        # 3. 相关性矩阵 (>2 列才计算)
        if len(numeric_cols) >= 2:
            corr_matrix = df[numeric_cols].corr()
            # 提取强相关对 (|r| > 0.7)
            strong_pairs: list[dict] = []
            for i, col_a in enumerate(numeric_cols):
                for col_b in numeric_cols[i + 1 :]:
                    r = corr_matrix.loc[col_a, col_b]
                    if abs(r) >= 0.7:
                        strong_pairs.append({
                            "col_a": col_a,
                            "col_b": col_b,
                            "correlation": round(float(r), 4),
                        })
            analysis["correlation"] = {
                "strong_pairs": strong_pairs,
            }

        logger.info(
            f"[{self.name}] Analyzed {len(numeric_cols)} numeric columns, "
            f"{len(analysis['outliers'])} cols with outliers, "
            f"{len(analysis['correlation'].get('strong_pairs', []))} strong correlations"
        )

        new_meta = {**ctx.meta, "analysis_result": analysis}

        return (
            object.__replace__(ctx, meta=new_meta)
            .with_metric("outlier_columns", len(analysis["outliers"]))
            .with_metric(
                "strong_correlations",
                len(analysis["correlation"].get("strong_pairs", [])),
            )
        )

    def rollback(self, ctx: PipelineContext) -> PipelineContext:
        new_meta = {
            k: v for k, v in ctx.meta.items() if k != "analysis_result"
        }
        return object.__replace__(ctx, meta=new_meta)
