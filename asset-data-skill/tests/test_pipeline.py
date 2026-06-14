"""Tests for Pipeline, PipelineFactory, Filter Protocol, and Goal."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from filters.pipeline import (
    Filter,
    Goal,
    Pipeline,
    PipelineConfig,
    PipelineFactory,
    PipelineResult,
    Wrapper,
)
from filters.context import PipelineContext


# ─── Mock Filters ─────────────────────────────────────────


class MockFilter:
    """A simple filter that records its invocation."""

    name = "mock"

    def __init__(self, name="mock", should_fail=False, transform=None):
        self._name = name
        self.should_fail = should_fail
        self.transform = transform
        self._apply_count = 0

    @property
    def name(self):
        return self._name

    def apply(self, ctx: PipelineContext) -> PipelineContext:
        self._apply_count += 1
        if self.should_fail:
            raise RuntimeError(f"Filter {self._name} failed")
        if self.transform:
            return self.transform(ctx)
        return ctx.with_metric(f"applied_{self._name}", True)

    def rollback(self, ctx: PipelineContext) -> PipelineContext:
        return ctx


class MockWrapper:
    """A simple wrapper that prepends/appends to filter execution."""

    def __init__(self, prefix: str = "W"):
        self.prefix = prefix

    def wrap(self, filter_: Filter) -> Filter:
        original_apply = filter_.apply
        wrapper = self

        class WrappedFilter:
            name = filter_.name

            def apply(self, ctx: PipelineContext) -> PipelineContext:
                ctx = ctx.with_metric(f"{wrapper.prefix}_before", True)
                result = original_apply(ctx)
                result = result.with_metric(f"{wrapper.prefix}_after", True)
                return result

            def rollback(self, ctx: PipelineContext) -> PipelineContext:
                return filter_.rollback(ctx)

        return WrappedFilter()


# ─── Filter Protocol Tests ──────────────────────────────────


class TestFilterProtocol:
    def test_filter_protocol_is_runtime_checkable(self):
        assert hasattr(Filter, "_is_runtime_protocol")

    def test_mock_filter_matches_protocol(self):
        assert isinstance(MockFilter(), Filter)

    def test_wrapper_protocol_is_checkable(self):
        assert hasattr(Wrapper, "_is_runtime_protocol")


# ─── Pipeline Tests ────────────────────────────────────────


class TestPipeline:
    def test_empty_pipeline(self, base_ctx):
        pipeline = Pipeline(filters=[])
        result = pipeline.execute(base_ctx)
        assert result.success
        assert result.executed_filters == []

    def test_single_filter(self, base_ctx):
        f = MockFilter(name="step1")
        pipeline = Pipeline(filters=[f])
        result = pipeline.execute(base_ctx)
        assert result.success
        assert result.executed_filters == ["step1"]
        assert result.final_context.metrics["applied_step1"] is True

    def test_multiple_filters(self, base_ctx):
        f1 = MockFilter(name="a")
        f2 = MockFilter(name="b")
        f3 = MockFilter(name="c")
        pipeline = Pipeline(filters=[f1, f2, f3])
        result = pipeline.execute(base_ctx)
        assert result.success
        assert result.executed_filters == ["a", "b", "c"]

    def test_stop_on_error(self, base_ctx):
        f1 = MockFilter(name="ok")
        f2 = MockFilter(name="fail", should_fail=True)
        f3 = MockFilter(name="never_reached")
        pipeline = Pipeline(filters=[f1, f2, f3], config=PipelineConfig(stop_on_error=True))
        result = pipeline.execute(base_ctx)
        assert not result.success
        assert result.failed_at == "fail"
        assert result.executed_filters == ["ok"]
        assert "never_reached" not in result.executed_filters

    def test_verbose_mode(self, base_ctx):
        pipeline = Pipeline(
            filters=[MockFilter(name="v")],
            config=PipelineConfig(verbose=True),
        )
        result = pipeline.execute(base_ctx)
        assert result.success

    def test_with_wrapper(self, base_ctx):
        f = MockFilter(name="wrapped")
        wrapper = MockWrapper(prefix="SEC")
        pipeline = Pipeline(filters=[f], wrappers=[wrapper])
        result = pipeline.execute(base_ctx)
        assert result.success
        assert result.final_context.metrics["SEC_before"] is True
        assert result.final_context.metrics["applied_wrapped"] is True
        assert result.final_context.metrics["SEC_after"] is True

    def test_resume_from_filter(self, base_ctx):
        f1 = MockFilter(name="step1")
        f2 = MockFilter(name="step2")
        f3 = MockFilter(name="step3")
        pipeline = Pipeline(filters=[f1, f2, f3])

        # Resume from step2 (should skip step1)
        result = pipeline.resume(base_ctx, from_filter="step2")
        assert result.success
        assert result.executed_filters == ["step2", "step3"]

    def test_resume_unknown_filter(self, base_ctx):
        pipeline = Pipeline(filters=[MockFilter(name="a")])
        result = pipeline.resume(base_ctx, from_filter="unknown")
        assert not result.success
        assert "not found" in result.error.lower()


# ─── PipelineResult Tests ──────────────────────────────────


class TestPipelineResult:
    def test_success_result(self, base_ctx):
        result = PipelineResult(
            success=True,
            final_context=base_ctx,
            executed_filters=["a", "b"],
        )
        assert result.success
        assert result.error is None
        assert result.failed_at is None

    def test_failure_result(self, base_ctx):
        result = PipelineResult(
            success=False,
            final_context=base_ctx,
            executed_filters=["a"],
            failed_at="b",
            error="Something went wrong",
        )
        assert not result.success
        assert result.failed_at == "b"
        assert result.error == "Something went wrong"


# ─── Goal Dataclass Tests ──────────────────────────────────


class TestGoal:
    def test_minimal_goal(self):
        g = Goal(asset_type="AT", operation="op", input_source="file.csv")
        assert g.asset_type == "AT"
        assert g.operation == "op"
        assert g.input_source == "file.csv"
        assert g.role == "analyst"
        assert g.params is None
        assert g.policy_override is None

    def test_goal_with_params(self):
        g = Goal(
            asset_type="AT",
            operation="full_pipeline",
            input_source="data.xlsx",
            role="intern",
            params={"interactive": True},
            policy_override={"policy_name": "long_term"},
        )
        assert g.params["interactive"] is True
        assert g.policy_override["policy_name"] == "long_term"


# ─── PipelineFactory Tests ─────────────────────────────────


class TestPipelineFactory:
    @pytest.fixture
    def routing_config(self) -> Path:
        """Create a temporary goal_routing.json."""
        config = {
            "goal_routing": {
                "test_op": [
                    {"step": "read"},
                    {"step": "clean"},
                    {"step": "analyze"},
                ],
                "empty_op": [],
            }
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(config, f)
            return Path(f.name)

    def test_create_pipeline(self, routing_config, base_ctx):
        factory = PipelineFactory(routing_config)
        goal = Goal(asset_type="RE_MORTGAGE", operation="test_op", input_source="data.csv")

        registry = {
            "read": MockFilter(name="read"),
            "clean": MockFilter(name="clean"),
            "analyze": MockFilter(name="analyze"),
        }

        pipeline = factory.create(goal, base_ctx.cluster, registry)
        assert isinstance(pipeline, Pipeline)
        assert len(pipeline._raw_filters) == 3

    def test_create_with_wrappers(self, routing_config, base_ctx):
        factory = PipelineFactory(routing_config)
        goal = Goal(asset_type="RE_MORTGAGE", operation="test_op", input_source="data.csv")
        registry = {
            "read": MockFilter(name="read"),
            "clean": MockFilter(name="clean"),
            "analyze": MockFilter(name="analyze"),
        }
        wrapper = MockWrapper(prefix="SEC")
        pipeline = factory.create(goal, base_ctx.cluster, registry, wrappers=[wrapper])
        result = pipeline.execute(base_ctx)
        assert result.success
        # Verify wrapper was applied
        assert "SEC_after" in result.final_context.metrics

    def test_create_unknown_operation(self, routing_config, base_ctx):
        factory = PipelineFactory(routing_config)
        goal = Goal(asset_type="X", operation="nonexistent", input_source="x.csv")
        with pytest.raises(ValueError, match="No route defined"):
            factory.create(goal, base_ctx.cluster, {})

    def test_create_skips_missing_filter(self, routing_config, base_ctx):
        factory = PipelineFactory(routing_config)
        goal = Goal(asset_type="X", operation="test_op", input_source="x.csv")
        # Only provide 1 of 3 filters
        registry = {"read": MockFilter(name="read")}
        pipeline = factory.create(goal, base_ctx.cluster, registry)
        # Should only have 1 filter (the others were skipped with warning)
        assert len(pipeline._raw_filters) == 1
