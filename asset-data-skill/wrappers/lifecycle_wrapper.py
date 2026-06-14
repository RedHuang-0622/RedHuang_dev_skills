"""Lifecycle Wrapper: TC6 生命周期管理。

装饰 Filter，注入 TTL 策略和备份标记。
在 finalize Filter 执行时将生命周期策略写入 meta.json。

Author: asset-data-skill
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ..filters.pipeline import Filter, PipelineContext, Wrapper

logger = logging.getLogger(__name__)


class LifecycleWrapper:
    """生命周期包装器 — 注入 TTL 策略。

    职责:
    - finalize Filter 执行后将生命周期策略写入 meta.json
    - 实习生任务强制 supervised_short_term 策略
    - 支持任务级 policy_override
    """

    def __init__(self, config_dir: str | Path):
        self._config_dir = Path(config_dir)
        with open(self._config_dir / "lifecycle_policies.json", encoding="utf-8") as f:
            self._policies = json.load(f)

    def wrap(self, filter_: Filter) -> Filter:
        original_apply = filter_.apply
        wrapper = self

        class WrappedFilter:
            name = filter_.name

            def apply(self, ctx: PipelineContext) -> PipelineContext:
                result = original_apply(ctx)

                # 在 finalize Filter 后注入生命周期策略
                if filter_.name == "finalize":
                    result = wrapper._attach_lifecycle(result)

                return result

            def rollback(self, ctx: PipelineContext) -> PipelineContext:
                return filter_.rollback(ctx)

        return WrappedFilter()

    def _attach_lifecycle(self, ctx: PipelineContext) -> PipelineContext:
        """附加生命周期策略到 Context。"""
        # 1. 从属性簇获取策略名
        cluster_policy_name = ctx.cluster.get("lifecycle", {}).get(
            "default_ttl_days"
        )
        if cluster_policy_name is None:
            cluster_policy_name = "short_term"

        # 2. 角色覆盖：intern → supervised_short_term
        if ctx.role == "intern":
            policy_name = "supervised_short_term"
        else:
            policy_name = ctx.meta.get("policy_override", {}).get(
                "policy_name", "short_term"
            )

        # 3. 加载策略详情
        policy = self._policies.get("policies", {}).get(policy_name, {})
        if not policy:
            policy = self._policies.get("policies", {}).get("short_term", {})

        # 4. 写入 Context meta
        new_meta = {**ctx.meta, "lifecycle_policy": policy}
        logger.info(
            f"[Lifecycle] Attached policy '{policy_name}' "
            f"(TTL: {policy.get('default_ttl_days', '?')} days)"
        )

        return object.__replace__(ctx, meta=new_meta)
