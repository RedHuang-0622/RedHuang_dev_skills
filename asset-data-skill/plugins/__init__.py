"""Plugins package: 资产类型特定逻辑插件。

每个插件提供该资产类型特有的校验器、变换器、分析器。
通过属性簇的 validator 字段引用插件中的校验器函数。

插件注册表:
    REGISTRY = {
        "imo_validator": ship_plugin.imo_validator,
        "tonnage_converter": ship_plugin.tonnage_converter,
    }
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

# 插件注册表：{validator_name: callable}
REGISTRY: dict[str, Callable[..., Any]] = {}


def register_plugin(name: str, func: Callable[..., Any]) -> None:
    """注册插件函数。"""
    REGISTRY[name] = func
    logger.debug(f"Plugin registered: {name}")


def get_plugin(name: str) -> Callable[..., Any] | None:
    """获取已注册的插件函数。"""
    return REGISTRY.get(name)


# 自动注册内置插件
def _register_builtins() -> None:
    try:
        from . import ship_plugin
        register_plugin("imo_validator", ship_plugin.imo_validator)
    except ImportError:
        pass

    try:
        from . import equipment_plugin
        register_plugin("straight_line_depreciation", equipment_plugin.straight_line_depreciation)
        register_plugin("double_declining_depreciation", equipment_plugin.double_declining_depreciation)
        register_plugin("compute_current_value", equipment_plugin.compute_current_value)
    except ImportError:
        pass


_register_builtins()
