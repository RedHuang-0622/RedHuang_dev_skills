"""Plugin Hooks: 插件钩子体系定义。

定义插件必须实现的协议和注册中心。
内核通过 Protocol 反向依赖插件，实现依赖倒置。

Author: asset-data-skill
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ─── Plugin Protocol ─────────────────────────────────────

@runtime_checkable
class PluginProtocol(Protocol):
    """插件必须满足的协议 — 内核定义，插件实现。

    每个资产类型对应一个插件，提供：
    - 属性簇定义
    - 特定读取/清洗/校验/变换/分析逻辑（可选，缺失则使用通用实现）
    - 提示词变体（可选，覆盖全局默认）
    - 生命周期策略（可选，覆盖属性簇默认）
    """

    plugin_id: str
    asset_type: str
    version: str

    def get_cluster(self) -> dict: ...

    def get_reader(self) -> callable | None: ...
    def get_cleaner(self) -> callable | None: ...
    def get_validator(self) -> callable | None: ...
    def get_transformer(self) -> callable | None: ...
    def get_analyzer(self) -> callable | None: ...

    def get_prompts(self) -> dict[str, str]: ...
    def get_lifecycle_policy(self) -> dict | None: ...


# ─── Plugin Registry ─────────────────────────────────────

class PluginRegistry:
    """插件注册表 — 发现 + 加载 + 版本管理。

    扫描 plugins/ 目录发现插件（通过 plugin.toml 或约定），
    按需加载插件实例，支持热更新。

    用法:
        registry = PluginRegistry("plugins/")
        registry.discover()
        plugin = registry.get_for_asset("RE_MORTGAGE")
        cluster = plugin.get_cluster()
    """

    def __init__(self, plugins_dir: str | Path):
        self._plugins_dir = Path(plugins_dir)
        self._plugins: dict[str, PluginProtocol] = {}
        self._asset_index: dict[str, str] = {}  # asset_type → plugin_id

    def discover(self) -> list[str]:
        """扫描 plugins/ 目录发现插件。

        发现策略:
        1. 查找 plugin.toml 文件
        2. 查找 __init__.py 中的 PluginProtocol 实现
        """
        discovered: list[str] = []

        for path in self._plugins_dir.iterdir():
            if not path.is_dir() or path.name.startswith("_"):
                continue

            # 检查 plugin.toml
            toml_path = path / "plugin.toml"
            if toml_path.exists():
                discovered.append(path.name)
                continue

            # 检查是否有 __init__.py
            init_path = path / "__init__.py"
            if init_path.exists():
                discovered.append(path.name)

        logger.info(f"Discovered {len(discovered)} plugins: {discovered}")
        return discovered

    def load(self, plugin_id: str) -> PluginProtocol:
        """加载指定插件。"""
        if plugin_id in self._plugins:
            return self._plugins[plugin_id]

        plugin_dir = self._plugins_dir / plugin_id
        if not plugin_dir.exists():
            raise FileNotFoundError(f"Plugin not found: {plugin_id}")

        # 动态加载（简化实现：要求插件目录下有实现类）
        import importlib
        module = importlib.import_module(f"plugins.{plugin_id}")
        # 查找 PluginProtocol 实现
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and PluginProtocol in getattr(attr, "__mro__", [])
                and attr is not PluginProtocol
            ):
                plugin = attr(plugin_dir)
                self._plugins[plugin_id] = plugin
                self._asset_index[plugin.asset_type] = plugin_id
                return plugin

        raise ValueError(f"No PluginProtocol implementation found in: {plugin_id}")

    def get_for_asset(self, asset_type: str) -> PluginProtocol | None:
        """根据资产类型获取对应插件。"""
        plugin_id = self._asset_index.get(asset_type)
        if plugin_id:
            return self._plugins.get(plugin_id)

        # 尝试发现并加载
        for pid in self.discover():
            try:
                plugin = self.load(pid)
                if plugin.asset_type == asset_type:
                    return plugin
            except Exception as e:
                logger.warning(f"Failed to load plugin {pid}: {e}")

        return None

    def reload(self, plugin_id: str) -> None:
        """热更新指定插件。"""
        if plugin_id in self._plugins:
            del self._plugins[plugin_id]
        self.load(plugin_id)
        logger.info(f"Plugin reloaded: {plugin_id}")
