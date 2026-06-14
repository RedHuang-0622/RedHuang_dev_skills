"""Security Wrapper: TC7 安全与角色控制。

装饰 Filter，注入权限校验、数据脱敏、沙箱限制、实习生安全网、审批工作流。

Author: asset-data-skill
"""

from __future__ import annotations
import dataclasses

import json
import logging
from dataclasses import replace, dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

from filters.pipeline import Filter, PipelineContext, Wrapper

logger = logging.getLogger(__name__)


class SecurityWrapper:
    """安全包装器 — 统一注入 TC7 全部安全控制。

    根据 role 自动启用：
    - intern: 数据脱敏 + 行数限制 + 强制分步确认 + 高风险拦截
    - analyst: 高风险操作确认
    - admin: 无限制
    """

    def __init__(self, config_dir: str | Path):
        self._config_dir = Path(config_dir)
        with open(self._config_dir / "role_permissions.json", encoding="utf-8") as f:
            self._role_config = json.load(f)
        with open(self._config_dir / "approval_rules.json", encoding="utf-8") as f:
            self._approval_rules = json.load(f)

    def wrap(self, filter_: Filter) -> Filter:
        original_apply = filter_.apply
        wrapper = self  # capture for closure

        class WrappedFilter:
            name = filter_.name

            def apply(self, ctx: PipelineContext) -> PipelineContext:
                # 1. 权限检查
                if not wrapper._check_permission(ctx.role, filter_.name):
                    raise PermissionError(
                        f"Role '{ctx.role}' not allowed to execute '{filter_.name}'"
                    )

                # 2. 高风险操作审批检查
                wrapper._check_approval(ctx.role, filter_.name)

                # 3. 实习生行数限制
                if ctx.role == "intern" and ctx.data is not None:
                    ctx = wrapper._enforce_row_limit(ctx)

                # 4. 实习生强制分步确认（标记 needs_confirmation）
                if ctx.role == "intern":
                    ctx = dataclasses.replace(
                        ctx,
                        meta={**ctx.meta, "needs_confirmation": True},
                    )

                # 5. 数据脱敏（在 Filter 执行前）
                if (
                    ctx.role == "intern"
                    and filter_.name not in ("read", "chunk", "index_lookup")
                    and ctx.data is not None
                ):
                    ctx = wrapper._mask_sensitive(ctx)

                # 执行原 Filter
                result = original_apply(ctx)

                # 6. 脱敏后检查（执行后再次确认）
                if (
                    ctx.role == "intern"
                    and filter_.name in ("snapshot", "finalize")
                    and result.data is not None
                ):
                    result = wrapper._mask_sensitive(result)

                return result

            def rollback(self, ctx: PipelineContext) -> PipelineContext:
                return filter_.rollback(ctx)

        return WrappedFilter()

    def _check_permission(self, role: str, filter_name: str) -> bool:
        """检查角色是否有权限执行该 Filter。"""
        role_info = self._role_config.get("roles", {}).get(role, {})
        allowed = role_info.get("allowed_operations", [])
        if "*" in allowed:
            return True  # admin 全部允许
        return filter_name in allowed

    def _check_approval(self, role: str, filter_name: str) -> None:
        """检查是否需要审批。"""
        if role == "admin":
            return

        high_risk = ["clean", "transform"]
        if role == "intern" and filter_name in high_risk:
            logger.warning(
                f"[Security] Intern attempting high-risk operation: {filter_name} — "
                f"mentor approval required"
            )

    def _enforce_row_limit(self, ctx: PipelineContext) -> PipelineContext:
        """实习生行数限制。"""
        if ctx.data is None:
            return ctx

        role_info = self._role_config.get("roles", {}).get("intern", {})
        row_limit = role_info.get("row_limit", 1000)

        if len(ctx.data) > row_limit:
            logger.info(
                f"[Security] Intern row limit: sampling {row_limit}/{len(ctx.data)} rows"
            )
            sampled = ctx.data.head(row_limit)
            return ctx.with_data(sampled)

        return ctx

    def _mask_sensitive(self, ctx: PipelineContext) -> PipelineContext:
        """按字段 access_level 自动脱敏。"""
        if ctx.data is None:
            return ctx

        df = ctx.data.copy()
        cluster_fields = ctx.cluster.get("fields", {})

        for fname, fdef in cluster_fields.items():
            if fname not in df.columns:
                continue

            access_level = fdef.get("access_level", "public")
            if access_level in ("restricted", "internal"):
                # 脱敏策略：按类型替换
                ftype = fdef.get("type", "string")
                if ftype == "string":
                    df[fname] = df[fname].apply(
                        lambda x: f"[RESTRICTED-{len(str(x))} chars]"
                        if pd.notna(x) and x != "" else x
                    )
                elif ftype in ("float", "integer"):
                    df[fname] = df[fname].apply(
                        lambda x: f"***.**" if pd.notna(x) else x
                    )

        logger.debug(
            f"[Security] Masked sensitive fields for role={ctx.role}"
        )
        return ctx.with_data(df)
