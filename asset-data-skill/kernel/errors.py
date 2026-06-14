"""错误体系 — 系统级异常层次。

设计原则:
- 模块级基类 + ≤3 层子类
- 禁止裸 raise Exception
- 每个异常有清晰的错误码和人类可读消息

Author: asset-data-skill
"""

from __future__ import annotations


class AssetDataError(Exception):
    """资产数据处理系统基类异常。"""
    code: str = "ASSET_DATA_ERROR"

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        if code:
            self.code = code


# ─── 配置异常 (继承深度 1) ────────────────────────────

class ConfigError(AssetDataError):
    """配置相关异常基类。"""
    code = "CONFIG_ERROR"


class ClusterNotFoundError(ConfigError):
    """属性簇未找到。"""
    code = "CLUSTER_NOT_FOUND"


class InvalidClusterError(ConfigError):
    """属性簇格式无效。"""
    code = "INVALID_CLUSTER"


class InheritanceDepthError(ConfigError):
    """属性簇继承深度超限。"""
    code = "INHERITANCE_DEPTH_EXCEEDED"


# ─── 数据处理异常 (继承深度 1) ─────────────────────────

class ProcessingError(AssetDataError):
    """数据处理异常基类。"""
    code = "PROCESSING_ERROR"


class ExtractionError(ProcessingError):
    """条目提取失败。"""
    code = "EXTRACTION_FAILED"


class ValidationError(ProcessingError):
    """数据校验失败。"""
    code = "VALIDATION_FAILED"


class NormalizationError(ProcessingError):
    """标准化失败。"""
    code = "NORMALIZATION_FAILED"


class FormatError(ProcessingError):
    """数据格式不支持或损坏。"""
    code = "FORMAT_ERROR"


# ─── 安全异常 (继承深度 1) ─────────────────────────────

class SecurityError(AssetDataError):
    """安全相关异常基类。"""
    code = "SECURITY_ERROR"


class PermissionDeniedError(SecurityError):
    """权限不足。"""
    code = "PERMISSION_DENIED"


class ApprovalRequiredError(SecurityError):
    """需要审批。"""
    code = "APPROVAL_REQUIRED"

    def __init__(self, message: str, ticket_id: str | None = None):
        super().__init__(message)
        self.ticket_id = ticket_id


# ─── 生命周期异常 (继承深度 1) ─────────────────────────

class LifecycleError(AssetDataError):
    """生命周期管理异常基类。"""
    code = "LIFECYCLE_ERROR"


class ArchiveError(LifecycleError):
    """归档失败。"""
    code = "ARCHIVE_FAILED"


class SecureDeleteError(LifecycleError):
    """安全删除失败。"""
    code = "SECURE_DELETE_FAILED"
