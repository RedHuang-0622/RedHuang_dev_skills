"""Wrappers package: 横切关注点 Wrapper 实现。

Wrapper 按装饰器模式注入横切能力:
- security_wrapper: TC7 安全 + RBAC + 脱敏 + 实习生安全网
- lifecycle_wrapper: TC6 生命周期 TTL 策略注入
- adaptive_wrapper: TC8 自适应数据特征检测
"""

from .security_wrapper import SecurityWrapper
from .lifecycle_wrapper import LifecycleWrapper
from .adaptive_wrapper import AdaptiveWrapper

__all__ = [
    "SecurityWrapper",
    "LifecycleWrapper",
    "AdaptiveWrapper",
]
