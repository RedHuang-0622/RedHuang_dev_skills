"""Ship Plugin: 船舶资产类型特定逻辑 — TC4 插件系统。

提供船舶特有的校验器和变换逻辑：
- IMO 编号校验（7 位数字 + 校验位）
- 吨位换算（GT → DWT 估算）
- 船龄计算与折旧

Author: asset-data-skill
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def imo_validator(series, field_name: str) -> list[dict]:
    """IMO 编号校验器。

    IMO 编号规则：7 位数字，第 7 位为校验位。
    校验算法：每位 × (7-pos)，和 mod 10 = 校验位。
    """
    issues: list[dict] = []

    for idx, val in series.dropna().items():
        if not isinstance(val, (str, int)):
            continue

        imo = str(int(val)).zfill(7)
        if len(imo) != 7 or not imo.isdigit():
            issues.append({
                "field": field_name,
                "row_index": int(idx),
                "description": f"IMO must be 7 digits, got '{val}'",
                "severity": "error",
                "suggestion": "Verify IMO number",
            })
            continue

        # 校验位检查
        try:
            digits = [int(d) for d in imo[:6]]
            check_digit = int(imo[6])
            computed = sum(d * (7 - i) for i, d in enumerate(digits)) % 10
            if computed != check_digit:
                issues.append({
                    "field": field_name,
                    "row_index": int(idx),
                    "description": f"IMO check digit mismatch: expected {computed}, got {check_digit}",
                    "severity": "warning",
                    "suggestion": "Verify IMO number typing",
                })
        except (ValueError, IndexError):
            pass

    return issues


def tonnage_converter(gross_tonnage: float) -> dict[str, float]:
    """吨位换算：GT → 估算 DWT。

    近似公式（适用于商船）：
    - 散货船: DWT ≈ 1.7 × GT
    - 油轮: DWT ≈ 1.9 × GT
    - 集装箱船: DWT ≈ 1.2 × GT
    默认使用 1.6 作为通用系数。
    """
    return {
        "gross_tonnage": gross_tonnage,
        "estimated_dwt": round(gross_tonnage * 1.6, 1),
    }


def compute_ship_age(build_year: int, current_year: int | None = None) -> int | None:
    """计算船龄。"""
    if current_year is None:
        from datetime import datetime
        current_year = datetime.now().year
    if build_year <= 0:
        return None
    return max(0, current_year - build_year)
