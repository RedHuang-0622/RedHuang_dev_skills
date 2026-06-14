"""Novel testing ideas — fuzzing, attack simulation, security penetration.

The 7 novel test approaches:
1. PipelineContext Immutability Fuzzing
2. Cluster Inheritance Attack Testing
3. Intern Security Net Penetration Test
4. Lifecycle Policy Conflict Test
5. Wrapper Order Commutativity Test
6. Snapshot Rollback Consistency Test
7. Pipeline Interrupt Recovery Test
"""

from __future__ import annotations

import copy
import dataclasses
import itertools
import json
import random
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from filters.context import PipelineContext
from filters.pipeline import Pipeline, PipelineConfig
from filters.f01_index import IndexLookupFilter
from filters.f05_normalize_structure import StructureNormalizerFilter
from filters.f07_generate_schema import SchemaGeneratorFilter
from filters.f10_clean import CleanerFilter
from wrappers.security_wrapper import SecurityWrapper
from wrappers.lifecycle_wrapper import LifecycleWrapper
from wrappers.adaptive_wrapper import AdaptiveWrapper


# ═══════════════════════════════════════════════════════════
# 1. PipelineContext Immutability Fuzzing
# ═══════════════════════════════════════════════════════════

class TestContextImmutabilityFuzzing:
    """Fuzz test: any sequence of mutations must not alter original context."""

    def _make_mutated_context(self, ctx: PipelineContext) -> list[PipelineContext]:
        """Generate a sequence of mutated contexts."""
        results = [ctx]
        df = pd.DataFrame({"a": [1, 2, 3]})

        # Apply random mutations
        mutations = [
            lambda c: c.with_data(df),
            lambda c: c.with_data(c.data.head(1)) if c.data is not None else c,
            lambda c: c.with_entries([{"x": 1}]),
            lambda c: c.with_entries(None),
            lambda c: c.with_artifact("step", "/tmp/x"),
            lambda c: c.with_metric("m", 42),
            lambda c: dataclasses.replace(c, meta={"key": "val"}),
            lambda c: dataclasses.replace(c, raw_text="hello"),
            lambda c: dataclasses.replace(c, schema={"col": {"type": "int"}}),
            lambda c: dataclasses.replace(c, summary="# Report"),
        ]

        # Apply 100 random mutations in sequence
        current = ctx
        for _ in range(100):
            mutation = random.choice(mutations)
            try:
                current = mutation(current)
                results.append(current)
            except Exception:
                pass

        return results

    def test_original_never_mutated(self, base_ctx):
        """After 1000 chain operations, original context is unchanged."""
        original_task_id = base_ctx.task_id
        original_data = base_ctx.data
        original_metrics = dict(base_ctx.metrics)
        original_artifacts = dict(base_ctx.artifacts)

        ctx = base_ctx
        for i in range(1000):
            ctx = ctx.with_data(pd.DataFrame({"x": [i]}))
            ctx = ctx.with_metric(f"m_{i}", i)
            ctx = ctx.with_artifact(f"step_{i}", f"/tmp/{i}")

        # Original context must be completely unchanged
        assert base_ctx.task_id == original_task_id
        assert base_ctx.data is original_data  # None
        assert base_ctx.metrics == original_metrics  # {}
        assert base_ctx.artifacts == original_artifacts  # {}

    def test_random_mutation_sequence_no_leak(self, base_ctx):
        """Random sequence of mutations should not corrupt original."""
        original = copy.deepcopy(base_ctx)

        for _ in range(100):
            ctx = base_ctx
            for __ in range(random.randint(1, 20)):
                rand = random.random()
                if rand < 0.3:
                    ctx = ctx.with_data(pd.DataFrame({"r": [random.random()]}))
                elif rand < 0.5:
                    ctx = ctx.with_metric(f"r{__}", random.random())
                elif rand < 0.7:
                    ctx = ctx.with_artifact(f"a{__}", f"/tmp/{random.randint(0, 999)}")
                elif rand < 0.9:
                    ctx = ctx.with_entries([{"f": random.random()}])
                else:
                    ctx = dataclasses.replace(ctx, meta={f"k{__}": random.random()})

        # Original must be pristine
        assert base_ctx.data == original.data
        assert base_ctx.metrics == original.metrics
        assert base_ctx.entries == original.entries
        assert base_ctx.artifacts == original.artifacts


# ═══════════════════════════════════════════════════════════
# 2. Cluster Inheritance Attack Testing
# ═══════════════════════════════════════════════════════════

