"""PipelineContext: 不可变数据流上下文 — 在 Filter 间传递。

设计决策:
- 使用 frozen dataclass 保证不可变性
- Filter.apply() 返回新实例（通过 dataclasses.replace）
- 只存储引用（DataFrame, dict 等），不深拷贝
- artifacts 追踪中间产物的文件路径
- metrics 累积处理指标

Author: asset-data-skill
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class PipelineContext:
    """不可变上下文 — Filter 间传递的唯一数据载体。

    Filter.apply(ctx) → new_ctx，通过 replace() 创建新实例。
    只存储引用，replace() 复制的是引用而非深拷贝。

    Attributes:
        task_id: 任务唯一标识
        asset_type: 资产类型编码 (e.g. "RE_MORTGAGE")
        role: 调用者角色 (intern/analyst/admin)
        cluster: 属性簇快照（dict，冻结于任务启动时）
        data: 当前数据表 (pd.DataFrame | None)
        entries: 条目化结果 (list[dict] | None)
        schema: schema.json 内容 (dict | None)
        summary: summary.md 内容 (str | None)
        artifacts: 产出物路径映射 {step_name: file_path}
        metrics: 处理指标 {metric_name: value}
        meta: 扩展元数据 (自由 dict)
    """

    task_id: str
    asset_type: str
    role: str = "analyst"
    cluster: dict = field(default_factory=dict)

    # 数据载体
    data: pd.DataFrame | None = None
    entries: list[dict] | None = None
    raw_text: str | None = None

    # 标准化输出
    schema: dict | None = None
    summary: str | None = None

    # 追踪
    artifacts: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def with_data(self, data: pd.DataFrame | None) -> "PipelineContext":
        """创建新 Context，替换 data 字段。"""
        return object.__replace__(self, data=data)

    def with_entries(self, entries: list[dict] | None) -> "PipelineContext":
        """创建新 Context，替换 entries 字段。"""
        return object.__replace__(self, entries=entries)

    def with_artifact(self, step: str, path: str) -> "PipelineContext":
        """创建新 Context，追加 artifact 记录。"""
        new_artifacts = {**self.artifacts, step: path}
        return object.__replace__(self, artifacts=new_artifacts)

    def with_metric(self, key: str, value: Any) -> "PipelineContext":
        """创建新 Context，追加 metric 记录。"""
        new_metrics = {**self.metrics, key: value}
        return object.__replace__(self, metrics=new_metrics)
