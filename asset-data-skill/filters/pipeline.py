"""Pipeline & Filter Protocol: 管道-过滤器架构核心。

Filter Protocol: (PipelineContext) → PipelineContext 的纯变换函数。
Wrapper Protocol: 装饰 Filter，注入横切关注点。
Pipeline: Chain of Responsibility 模式执行 Filter 链。
PipelineFactory: Factory Method 从 goal_routing.json 构建 Pipeline。

Author: asset-data-skill
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

from .context import PipelineContext

logger = logging.getLogger(__name__)


# ─── Filter Protocol ───────────────────────────────────────

@runtime_checkable
class Filter(Protocol):
    """过滤器协议 — 单一职责：接收 Context，返回新 Context。

    每个 Filter 是 (PipelineContext) → PipelineContext 的纯变换函数。
    副作用（文件读写）通过 Context.artifacts 追踪。
    """

    @property
    def name(self) -> str: ...

    def apply(self, ctx: PipelineContext) -> PipelineContext: ...

    def rollback(self, ctx: PipelineContext) -> PipelineContext:
        """回滚到本 Filter 执行前的状态。默认实现为无操作。"""
        return ctx


# ─── Wrapper Protocol ──────────────────────────────────────

@runtime_checkable
class Wrapper(Protocol):
    """包装器协议 — 装饰 Filter.apply()，注入横切关注点。

    典型用法:
        security_wrapper.wrap(clean_filter)
        → 返回一个新 Filter，其 apply() 先做权限检查再调用原 apply()
    """

    def wrap(self, filter_: Filter) -> Filter: ...


# ─── Pipeline ──────────────────────────────────────────────

@dataclass
class PipelineConfig:
    """Pipeline 运行时配置。"""
    verbose: bool = False
    stop_on_error: bool = True
    max_retries: int = 1


@dataclass
class PipelineResult:
    """Pipeline 执行结果。"""
    success: bool
    final_context: PipelineContext
    executed_filters: list[str] = field(default_factory=list)
    failed_at: str | None = None
    error: str | None = None


class Pipeline:
    """管道管理器 — Chain of Resp. 模式执行 Filter 链。

    用法:
        pipeline = Pipeline(filters=[f1, f2, f3], wrappers=[security_wrapper])
        result = pipeline.execute(initial_context)
    """

    def __init__(
        self,
        filters: list[Filter],
        wrappers: list[Wrapper] | None = None,
        config: PipelineConfig | None = None,
    ):
        self._raw_filters = filters
        self._wrappers = wrappers or []
        self._config = config or PipelineConfig()
        self._filters = self._apply_wrappers(filters)

    def _apply_wrappers(self, filters: list[Filter]) -> list[Filter]:
        """将 Wrapper 按顺序装饰每个 Filter。"""
        result = list(filters)
        for wrapper in self._wrappers:
            result = [wrapper.wrap(f) for f in result]
        return result

    def execute(self, ctx: PipelineContext) -> PipelineResult:
        """按顺序执行 Filter 链。"""
        executed: list[str] = []
        current_ctx = ctx

        for filter_ in self._filters:
            try:
                if self._config.verbose:
                    logger.info(f"[Pipeline] Executing: {filter_.name}")

                current_ctx = filter_.apply(current_ctx)
                executed.append(filter_.name)

            except Exception as e:
                logger.error(f"[Pipeline] Failed at {filter_.name}: {e}")
                if self._config.stop_on_error:
                    return PipelineResult(
                        success=False,
                        final_context=current_ctx,
                        executed_filters=executed,
                        failed_at=filter_.name,
                        error=str(e),
                    )

        return PipelineResult(
            success=True,
            final_context=current_ctx,
            executed_filters=executed,
        )

    def resume(
        self, ctx: PipelineContext, from_filter: str
    ) -> PipelineResult:
        """从指定 Filter 恢复执行。"""
        start_idx = next(
            (i for i, f in enumerate(self._filters) if f.name == from_filter),
            None,
        )
        if start_idx is None:
            return PipelineResult(
                success=False,
                final_context=ctx,
                error=f"Filter not found: {from_filter}",
            )

        remaining = self._filters[start_idx:]
        sub_pipeline = Pipeline(
            filters=remaining,
            wrappers=[],  # Wrappers already applied
            config=self._config,
        )
        return sub_pipeline.execute(ctx)


# ─── PipelineFactory ───────────────────────────────────────

@dataclass
class Goal:
    """数据处理目标定义。"""
    asset_type: str
    operation: str
    input_source: str
    role: str = "analyst"
    params: dict | None = None
    policy_override: dict | None = None


class PipelineFactory:
    """流水线工厂 — Factory Method 从 goal_routing.json 构建 Pipeline。

    用法:
        factory = PipelineFactory("configs/goal_routing.json")
        pipeline = factory.create(goal, cluster)
    """

    def __init__(self, routing_path: str | Path):
        with open(routing_path, encoding="utf-8") as f:
            self._routing: dict = json.load(f)

    def create(
        self,
        goal: Goal,
        cluster: dict,
        filter_registry: dict[str, Filter],
        wrappers: list[Wrapper] | None = None,
    ) -> Pipeline:
        """根据 Goal 和属性簇构建 Pipeline。"""
        operation_routes = self._routing.get("goal_routing", {}).get(
            goal.operation, []
        )
        if not operation_routes:
            raise ValueError(
                f"No route defined for operation: {goal.operation}"
            )

        filters: list[Filter] = []
        for step_def in operation_routes:
            step_name = step_def["step"]
            filter_ = filter_registry.get(step_name)
            if filter_ is None:
                logger.warning(
                    f"Filter not found: {step_name}, skipping"
                )
                continue
            filters.append(filter_)

        return Pipeline(filters=filters, wrappers=wrappers)
