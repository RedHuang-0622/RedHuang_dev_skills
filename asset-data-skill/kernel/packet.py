"""NormalizedPacket: 标准化数据包格式定义 — 三件套 DTO。

Agent 间通过 task_cache 交换数据的核心契约。

Author: asset-data-skill
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class NormalizedPacket:
    """标准化数据包 — 数据处理各阶段产出的统一格式。

    三件套:
        data_csv: 主数据表（列名为属性簇标准字段名）
        schema_json: 每列的详细元数据
        summary_md: 人类可读的概览报告

    扩展产出:
        raw_entries: 条目化结果（来源为 TC2）
        documents_jsonl: 向量嵌入文本行（来源为 TC3 format_adapter）
        data_normalized_csv: Z-score/Min-Max 归一化副本（来源为 TC3 numerical normalizer）
    """

    data_csv: pd.DataFrame | None = None
    schema_json: dict[str, Any] | None = None
    summary_md: str | None = None

    # 可选扩展
    raw_entries: list[dict] | None = None
    documents_jsonl: list[dict] | None = None
    data_normalized_csv: pd.DataFrame | None = None

    # 元数据
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_complete(self) -> bool:
        """检查三件套是否完整。"""
        return (
            self.data_csv is not None
            and self.schema_json is not None
            and self.summary_md is not None
        )

    def to_dict(self) -> dict[str, Any]:
        """转为可序列化的字典。"""
        return {
            "data_rows": len(self.data_csv) if self.data_csv is not None else 0,
            "data_columns": (
                list(self.data_csv.columns) if self.data_csv is not None else []
            ),
            "schema_fields": (
                list(self.schema_json.keys()) if self.schema_json else []
            ),
            "summary_length": len(self.summary_md) if self.summary_md else 0,
            "has_raw_entries": self.raw_entries is not None,
            "has_documents": self.documents_jsonl is not None,
            "has_normalized": self.data_normalized_csv is not None,
            "metadata": self.metadata,
        }