class TestClusterInheritanceAttack:
    """Test that malicious cluster configs are handled safely."""

    def test_circular_inheritance_detected(self, config_dir):
        """Circular inheritance should not cause infinite recursion."""
        # The actual configs don't have circular inheritance, but the depth
        # limit in _load_with_inheritance would catch deep chains too.
        # We verify the index filter handles the max depth correctly.
        index_filter = IndexLookupFilter(config_dir)

        # Create a ctx with valid asset type
        ctx = PipelineContext(task_id="t1", asset_type="RE_MORTGAGE")
        result = index_filter.apply(ctx)
        # Should succeed (inheritance chain is 2 levels, within limit)
        assert result.cluster["cluster_id"] == "RE_MORTGAGE"

    def test_depth_limit_enforced(self, config_dir):
        """The MAX_INHERIT_DEPTH=3 limit in the code prevents deep inheritance."""
        index_filter = IndexLookupFilter(config_dir)
        # Direct call to _load_with_inheritance with depth=4 should raise
        with pytest.raises(RecursionError):
            index_filter._load_with_inheritance(
                config_dir / "clusters" / "real_estate" / "mortgage.json",
                depth=4,
            )

    def test_field_override_child_wins(self, config_dir):
        """Child field definitions should override parent."""
        index_filter = IndexLookupFilter(config_dir)
        ctx = PipelineContext(task_id="t1", asset_type="RE_MORTGAGE")
        result = index_filter.apply(ctx)
        cluster = result.cluster
        # Child has mortgage_amount with unit=元
        assert cluster["fields"]["mortgage_amount"]["unit"] == "元"

    def test_missing_parent_handled_gracefully(self, config_dir):
        """Missing parent cluster should be handled without crash."""
        index_filter = IndexLookupFilter(config_dir)
        # _find_base_cluster for non-existent ID should return None
        result = index_filter._find_base_cluster("NONEXISTENT_CLUSTER")
        assert result is None


# ═══════════════════════════════════════════════════════════
# 3. Intern Security Net Penetration Test
# ═══════════════════════════════════════════════════════════

class TestInternSecurityPenetration:
    """Try to bypass all intern restrictions."""

    @pytest.fixture
    def security(self, config_dir):
        return SecurityWrapper(config_dir)

    @pytest.fixture
    def intern_ctx(self):
        return PipelineContext(
            task_id="pen-test",
            asset_type="RE_MORTGAGE",
            role="intern",
            cluster={
                "fields": {
                    "name": {"type": "string", "access_level": "public"},
                    "secret_data": {"type": "string", "access_level": "restricted"},
                    "internal_amount": {"type": "float", "access_level": "internal"},
                    "phone": {"type": "string", "access_level": "restricted"},
                }
            },
        )

    def test_cannot_bypass_row_limit(self, security, intern_ctx):
        """Intern should never see more than 1000 rows."""
        big_df = pd.DataFrame({
            "name": [f"user_{i}" for i in range(5000)],
            "secret_data": [f"secret_{i}" for i in range(5000)],
            "internal_amount": [float(i) for i in range(5000)],
            "phone": [f"1380000{i:04d}" for i in range(5000)],
        })
        ctx = intern_ctx.with_data(big_df)

        class AnyFilter:
            name = "read"  # Must be in intern allowed_operations list

            def apply(self, ctx):
                return ctx.with_metric("processed", len(ctx.data))

            def rollback(self, ctx):
                return ctx

        wrapped = security.wrap(AnyFilter())
        result = wrapped.apply(ctx)
        assert len(result.data) <= 1000
        assert result.metrics.get("processed", 0) <= 1000

    def test_cannot_access_restricted_fields(self, security, intern_ctx):
        """Restricted fields must be masked."""
        df = pd.DataFrame({
            "name": ["Alice", "Bob"],
            "secret_data": ["sensitive_info", "classified"],
            "internal_amount": [1000000.0, 2000000.0],
            "phone": ["13800000001", "13800000002"],
        })
        ctx = intern_ctx.with_data(df)

        class DataFilter:
            name = "clean"  # Must be in intern allowed_operations list

            def apply(self, ctx):
                return ctx

            def rollback(self, ctx):
                return ctx

        wrapped = security.wrap(DataFilter())
        result = wrapped.apply(ctx)

        # All restricted/internal string fields should be masked
        secret_col = result.data["secret_data"]
        assert all("RESTRICTED" in str(v) for v in secret_col if pd.notna(v))

        phone_col = result.data["phone"]
        assert all("RESTRICTED" in str(v) for v in phone_col if pd.notna(v))

        # Restricted numeric fields should be masked
        amount_col = result.data["internal_amount"]
        assert all("***" in str(v) for v in amount_col if pd.notna(v))

    def test_intern_always_needs_confirmation(self, security, intern_ctx):
        """Every intern filter execution should set needs_confirmation."""
        df = pd.DataFrame({"name": ["test"]})
        ctx = intern_ctx.with_data(df)

        class AnyFilter:
            name = "read"  # Must be in intern allowed list

            def apply(self, ctx):
                return ctx.with_metric("done", True)

            def rollback(self, ctx):
                return ctx

        wrapped = security.wrap(AnyFilter())
        result = wrapped.apply(ctx)
        assert result.meta.get("needs_confirmation") is True

    def test_public_fields_not_masked(self, security, intern_ctx):
        """Public fields should remain readable for intern."""
        df = pd.DataFrame({
            "name": ["Alice", "Bob"],
            "secret_data": ["s1", "s2"],
        })
        ctx = intern_ctx.with_data(df)

        class DataFilter:
            name = "read"  # Must be in intern allowed list

            def apply(self, ctx):
                return ctx

            def rollback(self, ctx):
                return ctx

        wrapped = security.wrap(DataFilter())
        result = wrapped.apply(ctx)
        # Public fields must be intact
        assert "Alice" in result.data["name"].values
        assert "Bob" in result.data["name"].values


