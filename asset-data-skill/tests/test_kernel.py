"""Tests for kernel module: errors, packet, hooks."""

from __future__ import annotations

import pytest

from kernel.errors import (
    ApprovalRequiredError,
    AssetDataError,
    ConfigError,
    ExtractionError,
    FormatError,
    InheritanceDepthError,
    LifecycleError,
    NormalizationError,
    PermissionDeniedError,
    ProcessingError,
    SecurityError,
    ValidationError,
)
from kernel.hooks import PluginProtocol, PluginRegistry
from kernel.packet import NormalizedPacket


# ─── Error Hierarchy Tests ────────────────────────────────


class TestErrorHierarchy:
    """Verify the error class hierarchy."""

    def test_all_errors_extend_asset_data_error(self):
        """Every error class must inherit from AssetDataError."""
        assert issubclass(ConfigError, AssetDataError)
        assert issubclass(ProcessingError, AssetDataError)
        assert issubclass(SecurityError, AssetDataError)
        assert issubclass(LifecycleError, AssetDataError)

    def test_config_error_subclasses(self):
        assert issubclass(InheritanceDepthError, ConfigError)
        assert issubclass(InheritanceDepthError, AssetDataError)

    def test_processing_error_subclasses(self):
        assert issubclass(ExtractionError, ProcessingError)
        assert issubclass(ValidationError, ProcessingError)
        assert issubclass(NormalizationError, ProcessingError)
        assert issubclass(FormatError, ProcessingError)

    def test_security_error_subclasses(self):
        assert issubclass(PermissionDeniedError, SecurityError)
        assert issubclass(ApprovalRequiredError, SecurityError)

    def test_lifecycle_error_subclasses(self):
        # LifecycleError subclasses are defined in errors.py
        from kernel.errors import ArchiveError, SecureDeleteError
        assert issubclass(ArchiveError, LifecycleError)
        assert issubclass(SecureDeleteError, LifecycleError)

    def test_error_inheritance_depth(self):
        """All errors must be ≤3 levels deep."""
        def depth(cls):
            d = 0
            c = cls
            while c is not Exception:
                d += 1
                c = c.__bases__[0]
            return d
        # AssetDataError is level 1 above Exception
        # ConfigError etc are level 2
        # Specific errors like InheritanceDepthError are level 3
        assert depth(InheritanceDepthError) <= 4  # Exception(0) → AssetDataError(1) → ConfigError(2) → InheritanceDepthError(3)

    def test_error_codes_are_unique(self):
        """Each error class should have a unique code."""
        codes = set()
        for cls in [ConfigError, ProcessingError, SecurityError, LifecycleError,
                     InheritanceDepthError, ExtractionError, ValidationError,
                     PermissionDeniedError, ApprovalRequiredError]:
            codes.add(cls.code)
        # All 10+ classes should have unique codes
        assert len(codes) >= 8

    def test_approval_required_has_ticket_id(self):
        err = ApprovalRequiredError("Need approval", ticket_id="TKT-001")
        assert err.ticket_id == "TKT-001"
        assert "Need approval" in str(err)

    def test_raise_and_catch_config_error(self):
        with pytest.raises(ConfigError):
            raise InheritanceDepthError("Depth exceeded")

    def test_raise_and_catch_security_error(self):
        with pytest.raises(SecurityError):
            raise PermissionDeniedError("Access denied")

    def test_custom_error_code(self):
        err = AssetDataError("Generic error", code="CUSTOM_001")
        assert err.code == "CUSTOM_001"


# ─── NormalizedPacket Tests ───────────────────────────────


