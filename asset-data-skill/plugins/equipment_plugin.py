"""Equipment Plugin: 设备资产类型特定逻辑 — TC4 插件系统。

提供设备特有的计算逻辑：
- 直线折旧法计算
- 双倍余额递减法计算
- 残值估算

Author: asset-data-skill
"""

from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Any

logger = logging.getLogger(__name__)


def straight_line_depreciation(
    purchase_price: float,
    residual_rate: float,
    useful_life_years: int,
) -> dict[str, float]:
    """直线折旧法：每年折旧额相等。

    annual = purchase_price * (1 - residual_rate) / useful_life_years
    """
    if useful_life_years <= 0:
        return {"annual_depreciation": 0.0}

    annual = purchase_price * (1 - residual_rate) / useful_life_years
    monthly = annual / 12

    return {
        "annual_depreciation": round(annual, 2),
        "monthly_depreciation": round(monthly, 2),
        "depreciation_method": "straight_line",
    }


def double_declining_depreciation(
    purchase_price: float,
    residual_rate: float,
    useful_life_years: int,
    current_year: int,
) -> dict[str, float]:
    """双倍余额递减法：前期折旧多，后期折旧少。

    rate = 2 / useful_life_years
    每年：book_value × rate（不低于残值）
    """
    if useful_life_years <= 0:
        return {"annual_depreciation": 0.0}

    rate = 2.0 / useful_life_years
    residual = purchase_price * residual_rate
    book_value = purchase_price
    annual = book_value * rate

    # 不低于残值
    if book_value - annual < residual:
        annual = book_value - residual

    return {
        "annual_depreciation": round(annual, 2),
        "depreciation_rate": round(rate, 4),
        "book_value": round(book_value, 2),
        "residual_value": round(residual, 2),
        "depreciation_method": "double_declining_balance",
    }


def compute_current_value(
    purchase_price: float,
    annual_depreciation: float,
    purchase_date: str | date | None,
    current_date: date | None = None,
) -> dict[str, Any]:
    """计算当前账面价值。

    current_value = purchase_price - annual_depreciation × years_elapsed
    """
    if current_date is None:
        current_date = date.today()

    if purchase_date is None:
        return {
            "current_value": purchase_price,
            "years_elapsed": None,
            "note": "Purchase date unknown, assuming original value",
        }

    if isinstance(purchase_date, str):
        purchase_date = date.fromisoformat(purchase_date)

    years_elapsed = (current_date - purchase_date).days / 365.25
    accumulated = annual_depreciation * years_elapsed
    current_value = max(0, purchase_price - accumulated)

    return {
        "current_value": round(current_value, 2),
        "years_elapsed": round(years_elapsed, 2),
        "accumulated_depreciation": round(accumulated, 2),
    }
