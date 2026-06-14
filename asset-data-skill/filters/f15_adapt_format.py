"""f15_adapt_format: 多 Agent 格式适配 Filter — TC3 格式适配。

职责: 根据属性簇 agent_preference 和下游 Agent 能力，
生成额外格式：documents.jsonl（向量嵌入）、report.md（详细报告）。

Author: asset-data-skill
"""

from __future__ import annotations
import dataclasses

import json
import logging
from pathlib import Path

import pandas as pd

from .context import PipelineContext
from .pipeline import Filter

logger = logging.getLogger(__name__)


class FormatAdapterFilter:
    """格式适配 Filter — 为下游 Agent 生成适配格式。

    根据 agent_preference 生成:
    - "csv_batch": 保持 data.csv（默认，无需额外处理）
    - "llm_reasoning": 生成 documents.jsonl（每行一个文本描述）
    - 同时生成 enhanced_report.md（更详细的描述统计）
    """

    name = "adapt_format"

    def apply(self, ctx: PipelineContext) -> PipelineContext:
        df = ctx.data
        if df is None:
            logger.info(f"[{self.name}] No data to adapt")
            return ctx

        agent_pref = ctx.cluster.get(
            "agent_preference",
            ctx.cluster.get("base_type", "csv_batch"),
        )

        if "llm_reasoning" in agent_pref:
            documents = self._generate_documents(df, ctx.cluster)
            new_meta = {**ctx.meta, "documents": documents}
            ctx = dataclasses.replace(ctx, meta=new_meta)
            logger.info(
                f"[{self.name}] Generated {len(documents)} documents.jsonl entries"
            )

        # 生成详细报告
        report = self._generate_enhanced_report(df, ctx)
        new_meta = {**ctx.meta, "enhanced_report": report}
        ctx = dataclasses.replace(ctx, meta=new_meta)

        return ctx

    def _generate_documents(
        self, df: pd.DataFrame, cluster: dict
    ) -> list[dict]:
        """生成 documents.jsonl：每行一个自然语言描述。"""
        documents: list[dict] = []
        fields = cluster.get("fields", {})

        for idx, row in df.iterrows():
            # 构建自然语言描述
            parts = []
            for col in df.columns:
                val = row[col]
                if pd.isna(val):
                    continue

                fdef = fields.get(col, {})
                unit = fdef.get("unit", "")
                if unit:
                    parts.append(f"{col}: {val} {unit}")
                else:
                    parts.append(f"{col}: {val}")

            text = "; ".join(parts)
            documents.append({
                "id": f"doc_{idx}",
                "text": text,
                "metadata": {
                    "row_index": int(idx),
                    "asset_type": cluster.get("cluster_id", ""),
                },
            })

        return documents

    def _generate_enhanced_report(
        self, df: pd.DataFrame, ctx: PipelineContext
    ) -> str:
        """生成增强版 Markdown 报告。"""
        lines: list[str] = [
            f"# Enhanced Report: {ctx.asset_type}",
            f"",
            f"## Data Profile",
            f"- Rows: {len(df):,}",
            f"- Columns: {len(df.columns)}",
            f"- Memory: {df.memory_usage(deep=True).sum() / 1024 / 1024:.1f} MB",
            f"",
            f"## Column Details",
            f"",
            f"| Column | Dtype | Non-Null | Null% | Unique |",
            f"|--------|-------|----------|-------|--------|",
        ]

        for col in df.columns:
            null_rate = df[col].isna().mean()
            lines.append(
                f"| {col} "
                f"| {df[col].dtype} "
                f"| {df[col].notna().sum()} "
                f"| {null_rate:.1%} "
                f"| {df[col].nunique()} |"
            )

        # 分析结果嵌入
        analysis = ctx.meta.get("analysis_result", {})
        if analysis.get("outliers"):
            lines.extend([
                f"",
                f"## Outlier Summary",
            ])
            for col, info in analysis["outliers"].items():
                lines.append(
                    f"- **{col}**: {info['count']} outliers "
                    f"({info['rate']:.1%}), range [{info['extreme_min']:.2f}, {info['extreme_max']:.2f}]"
                )

        if analysis.get("correlation", {}).get("strong_pairs"):
            lines.extend([
                f"",
                f"## Strong Correlations (|r| ≥ 0.7)",
            ])
            for pair in analysis["correlation"]["strong_pairs"]:
                lines.append(
                    f"- {pair['col_a']} ↔ {pair['col_b']}: r = {pair['correlation']}"
                )

        return "\n".join(lines)

    def rollback(self, ctx: PipelineContext) -> PipelineContext:
        new_meta = {
            k: v for k, v in ctx.meta.items()
            if k not in ("documents", "enhanced_report")
        }
        return dataclasses.replace(ctx, meta=new_meta)