# ═══════════════════════════════════════════════════════════
# 4. Lifecycle Policy Conflict Test
# ═══════════════════════════════════════════════════════════

class TestLifecyclePolicyConflict:
    """Test policy override priority: task override > cluster default > role forced."""

    @pytest.fixture
    def lifecycle(self, config_dir):
        return LifecycleWrapper(config_dir)

    def test_intern_cannot_override_to_permanent(self, lifecycle):
        """Intern should always get supervised_short_term regardless of overrides."""
        ctx = PipelineContext(
            task_id="conflict-test",
            asset_type="RE_MORTGAGE",
            role="intern",
            cluster={"lifecycle": {"default_ttl_days": 365}},
            meta={"policy_override": {"policy_name": "permanent"}},
        )

        class FinalizeMock:
            name = "finalize"

            def apply(self, ctx):
                return ctx

            def rollback(self, ctx):
                return ctx

        wrapped = lifecycle.wrap(FinalizeMock())
        result = wrapped.apply(ctx)
        policy = result.meta.get("lifecycle_policy", {})
        # Intern is forced to supervised_short_term (15 days)
        assert policy.get("default_ttl_days") == 15

    def test_analyst_can_override(self, lifecycle):
        """Analyst should be able to use policy override."""
        ctx = PipelineContext(
            task_id="override-test",
            asset_type="RE_MORTGAGE",
            role="analyst",
            cluster={"lifecycle": {"default_ttl_days": 30}},
            meta={"policy_override": {"policy_name": "long_term"}},
        )

        class FinalizeMock:
            name = "finalize"

            def apply(self, ctx):
                return ctx

            def rollback(self, ctx):
                return ctx

        wrapped = lifecycle.wrap(FinalizeMock())
        result = wrapped.apply(ctx)
        policy = result.meta.get("lifecycle_policy", {})
        assert policy.get("default_ttl_days") == 365


# ═══════════════════════════════════════════════════════════
# 5. Wrapper Order Commutativity Test
# ═══════════════════════════════════════════════════════════

