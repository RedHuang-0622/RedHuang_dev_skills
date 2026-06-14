"""f06_normalize_numeric: 数值归一化 Filter — TC3。

职责: 按属性簇 normalization_available 标记，对数值列执行 Z-score 或 Min-Max 归一化。
生成独立文件 data_normalized.csv（可选）。

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


class NumericNormalizerFilter:
    """数值归一化 Filter。

    根据字段定义的 normalization_available 标记执行归一化:
    - "zscore": (x - mean) / std
    - "minmax": (x - min) / (max - min)

    归一化后的数据追加为 `{field}_normalized` 新列，保留原列。
    """

    name = "normalize_numeric"

    def apply(self, ctx: PipelineContext) -> PipelineContext:
        df = ctx.data
        if df is None:
            logger.info(f"[{self.name}] No data to normalize")
            return ctx

        cluster = ctx.cluster
        fields = cluster.get("fields", {})
        normalized_cols: list[str] = []

        for fname, fdef in fields.items():
            norms = fdef.get("normalization_available", [])
            if not norms:
                continue
            if fname not in df.columns:
                continue

            col = df[fname]
            if not pd.api.types.is_numeric_dtype(col):
                logger.debug(f"[{self.name}] Skipping non-numeric column: {fname}")
                continue

            if "zscore" in norms:
                new_col = f"{fname}_zscore"
                mean = col.mean()
                std = col.std()
                if std and std > 0:
                    df[new_col] = (col - mean) / std
                else:
                    df[new_col] = 0.0
                normalized_cols.append(new_col)

            if "minmax" in norms:
                new_col = f"{fname}_minmax"
                col_min = col.min()
                col_max = col.max()
                if col_max > col_min:
                    df[new_col] = (col - col_min) / (col_max - col_min)
                else:
                    df[new_col] = 0.0
                normalized_cols.append(new_col)

        logger.info(
            f"[{self.name}] Added {len(normalized_cols)} normalized columns: "
            f"{normalized_cols}"
        )

        return ctx.with_data(df).with_metric(
            "normalized_columns", len(normalized_cols)
        )

    def rollback(self, ctx: PipelineContext) -> PipelineContext:
        # 移除归一化列
        df = ctx.data
        if df is not None:
            norm_cols = [c for c in df.columns if c.endswith(("_zscore", "_minmax"))]
            df = df.drop(columns=norm_cols, errors="ignore")
        return dataclasses.replace(ctx, data=df)
