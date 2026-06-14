"""f08_generate_summary: Summary 生成 Filter — TC3。

职责: 生成人类可读的 summary.md 概览报告 — 行数、列列表、异常预览、建议操作。

Author: asset-data-skill
"""

from __future__ import annotations

import logging

import pandas as pd

from ..context import PipelineContext
from ..pipeline import Filter

logger = logging.getLogger(__name__)


class SummaryGeneratorFilter:
    """Summary 生成 Filter — 生成 Markdown 格式的概览报告。

    输出到 ctx.summary 字段，内容可供人和 Agent 阅读。
    """

    name = "generate_summary"

    def apply(self, ctx: PipelineContext) -> PipelineContext:
        df = ctx.data
        schema = ctx.schema or {}

        lines: list[str] = [
            f"# 数据概览报告",
            f"",
            f"**任务**: {ctx.task_id}",
            f"**资产类型**: {ctx.asset_type}",
            f"**角色**: {ctx.role}",
            f"",
        ]

        if df is not None:
            lines.extend([
                f"## 基本统计",
                f"",
                f"- **总行数**: {len(df):,}",
                f"- **总列数**: {len(df.columns)}",
                f"- **列名**: {', '.join(df.columns[:20])}"
                f"{' ...' if len(df.columns) > 20 else ''}",
                f"",
                f"## 列概览",
                f"",
                f"| 列名 | 类型 | 非空值 | 空值 | 唯一值 | 备注 |",
                f"|------|------|--------|------|--------|------|",
            ])

            for col in df.columns:
                col_info = schema.get(col, {})
                lines.append(
                    f"| {col} "
                    f"| {col_info.get('type', '?')} "
                    f"| {col_info.get('count', '?')} "
                    f"| {col_info.get('null_count', '?')} "
                    f"| {col_info.get('unique_count', '?')} "
                    f"| {col_info.get('business_note', '')} |"
                )

        # 异常预览
        anomalies = ctx.metrics.get("anomaly_count", 0)
        if anomalies > 0:
            lines.extend([
                f"",
                f"## ⚠️ 异常警告 ({anomalies} 项)",
                f"",
                f"> 详见 schema.json 中各列的 anomaly 描述。",
            ])

        # 建议操作
        lines.extend([
            f"",
            f"## 建议操作",
            f"",
        ])

        if df is not None:
            null_rate = df.isna().mean().mean() if len(df) > 0 else 0
            if null_rate > 0.1:
                lines.append(
                    f"- 🔴 整体缺失率 {null_rate:.1%}，建议执行缺失值分析"
                )
            elif null_rate > 0:
                lines.append(
                    f"- 🟡 存在少量缺失值 ({null_rate:.1%})，可自动填充或标记"
                )
            else:
                lines.append("- 🟢 数据完整，无缺失值")

            if len(df) > 10000:
                lines.append(
                    f"- ℹ️ 数据量较大 ({len(df):,} 行)，建议分批处理或使用批量模式"
                )

        summary = "\n".join(lines)
        logger.info(f"[{self.name}] Generated summary ({len(summary)} chars)")

        return object.__replace__(ctx, summary=summary)

    def rollback(self, ctx: PipelineContext) -> PipelineContext:
        return object.__replace__(ctx, summary=None)