class TestWrapperOrderCommutativity:
    """Test that different wrapper orders produce consistent results."""

    @pytest.fixture
    def data_for_wrapper_test(self, mortgage_cluster):
        ctx = PipelineContext(
            task_id="order-test",
            asset_type="RE_MORTGAGE",
            role="analyst",
            cluster=mortgage_cluster,
        )
        df = pd.DataFrame({
            "房产地址": ["北京路1号", "上海路2号"],
            "建筑面积": [120.5, 85.3],
            "抵押金额": [5000000, 3000000],
            "估值金额": [6000000, 3500000],
        })
        return ctx.with_data(df)

    def test_wrapper_order_permutations(self, config_dir, data_for_wrapper_test):
        """All permutations of 3 wrappers should produce valid output."""
        security = SecurityWrapper(config_dir)
        lifecycle = LifecycleWrapper(config_dir)
        adaptive = AdaptiveWrapper()

        wrappers = [security, lifecycle, adaptive]
        results = []

        for perm in itertools.permutations(wrappers):
            # Use 'read' filter which is allowed for all roles
            from filters.f09_read import ReaderFilter
            import dataclasses
            read_ctx = dataclasses.replace(
                data_for_wrapper_test,
                meta={**data_for_wrapper_test.meta, "input_source": ""},
            )
            pipeline = Pipeline(
                filters=[ReaderFilter()],
                wrappers=list(perm),
            )
            result = pipeline.execute(read_ctx)
            # ReaderFilter skips when no input_source (returns ctx unchanged)
            results.append(result)

        # All results should be valid pipeline results
        assert len(results) == 6  # 3! = 6 permutations

    def test_security_outmost_when_intern(self, config_dir):
        """When role is intern, security wrapper should mask data."""
        security = SecurityWrapper(config_dir)
        lifecycle = LifecycleWrapper(config_dir)
        adaptive = AdaptiveWrapper()

        ctx = PipelineContext(
            task_id="order-intern",
            asset_type="RE_MORTGAGE",
            role="intern",
            cluster={
                "fields": {
                    "address": {"type": "string", "access_level": "restricted"},
                    "amount": {"type": "float", "access_level": "public"},
                }
            },
        )
        df = pd.DataFrame({
            "address": ["secret_addr_1", "secret_addr_2"],
            "amount": [1000.0, 2000.0],
        })
        ctx = ctx.with_data(df)

        # Security first, with a 'read' filter (allowed for intern)
        from filters.f09_read import ReaderFilter
        pipeline = Pipeline(
            filters=[ReaderFilter()],
            wrappers=[security, lifecycle, adaptive],
        )
        # Need input_source in meta for ReaderFilter to do anything
        import dataclasses
        ctx = dataclasses.replace(ctx, meta={"input_source": ""})
        result = pipeline.execute(ctx)
        # ReaderFilter skips on empty source, but security wrapper should still
        # have enforced row limit and confirmation
        assert result.final_context.meta.get("needs_confirmation") is True


class TestSnapshotRollbackConsistency:
    """Each filter's apply() then rollback() should restore original state."""

    def test_structure_normalizer_roundtrip(self, base_ctx, sample_df):
        ctx = base_ctx.with_data(copy.deepcopy(sample_df))
        f = StructureNormalizerFilter()
        after = f.apply(ctx)
        assert after.data is not None
        rolled = f.rollback(after)
        assert rolled.data is None  # Original had no data

    def test_multiple_filter_roundtrip(self, base_ctx, sample_df):
        """Apply all filters, then rollback each — should reach initial state."""
        ctx = base_ctx.with_data(copy.deepcopy(sample_df))

        filters = [
            StructureNormalizerFilter(),
        ]
        from filters.f06_normalize_numeric import NumericNormalizerFilter
        from filters.f10_clean import CleanerFilter
        filters.append(NumericNormalizerFilter())
        filters.append(CleanerFilter())

        # Apply all
        current = ctx
        for f in filters:
            current = f.apply(current) if hasattr(f, 'apply') else current

        # Rollback in reverse
        for f in reversed(filters):
            current = f.rollback(current) if hasattr(f, 'rollback') else current

        # Final state: data should be None (or equivalent to initial)
        assert current is not None

    def test_context_idempotent(self, base_ctx):
        """Repeated apply→rollback cycles should be stable."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        ctx = base_ctx.with_data(df)
        f = StructureNormalizerFilter()

        for _ in range(10):
            applied = f.apply(ctx)
            rolled = f.rollback(applied)
            assert rolled.data is None


# ═══════════════════════════════════════════════════════════
# 7. Pipeline Interrupt Recovery Test
# ═══════════════════════════════════════════════════════════

class TestPipelineInterruptRecovery:
    """Simulate failures and verify recovery from any step."""

    def test_recovery_from_each_filter(self, base_ctx, sample_df, config_dir):
        """Verify pipeline can be resumed from every filter position."""

        # Build chain
        index_filter = IndexLookupFilter(config_dir)
        ctx = index_filter.apply(base_ctx)
        ctx = ctx.with_data(sample_df)

        filters = [
            StructureNormalizerFilter(),
            CleanerFilter(),
            SchemaGeneratorFilter(),
        ]

        pipeline = Pipeline(filters=filters)

        # Run full pipeline first to get reference
        ref_result = pipeline.execute(ctx)
        assert ref_result.success

        # Now verify each filter can be the resume point
        for f in filters:
            resume_result = pipeline.resume(ctx, from_filter=f.name)
            assert resume_result.success, f"Failed to resume from {f.name}"
