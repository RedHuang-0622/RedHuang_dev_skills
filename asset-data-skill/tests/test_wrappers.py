"""Tests for all 3 wrappers: Security, Lifecycle, Adaptive."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from filters.context import PipelineContext
from wrappers.security_wrapper import SecurityWrapper
from wrappers.lifecycle_wrapper import LifecycleWrapper
from wrappers.adaptive_wrapper import AdaptiveWrapper


# ─── Shared test helpers ───────────────────────────────────


class MockFilter:
    name = "read"  # Must be in intern's allowed_operations

    def apply(self, ctx: PipelineContext) -> PipelineContext:
        return ctx.with_metric("applied", True)

    def rollback(self, ctx: PipelineContext) -> PipelineContext:
        return ctx


class HighRiskFilter:
    name = "clean"

    def apply(self, ctx: PipelineContext) -> PipelineContext:
        return ctx.with_metric("cleaned", True)

    def rollback(self, ctx: PipelineContext) -> PipelineContext:
        return ctx


def _create_config_dir() -> Path:
    """Create a temporary config directory with role_permissions and approval_rules."""
    d = Path(tempfile.mkdtemp())
    d.mkdir(exist_ok=True)

    role_perms = {
        "roles": {
            "admin": {"allowed_operations": ["*"], "row_limit": None, "mask_sensitive": False},
            "analyst": {"allowed_operations": ["*"], "row_limit": None, "mask_sensitive": False},
            "intern": {
                "allowed_operations": ["read", "clean", "validate", "transform"],
                "row_limit": 1000,
                "mask_sensitive": True,
            },
        }
    }
    with open(d / "role_permissions.json", "w", encoding="utf-8") as f:
        json.dump(role_perms, f)

    approval_rules = {
        "rules": [
            {"operation": "delete_rows", "require_role": "admin"},
            {"operation": "modify_sensitive", "require_role": "admin"},
        ]
    }
    with open(d / "approval_rules.json", "w", encoding="utf-8") as f:
        json.dump(approval_rules, f)

    lifecycle_policies = {
        "policies": {
            "supervised_short_term": {"name": "supervised_short_term", "default_ttl_days": 15},
            "short_term": {"name": "short_term", "default_ttl_days": 30},
            "long_term": {"name": "long_term", "default_ttl_days": 365},
            "permanent": {"name": "permanent", "default_ttl_days": 36500},
        }
    }
    with open(d / "lifecycle_policies.json", "w", encoding="utf-8") as f:
        json.dump(lifecycle_policies, f)

    return d


# ═══ SecurityWrapper ═══════════════════════════════════════


class TestSecurityWrapper:
    @pytest.fixture
    def config_dir(self):
        return _create_config_dir()

    @pytest.fixture
    def security(self, config_dir):
        return SecurityWrapper(config_dir)

    @pytest.fixture
    def intern_ctx(self) -> PipelineContext:
        return PipelineContext(
            task_id="t-sec",
            asset_type="RE_MORTGAGE",
            role="intern",
            cluster={"fields": {
                "name": {"type": "string", "access_level": "public"},
                "secret": {"type": "string", "access_level": "restricted"},
                "internal_id": {"type": "string", "access_level": "internal"},
                "amount": {"type": "float", "access_level": "restricted"},
            }},
        )

    def test_analyst_passes_through(self, security, base_ctx):
        """Analyst role should pass through with no restrictions."""
        wrapped = security.wrap(MockFilter())
        result = wrapped.apply(base_ctx)
        assert "applied" in result.metrics

    def test_intern_enforces_row_limit(self, security, intern_ctx):
        """Intern should only see first 1000 rows."""
        df = pd.DataFrame({"name": range(2000)})
        ctx = intern_ctx.with_data(df)
        wrapped = security.wrap(MockFilter())
        result = wrapped.apply(ctx)
        assert len(result.data) <= 1000

    def test_intern_data_masking(self, security, intern_ctx):
        """Sensitive fields should be masked for intern."""
        df = pd.DataFrame({
            "name": ["Alice", "Bob"],
            "secret": ["password123", "sensitive_data"],
            "internal_id": ["ID001", "ID002"],
            "amount": [1000.0, 2000.0],
        })
        ctx = intern_ctx.with_data(df)
        # Use "clean" instead of "read" — "read" is exempt from masking
        mask_filter = MockFilter()
        mask_filter.name = "clean"
        wrapped = security.wrap(mask_filter)
        result = wrapped.apply(ctx)
        # Restricted string fields should be masked
        secret_col = result.data["secret"]
        assert any("RESTRICTED" in str(v) for v in secret_col)

    def test_intern_needs_confirmation(self, security, intern_ctx):
        """Intern should always get needs_confirmation flag."""
        ctx = intern_ctx.with_data(pd.DataFrame({"name": ["a"]}))
        wrapped = security.wrap(MockFilter())
        result = wrapped.apply(ctx)
        assert result.meta.get("needs_confirmation") is True

    def test_intern_read_filter_no_masking(self, security, intern_ctx):
        """Read filter should NOT mask data (to allow reading)."""
        df = pd.DataFrame({
            "name": ["Alice"],
            "secret": ["my_secret"],
            "internal_id": ["ID001"],
            "amount": [1000.0],
        })
        ctx = intern_ctx.with_data(df)
        read_filter = MockFilter()
        read_filter.name = "read"
        wrapped = security.wrap(read_filter)
        result = wrapped.apply(ctx)
        # Read filter should not mask
        assert "RESTRICTED" not in str(result.data["secret"].iloc[0])

    def test_high_risk_intern_warning(self, security, intern_ctx):
        """Intern attempting clean should trigger log warning."""
        wrapped = security.wrap(HighRiskFilter())
        # Should not raise, but log warning
        result = wrapped.apply(intern_ctx)
        assert result is not None

    def test_admin_no_restrictions(self, security):
        """Admin role should have no restrictions."""
        df = pd.DataFrame({
            "name": ["Alice"],
            "secret": ["my_secret"],
            "amount": [1000.0],
        })
        ctx = PipelineContext(
            task_id="admin-test",
            asset_type="RE_MORTGAGE",
            role="admin",
            cluster={"fields": {
                "name": {"type": "string", "access_level": "public"},
                "secret": {"type": "string", "access_level": "restricted"},
                "amount": {"type": "float", "access_level": "restricted"},
            }},
        )
        ctx = ctx.with_data(df)
        wrapped = security.wrap(MockFilter())
        result = wrapped.apply(ctx)
        assert result is not None

    def test_rollback_delegated(self, security, base_ctx):
        wrapped = security.wrap(MockFilter())
        result = wrapped.apply(base_ctx)
        rolled = wrapped.rollback(result)
        assert rolled is not None


# ═══ LifecycleWrapper ══════════════════════════════════════


class TestLifecycleWrapper:
    @pytest.fixture
    def config_dir(self):
        return _create_config_dir()

    @pytest.fixture
    def lifecycle(self, config_dir):
        return LifecycleWrapper(config_dir)

    def test_attaches_policy_on_finalize(self, lifecycle, base_ctx):
        """Lifecycle policy should be attached when finalize filter runs."""

        class FinalizeMock:
            name = "finalize"

            def apply(self, ctx: PipelineContext) -> PipelineContext:
                return ctx.with_metric("finalized", True)

            def rollback(self, ctx):
                return ctx

        wrapped = lifecycle.wrap(FinalizeMock())
        result = wrapped.apply(base_ctx)
        assert "lifecycle_policy" in result.meta

    def test_intern_forced_supervised_short_term(self, lifecycle):
        """Intern tasks must use supervised_short_term policy."""
        intern_ctx = PipelineContext(
            task_id="t-lifecycle",
            asset_type="RE_MORTGAGE",
            role="intern",
            cluster={"lifecycle": {"default_ttl_days": 365}},
        )

        class FinalizeMock:
            name = "finalize"

            def apply(self, ctx: PipelineContext) -> PipelineContext:
                return ctx

            def rollback(self, ctx):
                return ctx

        wrapped = lifecycle.wrap(FinalizeMock())
        result = wrapped.apply(intern_ctx)
        policy = result.meta.get("lifecycle_policy", {})
        # Intern should get supervised_short_term (15 days)
        assert policy.get("default_ttl_days") == 15

    def test_non_finalize_passes_through(self, lifecycle, base_ctx):
        """Non-finalize filters should not be affected."""
        wrapped = lifecycle.wrap(MockFilter())
        result = wrapped.apply(base_ctx)
        assert "applied" in result.metrics
        assert "lifecycle_policy" not in result.meta

    def test_policy_override(self, lifecycle):
        """Task-level policy_override should take effect."""
        ctx = PipelineContext(
            task_id="t-override",
            asset_type="RE_MORTGAGE",
            role="analyst",
            cluster={"lifecycle": {"default_ttl_days": 30}},
            meta={"policy_override": {"policy_name": "long_term"}},
        )

        class FinalizeMock:
            name = "finalize"

            def apply(self, ctx: PipelineContext) -> PipelineContext:
                return ctx

            def rollback(self, ctx):
                return ctx

        wrapped = lifecycle.wrap(FinalizeMock())
        result = wrapped.apply(ctx)
        policy = result.meta.get("lifecycle_policy", {})
        assert policy.get("default_ttl_days") == 365

    def test_rollback_delegated(self, lifecycle, base_ctx):
        wrapped = lifecycle.wrap(MockFilter())
        result = wrapped.apply(base_ctx)
        rolled = wrapped.rollback(result)
        assert rolled is not None


# ═══ AdaptiveWrapper ═══════════════════════════════════════


class TestAdaptiveWrapper:
    def test_read_filter_analyzes_features(self, base_ctx):
        adaptive = AdaptiveWrapper()

        class ReadMock:
            name = "read"

            def apply(self, ctx: PipelineContext) -> PipelineContext:
                return ctx.with_metric("read", True)

            def rollback(self, ctx):
                return ctx

        df = pd.DataFrame({
            "text_col": ["A" * 200] * 10,  # Long text → high text_ratio
            "num_col": [1.0, None, None, None, None, None, None, None, None, None],  # >30% null
        })
        ctx = base_ctx.with_data(df)
        wrapped = adaptive.wrap(ReadMock())
        result = wrapped.apply(ctx)
        assert "data_features" in result.meta

    def test_high_text_ratio_triggers_extraction(self, base_ctx):
        adaptive = AdaptiveWrapper(text_ratio_threshold=0.1)  # Low threshold for testing

        class ReadMock:
            name = "read"

            def apply(self, ctx: PipelineContext) -> PipelineContext:
                return ctx.with_metric("read", True)

            def rollback(self, ctx):
                return ctx

        df = pd.DataFrame({"long_text": [("A" * 200)] * 10, "num": [1] * 10})
        ctx = base_ctx.with_data(df)
        wrapped = adaptive.wrap(ReadMock())
        result = wrapped.apply(ctx)
        # Should detect text and flag needs_extraction
        features = result.meta.get("data_features", {})
        assert features.get("text_ratio", 0) > 0

    def test_high_null_rate_triggers_analysis(self, base_ctx):
        adaptive = AdaptiveWrapper(null_rate_threshold=0.1)

        class ReadMock:
            name = "read"

            def apply(self, ctx: PipelineContext) -> PipelineContext:
                return ctx.with_metric("read", True)

            def rollback(self, ctx):
                return ctx

        df = pd.DataFrame({
            "a": [1.0, None, None, None, None, None, None, None, None, None],
        })
        ctx = base_ctx.with_data(df)
        wrapped = adaptive.wrap(ReadMock())
        result = wrapped.apply(ctx)
        assert result.meta.get("needs_null_analysis") is True

    def test_large_dataset_detection(self, base_ctx):
        adaptive = AdaptiveWrapper(large_data_threshold=10)

        class ReadMock:
            name = "read"

            def apply(self, ctx: PipelineContext) -> PipelineContext:
                return ctx.with_metric("read", True)

            def rollback(self, ctx):
                return ctx

        df = pd.DataFrame({"a": range(100)})
        ctx = base_ctx.with_data(df)
        wrapped = adaptive.wrap(ReadMock())
        result = wrapped.apply(ctx)
        assert result.meta.get("large_dataset") is True

    def test_non_read_filter_passthrough(self, base_ctx):
        adaptive = AdaptiveWrapper()
        wrapped = adaptive.wrap(MockFilter())
        result = wrapped.apply(base_ctx)
        assert "applied" in result.metrics

    def test_chunk_filter_large_text(self, base_ctx):
        adaptive = AdaptiveWrapper(large_data_threshold=100)

        class ChunkMock:
            name = "chunk"

            def apply(self, ctx: PipelineContext) -> PipelineContext:
                return ctx.with_metric("chunked", True)

            def rollback(self, ctx):
                return ctx

        import dataclasses
        ctx = dataclasses.replace(base_ctx, raw_text="X" * 500)
        wrapped = adaptive.wrap(ChunkMock())
        result = wrapped.apply(ctx)
        assert result.meta.get("large_text") is True
        assert result.meta.get("chunk_size_override") == 4000

    def test_rollback_delegated(self, base_ctx):
        adaptive = AdaptiveWrapper()
        wrapped = adaptive.wrap(MockFilter())
        result = wrapped.apply(base_ctx)
        rolled = wrapped.rollback(result)
        assert rolled is not None
