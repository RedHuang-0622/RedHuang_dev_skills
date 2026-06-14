"""f10_clean: 数据清洗 Filter — TC4 处理逻辑。

职责: 缺失值处理、去重、异常检测、common_errors 自动修复。
根据属性簇的 common_errors 配置自动修复已知错误模式。

Author: asset-data-skill
"""

from __future__ import annotations

import logging

import pandas as pd

from ..context import PipelineContext
from ..pipeline import Filter

logger = logging.getLogger(__name__)


class CleanerFilter:
    """数据清洗 Filter — 自动修复常见错误 + 去重 + 缺失值标注。

    处理流程:
    1. 去除全空行和全空列
    2. 按属性簇 common_errors 自动修复
    3. 去重（基于主键列）
    4. 缺失值统计与标注
    """

    name = "clean"

    def __init__(self, drop_na_threshold: float = 0.9):
        """drop_na_threshold: 缺失率超过此值的列，标记但不删除"""
        self._drop_na_threshold = drop_na_threshold

    def apply(self, ctx: PipelineContext) -> PipelineContext:
        df = ctx.data
        if df is None:
            logger.warning(f"[{self.name}] No data to clean")
            return ctx

        initial_rows = len(df)
        initial_cols = len(df.columns)

        # 1. 去除全空行
        df = df.dropna(how="all")
        # 去除全空列
        df = df.dropna(axis=1, how="all")

        # 2. 按 common_errors 自动修复
        cluster_fields = ctx.cluster.get("fields", {})
        df, fixes = self._fix_common_errors(df, cluster_fields)

        # 3. 去重
        before_dedup = len(df)
        df = df.drop_duplicates()
        dupes_removed = before_dedup - len(df)

        # 4. 缺失值统计
        na_stats = {}
        for col in df.columns:
            na_count = df[col].isna().sum()
            if na_count > 0:
                na_rate = na_count / len(df)
                na_stats[col] = {"count": int(na_count), "rate": round(na_rate, 4)}
                if na_rate > self._drop_na_threshold:
                    logger.warning(
                        f"[{self.name}] Column '{col}' has {na_rate:.1%} missing — "
                        f"consider dropping"
                    )

        logger.info(
            f"[{self.name}] {initial_rows}→{len(df)} rows, "
            f"{initial_cols}→{len(df.columns)} cols, "
            f"{dupes_removed} dupes removed, "
            f"{len(fixes)} fixes applied, "
            f"{len(na_stats)} cols with nulls"
        )

        return (
            ctx.with_data(df)
            .with_metric("cleaned_rows", len(df))
            .with_metric("dupes_removed", dupes_removed)
            .with_metric("fixes_applied", len(fixes))
            .with_metric("null_columns", len(na_stats))
        )

    def _fix_common_errors(
        self, df: pd.DataFrame, cluster_fields: dict
    ) -> tuple[pd.DataFrame, list[str]]:
        """根据 common_errors 配置自动修复。"""
        fixes: list[str] = []

        for fname, fdef in cluster_fields.items():
            if fname not in df.columns:
                continue

            common_errors = fdef.get("common_errors", [])
            for error_desc in common_errors:
                if "万" in error_desc:
                    col = df[fname]
                    if col.dtype == object:
                        mask = col.str.contains("万", na=False)
                        if mask.any():
                            # 提取数字并乘以 10000
                            df.loc[mask, fname] = (
                                col[mask]
                                .str.replace("万", "", regex=False)
                                .str.replace(r"[^\d.]", "", regex=True)
                                .apply(lambda x: float(x) * 10000 if x else None)
                            )
                            fixes.append(f"{fname}: 修复 '万' 单位 ({mask.sum()} 行)")

                if "负数" in error_desc:
                    col = df[fname]
                    if pd.api.types.is_numeric_dtype(col):
                        neg_mask = col < 0
                        if neg_mask.any():
                            df.loc[neg_mask, fname] = abs(col[neg_mask])
                            fixes.append(f"{fname}: 修复负数为正数 ({neg_mask.sum()} 行)")

                if "填反" in error_desc or ">120%" in error_desc:
                    col = df[fname]
                    if pd.api.types.is_numeric_dtype(col):
                        outliers = col > 1.2
                        if outliers.any():
                            fixes.append(
                                f"{fname}: 发现疑似填反值 >120% ({outliers.sum()} 行) — 需人工确认"
                            )

        return df, fixes

    def rollback(self, ctx: PipelineContext) -> PipelineContext:
        return ctx.with_data(None)
