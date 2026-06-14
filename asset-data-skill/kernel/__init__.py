"""Kernel package: 微内核组件。

内核提供最简功能：
- scheduler: 任务调度 — 接收 Goal → 加载插件 → 执行 Pipeline
- filesystem: 文件系统约定 — task_cache 目录结构
- packet: 数据包格式 — NormalizedPacket 定义
- errors: 错误体系 — 系统级异常层次
- hooks: 插件钩子 — PluginProtocol 定义
"""

from .errors import AssetDataError
from .packet import NormalizedPacket
from .hooks import PluginProtocol, PluginRegistry

__all__ = [
    "AssetDataError",
    "NormalizedPacket",
    "PluginProtocol",
    "PluginRegistry",
]
