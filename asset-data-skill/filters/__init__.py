"""Filters package: 管道-过滤器架构的 Filter 实现。

Filter 按数据流顺序编号:
  f01: 索引查找
  f02-f04: 条目化预处理
  f05-f08: 标准化中间表示
  f09-f13: 处理逻辑 (read/clean/validate/transform/analyze)
  f14-f16: 缓存与交付 (snapshot/adapt/finalize)
"""

from .context import PipelineContext
from .pipeline import Filter, Goal, Pipeline, PipelineConfig, PipelineFactory, PipelineResult, Wrapper

__all__ = [
    "Filter",
    "Goal",
    "Pipeline",
    "PipelineConfig",
    "PipelineContext",
    "PipelineFactory",
    "PipelineResult",
    "Wrapper",
]