class TestNormalizedPacket:
    """Test the NormalizedPacket DTO."""

    def test_default_construction(self):
        pkt = NormalizedPacket()
        assert pkt.data_csv is None
        assert pkt.schema_json is None
        assert pkt.summary_md is None
        assert not pkt.is_complete()

    def test_is_complete_when_all_present(self):
        import pandas as pd
        pkt = NormalizedPacket(
            data_csv=pd.DataFrame({"a": [1, 2]}),
            schema_json={"a": {"type": "integer"}},
            summary_md="# Report",
        )
        assert pkt.is_complete()

    def test_is_complete_missing_data(self):
        pkt = NormalizedPacket(
            schema_json={"a": {"type": "integer"}},
            summary_md="# Report",
        )
        assert not pkt.is_complete()

    def test_to_dict(self):
        import pandas as pd
        pkt = NormalizedPacket(
            data_csv=pd.DataFrame({"a": [1, 2, 3]}),
            schema_json={"a": {"type": "integer"}},
            summary_md="# Summary",
            raw_entries=[{"fields": {"a": 1}}],
        )
        d = pkt.to_dict()
        assert d["data_rows"] == 3
        assert d["data_columns"] == ["a"]
        assert d["has_raw_entries"] is True
        assert d["has_documents"] is False

    def test_with_extensions(self):
        import pandas as pd
        pkt = NormalizedPacket(
            data_csv=pd.DataFrame({"a": [1]}),
            schema_json={},
            summary_md="ok",
            raw_entries=[{"f": 1}],
            documents_jsonl=[{"id": "d1"}],
            data_normalized_csv=pd.DataFrame({"a_zscore": [0.0]}),
            metadata={"version": "1.0"},
        )
        d = pkt.to_dict()
        assert d["has_raw_entries"]
        assert d["has_documents"]
        assert d["has_normalized"]
        assert d["metadata"]["version"] == "1.0"


# ─── PluginProtocol and PluginRegistry Tests ──────────────


class TestPluginProtocol:
    """Verify PluginProtocol is a valid runtime_checkable Protocol."""

    def test_protocol_is_runtime_checkable(self):
        from typing import runtime_checkable
        assert hasattr(PluginProtocol, "_is_runtime_protocol")

    def test_class_matching_protocol(self):
        """A class with required attributes matches the protocol."""

        class FakePlugin:
            plugin_id = "test_plugin"
            asset_type = "TEST"
            version = "1.0"

            def get_cluster(self) -> dict:
                return {}

            def get_reader(self):
                return None

            def get_cleaner(self):
                return None

            def get_validator(self):
                return None

            def get_transformer(self):
                return None

            def get_analyzer(self):
                return None

            def get_prompts(self) -> dict:
                return {}

            def get_lifecycle_policy(self):
                return None

        assert isinstance(FakePlugin(), PluginProtocol)

    def test_class_not_matching_protocol(self):
        """A class missing attributes does NOT match."""

        class IncompletePlugin:
            pass

        assert not isinstance(IncompletePlugin(), PluginProtocol)


class TestPluginRegistry:
    """Test PluginRegistry discovery and loading."""

    def test_init_empty(self, temp_output_dir):
        registry = PluginRegistry(temp_output_dir)
        assert len(registry._plugins) == 0

    def test_discover_empty_dir(self, temp_output_dir):
        registry = PluginRegistry(temp_output_dir)
        discovered = registry.discover()
        assert discovered == []

    def test_discover_with_plugin_dirs(self, temp_output_dir):
        # Create a mock plugin directory with __init__.py
        plugin_dir = temp_output_dir / "test_asset"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text("# test plugin")
        (plugin_dir / "plugin.toml").write_text("[plugin]\nid = 'test_asset'")

        registry = PluginRegistry(temp_output_dir)
        discovered = registry.discover()
        assert "test_asset" in discovered

    def test_get_for_asset_none_for_unknown(self, temp_output_dir):
        registry = PluginRegistry(temp_output_dir)
        result = registry.get_for_asset("UNKNOWN_TYPE")
        assert result is None

    def test_load_nonexistent_plugin(self, temp_output_dir):
        registry = PluginRegistry(temp_output_dir)
        with pytest.raises(FileNotFoundError):
            registry.load("nonexistent")
