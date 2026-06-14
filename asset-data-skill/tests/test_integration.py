"""Integration tests: Filter chains, full Pipeline, Wrapper combinations."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from filters.context import PipelineContext
from filters.pipeline import Pipeline, PipelineConfig, PipelineResult
from filters.f01_index import IndexLookupFilter
from filters.f05_normalize_structure import StructureNormalizerFilter
from filters.f06_normalize_numeric import NumericNormalizerFilter
from filters.f07_generate_schema import SchemaGeneratorFilter
from filters.f08_generate_summary import SummaryGeneratorFilter
from filters.f10_clean import CleanerFilter
from filters.f11_validate import ValidatorFilter
from filters.f12_transform import TransformerFilter
from filters.f13_analyze import AnalyzerFilter
from wrappers.security_wrapper import SecurityWrapper
from wrappers.lifecycle_wrapper import LifecycleWrapper
from wrappers.adaptive_wrapper import AdaptiveWrapper


class TestFilterChainIntegration:
    """Test real filter chains that are used in production."""

    @pytest.fixture
    def cleanup_request_chain(self, config_dir):
        """Filters for the clean_and_validate route."""
        return [
            StructureNormalizerFilter(),
            NumericNormalizerFilter(),
            ValidatorFilter(),
            CleanerFilter(),
            TransformerFilter(),
            SchemaGeneratorFilter(),
            SummaryGeneratorFilter(),
        ]

    @pytest.fixture
    def analytics_chain(self, config_dir):
        """Filters for analysis-heavy pipeline."""
        return [
            StructureNormalizerFilter(),
            CleanerFilter(),
            TransformerFilter(),
            AnalyzerFilter(),
            SchemaGeneratorFilter(),
            SummaryGeneratorFilter(),
        ]

    @pytest.fixture
    def sample_data(self):
        return pd.DataFrame({
            "房产地址": ["北京朝阳路1号", "上海浦东路2号", "广州天河路3号"],
            "建筑面积": ["120.5", "85.3", "200.0"],
            "抵押金额": ["500万元", "300万元", "800万元"],
            "估值金额": [6000000, 3500000, 10000000],
            "登记日期": ["2023-01-15", "2023/06/20", "2023年12月01日"],
            "用途": ["商业", "住宅", "商业"],
        })

    def test_clean_validate_full_chain(self, config_dir, cleanup_request_chain, base_ctx, sample_data):
        """Execute the clean_and_validate filter chain with real data."""
        # Load cluster first
        index_filter = IndexLookupFilter(config_dir)
        ctx = index_filter.apply(base_ctx)
        ctx = ctx.with_data(sample_data)

        wrapper = SecurityWrapper(config_dir)

        pipeline = Pipeline(
            filters=cleanup_request_chain,
            wrappers=[wrapper],
            config=PipelineConfig(verbose=True),
        )
        result = pipeline.execute(ctx)
        assert result.success, f"Pipeline failed: {result.error} at {result.failed_at}"
        assert len(result.executed_filters) == 7

        # Verify final state
        final = result.final_context
        assert final.data is not None
        assert final.summary is not None
        assert "# 数据概览报告" in (final.summary or "")

    def test_analytics_chain(self, config_dir, analytics_chain, base_ctx, sample_data):
        """Execute analytics pipeline with analysis output."""
        index_filter = IndexLookupFilter(config_dir)
        ctx = index_filter.apply(base_ctx)
        ctx = ctx.with_data(sample_data)

        pipeline = Pipeline(filters=analytics_chain)
        result = pipeline.execute(ctx)
        assert result.success
        final = result.final_context
        assert "analysis_result" in final.meta
        assert "descriptive" in final.meta["analysis_result"]

    def test_error_recovery_from_midpoint(self, config_dir, cleanup_request_chain, base_ctx, sample_data):
        """Verify that a pipeline that fails mid-way can be resumed."""
        index_filter = IndexLookupFilter(config_dir)
        ctx = index_filter.apply(base_ctx)
        ctx = ctx.with_data(sample_data)

        # Execute first 3 filters manually
        ctx = cleanup_request_chain[0].apply(ctx)  # normalize_structure
        ctx = cleanup_request_chain[1].apply(ctx)  # normalize_numeric

        # Now resume from validate
        pipeline = Pipeline(filters=cleanup_request_chain[2:])  # Start from validate
        result = pipeline.execute(ctx)
        assert result.success
        assert "validate" in result.executed_filters
        assert result.final_context.summary is not None

    def test_filter_order_data_flow(self, config_dir, base_ctx, sample_data):
        """Verify data flows correctly through the filter chain."""
        index_filter = IndexLookupFilter(config_dir)
        ctx = index_filter.apply(base_ctx)
        ctx = ctx.with_data(sample_data)

        # Structure normalizer: alias matching + date normalization
        ctx = StructureNormalizerFilter().apply(ctx)
        assert "property_address" in ctx.data.columns
        assert "building_area_sqm" in ctx.data.columns

        # Cleaner: fix common errors
        ctx = CleanerFilter().apply(ctx)
        assert ctx.metrics.get("fixes_applied", 0) >= 0

        # Schema generator
        ctx = SchemaGeneratorFilter().apply(ctx)
        assert ctx.schema is not None

        # Summary generator
        ctx = SummaryGeneratorFilter().apply(ctx)
        assert ctx.summary is not None


class TestPipelineResumeScenarios:
    """Test pipeline interruption and resume behavior."""

    def test_resume_from_any_filter(self, base_ctx):
        """Resume should work from any filter name in the chain."""

        class CountingFilter:
            def __init__(self, name):
                self._name = name
                self.count = 0

            @property
            def name(self):
                return self._name

            def apply(self, ctx):
                self.count += 1
                return ctx.with_metric(self._name, True)

            def rollback(self, ctx):
                return ctx

        f1 = CountingFilter("step1")
        f2 = CountingFilter("step2")
        f3 = CountingFilter("step3")
        pipeline = Pipeline(filters=[f1, f2, f3])

        result = pipeline.resume(base_ctx, from_filter="step2")
        assert result.success
        assert f1.count == 0  # step1 was skipped
        assert f2.count == 1
        assert f3.count == 1
        assert "step2" in result.executed_filters
        assert "step1" not in result.executed_filters

    def test_pipeline_stop_on_error_mid_chain(self, base_ctx):
        """When a filter fails, stop and preserve context."""

        class FailFilter:
            name = "failer"

            def apply(self, ctx):
                raise ValueError("Intentional failure")

            def rollback(self, ctx):
                return ctx

        f1 = type("F1", (), {"name": "ok1", "apply": lambda s, c: c.with_metric("ok1", True), "rollback": lambda s, c: c})()
        f2 = FailFilter()
        f3 = type("F3", (), {"name": "ok2", "apply": lambda s, c: c.with_metric("ok2", True), "rollback": lambda s, c: c})()

        pipeline = Pipeline(filters=[f1, f2, f3], config=PipelineConfig(stop_on_error=True))
        result = pipeline.execute(base_ctx)
        assert not result.success
        assert result.failed_at == "failer"
        assert result.executed_filters == ["ok1"]
        assert "ok2" not in result.final_context.metrics


class TestWrapperCombinations:
    """Test all 3 wrappers composed together."""

    def test_all_three_wrappers(self, config_dir, base_ctx, sample_df):
        """Security + Lifecycle + Adaptive all applied together."""

        # Create config directory with all required files
        security = SecurityWrapper(config_dir)
        lifecycle = LifecycleWrapper(config_dir)
        adaptive = AdaptiveWrapper()

        # Build cluster first
        index_filter = IndexLookupFilter(config_dir)
        ctx = index_filter.apply(base_ctx)
        ctx = ctx.with_data(sample_df)

        filters = [
            StructureNormalizerFilter(),
            CleanerFilter(),
            SchemaGeneratorFilter(),
        ]

        pipeline = Pipeline(
            filters=filters,
            wrappers=[security, lifecycle, adaptive],
        )
        result = pipeline.execute(ctx)
        # Should complete without errors
        assert result.success

    def test_wrapper_order_security_first(self, config_dir, base_ctx, sample_df):
        """Security wrapper applied first (outmost)."""
        security = SecurityWrapper(config_dir)
        lifecycle = LifecycleWrapper(config_dir)
        adaptive = AdaptiveWrapper()

        index_filter = IndexLookupFilter(config_dir)
        ctx = index_filter.apply(base_ctx)
        ctx = ctx.with_data(sample_df)

        # Order: security → lifecycle → adaptive → filter
        pipeline = Pipeline(
            filters=[StructureNormalizerFilter()],
            wrappers=[security, lifecycle, adaptive],
        )
        result = pipeline.execute(ctx)
        assert result.success

    def test_intern_with_lifecycle_override(self, config_dir, mortgage_cluster):
        """Intern role: security limits + lifecycle override."""
        security = SecurityWrapper(config_dir)
        lifecycle = LifecycleWrapper(config_dir)

        ctx = PipelineContext(
            task_id="intern-lifecycle-test",
            asset_type="RE_MORTGAGE",
            role="intern",
            cluster=mortgage_cluster,
        )
        df = pd.DataFrame({
            "房产地址": ["北京路1号", "上海路2号"],
            "建筑面积": [120.5, 85.3],
            "抵押金额": [5000000, 3000000],
        })
        ctx = ctx.with_data(df)

        # Only test with filters allowed for intern
        import dataclasses
        filters = [
            StructureNormalizerFilter(),
        ]
        pipeline = Pipeline(filters=filters, wrappers=[security, lifecycle])
        result = pipeline.execute(ctx)
        assert result.success
        # Lifecycle wrapper attaches policy on finalize; structure filter confirms intern restrictions
        assert result.final_context.meta.get("needs_confirmation") is True
