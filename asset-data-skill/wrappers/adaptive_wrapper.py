"""Adaptive Wrapper: TC8 Goal 编排 — 自适应处理。

装饰 Filter 链，在 Pipeline 执行前分析数据特征，
动态插入/跳过步骤。自动检测：
- 自由文本比率 > 90% → 插入条目化 Filter
- 缺失率 > 阈值 → 插入缺失值分析步骤
- 大数据量 → 启用量采样

Author: asset-data-skill
"""

from __future__ import annotations
import dataclasses

import logging

import pandas as pd

from filters.pipeline import Filter, PipelineContext, Wrapper

logger = logging.getLogger(__name__)

TEXT_RATIO_THRESHOLD = 0.9
NULL_RATE_THRESHOLD = 0.3
LARGE_DATA_THRESHOLD = 100_000


class AdaptiveWrapper:
    """自适应包装器 — 根据数据特征动态调整 Filter 行为。

    不改变 Filter 链结构，而是通过 Context meta 标记
    告知下游 Filter 是否需要特殊处理。
    """

    def __init__(
        self,
        text_ratio_threshold: float = TEXT_RATIO_THRESHOLD,
        null_rate_threshold: float = NULL_RATE_THRESHOLD,
        large_data_threshold: int = LARGE_DATA_THRESHOLD,
    ):
        self._text_threshold = text_ratio_threshold
        self._null_threshold = null_rate_threshold
        self._large_threshold = large_data_threshold

    def wrap(self, filter_: Filter) -> Filter:
        original_apply = filter_.apply
        wrapper = self

        class WrappedFilter:
            name = filter_.name

            def apply(self, ctx: PipelineContext) -> PipelineContext:
                # 在 read Filter 后分析数据特征
                if filter_.name == "read" and ctx.data is not None:
                    ctx = wrapper._analyze_and_tag(ctx)

                # 在 chunk Filter 前检查 raw_text
                if filter_.name == "chunk" and ctx.raw_text is not None:
                    text_len = len(ctx.raw_text)
                    if text_len > wrapper._large_threshold:
                        logger.info(
                            f"[Adaptive] Large text ({text_len} chars), "
                            f"using larger chunk size"
                        )
                        ctx = dataclasses.replace(
                            ctx,
                            meta={
                                **ctx.meta,
                                "chunk_size_override": 4000,
                                "large_text": True,
                            },
                        )

                return original_apply(ctx)

            def rollback(self, ctx: PipelineContext) -> PipelineContext:
                return filter_.rollback(ctx)

        return WrappedFilter()

    def _analyze_and_tag(self, ctx: PipelineContext) -> PipelineContext:
        """分析数据特征并标记 Context。"""
        df = ctx.data
        if df is None:
            return ctx

        features: dict[str, bool | float] = {}
        new_meta = dict(ctx.meta)

        # 1. 自由文本比率检测
        text_ratio = self._compute_text_ratio(df)
        features["text_ratio"] = text_ratio
        if text_ratio > self._text_threshold:
            new_meta["needs_extraction"] = True
            logger.info(
                f"[Adaptive] Text ratio {text_ratio:.1%} > {self._text_threshold:.0%}, "
                f"enabling entry extraction"
            )

        # 2. 缺失率检测
        null_rate = df.isna().mean().mean() if len(df) > 0 else 0
        features["null_rate"] = null_rate
        if null_rate > self._null_threshold:
            new_meta["needs_null_analysis"] = True
            logger.info(
                f"[Adaptive] Null rate {null_rate:.1%} > {self._null_threshold:.0%}, "
                f"enabling null analysis"
            )

        # 3. 数据量检测
        if len(df) > self._large_threshold:
            new_meta["large_dataset"] = True
            new_meta["sample_size"] = min(self._large_threshold, len(df))
            logger.info(
                f"[Adaptive] Large dataset ({len(df):,} rows), "
                f"recommend batch processing"
            )

        # 4. 行/列比例检测（宽表 vs 长表）
        if len(df.columns) > len(df) * 2:
            features["wide_table"] = True

        new_meta["data_features"] = features

        return dataclasses.replace(ctx, meta=new_meta)

    @staticmethod
    def _compute_text_ratio(df: pd.DataFrame) -> float:
        """计算自由文本列的比率。"""
        text_cols = 0
        for col in df.columns:
            if df[col].dtype == object:
                # 检查是否像自由文本（平均长度 > 100）
                avg_len = (
                    df[col]
                    .dropna()
                    .apply(lambda x: len(str(x)) if isinstance(x, str) else 0)
                    .mean()
                )
                if avg_len > 100:
                    text_cols += 1

        return text_cols / max(len(df.columns), 1)
