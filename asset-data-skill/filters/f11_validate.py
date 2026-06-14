"""f11_validate: 数据校验 Filter — TC4 处理逻辑。

职责: 模式校验、跨字段逻辑校验、校验失败建议生成。
基于属性簇字段定义（type/min/max/pattern/enum/validator）执行校验。

Author: asset-data-skill
"""

from __future__ import annotations
import dataclasses

import logging
import re
from dataclasses import replace, dataclass
from typing import Any, Callable

import pandas as pd

from .context import PipelineContext
from .pipeline import Filter

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """校验问题。"""
    field: str
    row_index: int
    description: str
    severity: str  # "error" | "warning" | "suggestion"
    suggestion: str | None = None


class ValidatorFilter:
    """数据校验 Filter — 按属性簇定义逐字段校验。

    校验规则:
    - type: 类型匹配
    - required: 非空
    - min/max: 数值范围
    - pattern: 正则匹配
    - enum: 枚举值
    - validator: 自定义校验器

    校验结果写入 ctx.meta["validation_issues"] + ctx.metrics。
    """

    name = "validate"

    def __init__(self, custom_validators: dict[str, Callable[..., Any]] | None = None):
        self._validators = custom_validators or {}

    def apply(self, ctx: PipelineContext) -> PipelineContext:
        df = ctx.data
        if df is None:
            logger.warning(f"[{self.name}] No data to validate")
            return ctx

        cluster_fields = ctx.cluster.get("fields", {})
        issues: list[ValidationIssue] = []

        for fname, fdef in cluster_fields.items():
            if fname not in df.columns:
                if fdef.get("required"):
                    issues.append(
                        ValidationIssue(
                            field=fname,
                            row_index=-1,
                            description=f"Required field '{fname}' not found in data",
                            severity="error",
                        )
                    )
                continue

            series = df[fname]

            # Required check
            if fdef.get("required"):
                na_mask = series.isna()
                if na_mask.any():
                    for idx in series[na_mask].index:
                        issues.append(
                            ValidationIssue(
                                field=fname,
                                row_index=int(idx),
                                description=f"Required field '{fname}' is null",
                                severity="error",
                                suggestion="Fill value or remove row",
                            )
                        )

            # Type check
            expected_type = fdef.get("type")
            if expected_type:
                type_issues = self._check_type(
                    series, fname, expected_type
                )
                issues.extend(type_issues)

            # Range check
            if "min" in fdef or "max" in fdef:
                range_issues = self._check_range(series, fname, fdef)
                issues.extend(range_issues)

            # Pattern check
            if fdef.get("pattern"):
                pattern_issues = self._check_pattern(series, fname, fdef["pattern"])
                issues.extend(pattern_issues)

            # Enum check
            if fdef.get("enum"):
                enum_issues = self._check_enum(series, fname, fdef["enum"])
                issues.extend(enum_issues)

            # Custom validator
            validator_name = fdef.get("validator")
            if validator_name and validator_name in self._validators:
                custom_issues = self._validators[validator_name](series, fname)
                issues.extend(custom_issues)

        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]
        suggestions = [i for i in issues if i.severity == "suggestion"]

        logger.info(
            f"[{self.name}] {len(errors)} errors, {len(warnings)} warnings, "
            f"{len(suggestions)} suggestions"
        )

        new_meta = {
            **ctx.meta,
            "validation_issues": [vars(i) for i in issues],
            "validation_error_count": len(errors),
            "validation_warning_count": len(warnings),
        }

        return (
            dataclasses.replace(ctx, meta=new_meta)
            .with_metric("validation_errors", len(errors))
            .with_metric("validation_warnings", len(warnings))
        )

    def _check_type(
        self, series: pd.Series, fname: str, expected: str
    ) -> list[ValidationIssue]:
        """检查列类型是否匹配预期。"""
        issues: list[ValidationIssue] = []

        if expected in ("float", "integer"):
            if not pd.api.types.is_numeric_dtype(series):
                # 检查是否包含非数值
                non_numeric = series.apply(
                    lambda x: isinstance(x, str) and not x.replace(".", "").replace("-", "").isdigit()
                    if pd.notna(x) else False
                )
                for idx in series[non_numeric].index[:10]:  # 最多报告 10 行
                    issues.append(
                        ValidationIssue(
                            field=fname,
                            row_index=int(idx),
                            description=f"Expected {expected}, got '{series[idx]}'",
                            severity="warning",
                            suggestion="Auto-clean or manually fix",
                        )
                    )

        return issues

    def _check_range(
        self, series: pd.Series, fname: str, fdef: dict
    ) -> list[ValidationIssue]:
        """检查数值范围。"""
        issues: list[ValidationIssue] = []

        if not pd.api.types.is_numeric_dtype(series):
            return issues

        if "min" in fdef:
            below = series < fdef["min"]
            for idx in series[below].index[:10]:
                issues.append(
                    ValidationIssue(
                        field=fname,
                        row_index=int(idx),
                        description=f"Value {series[idx]} below min {fdef['min']}",
                        severity="error",
                        suggestion="Verify or fix value",
                    )
                )

        if "max" in fdef:
            above = series > fdef["max"]
            for idx in series[above].index[:10]:
                issues.append(
                    ValidationIssue(
                        field=fname,
                        row_index=int(idx),
                        description=f"Value {series[idx]} above max {fdef['max']}",
                        severity="error",
                        suggestion="Verify or fix value",
                    )
                )

        return issues

    def _check_pattern(
        self, series: pd.Series, fname: str, pattern: str
    ) -> list[ValidationIssue]:
        """检查正则模式。"""
        issues: list[ValidationIssue] = []
        regex = re.compile(pattern)

        for idx, val in series.dropna().items():
            if isinstance(val, str) and not regex.match(str(val)):
                issues.append(
                    ValidationIssue(
                        field=fname,
                        row_index=int(idx),
                        description=f"Value '{val}' doesn't match pattern '{pattern}'",
                        severity="warning",
                    )
                )
                if len(issues) >= 10:
                    break

        return issues

    def _check_enum(
        self, series: pd.Series, fname: str, allowed: list[str]
    ) -> list[ValidationIssue]:
        """检查枚举值。"""
        issues: list[ValidationIssue] = []
        allowed_set = set(allowed)

        for idx, val in series.dropna().items():
            if str(val) not in allowed_set:
                issues.append(
                    ValidationIssue(
                        field=fname,
                        row_index=int(idx),
                        description=f"Value '{val}' not in allowed: {allowed}",
                        severity="error",
                        suggestion=f"Choose from: {allowed}",
                    )
                )
                if len(issues) >= 10:
                    break

        return issues

    def rollback(self, ctx: PipelineContext) -> PipelineContext:
        new_meta = {
            k: v for k, v in ctx.meta.items()
            if k not in ("validation_issues", "validation_error_count", "validation_warning_count")
        }
        return dataclasses.replace(ctx, meta=new_meta)
