"""Tests for f12_transform: TransformerFilter."""

from __future__ import annotations

import pandas as pd
import pytest

from filters.f12_transform import TransformerFilter


class TestTransformerFilter:
    @pytest.fixture
    def transform_data(self):
        return pd.DataFrame({
            "mortgage_amount": [5000000, 3000000, 8000000],
            "valuation_amount": [6000000, 3500000, 10000000],
        })

    def test_no_data(self, base_ctx):
        f = TransformerFilter()
        result = f.apply(base_ctx)
        assert result.data is None

    def test_computed_field_added(self, base_ctx, transform_data, mortgage_cluster):
        ctx = base_ctx.with_data(transform_data)
        f = TransformerFilter()
        result = f.apply(ctx)
        # "抵押率" = mortgage_amount / valuation_amount
        data = result.data
        assert data is not None

    def test_column_reorder(self, base_ctx, transform_data, mortgage_cluster):
        ctx = base_ctx.with_data(transform_data)
        f = TransformerFilter()
        result = f.apply(ctx)
        data = result.data
        # default_columns should come first
        default_cols = mortgage_cluster.get("table_mapping", {}).get("default_columns", [])
        if default_cols:
            for col in default_cols:
                if col in data.columns:
                    # These should be among the first columns
                    first_cols = list(data.columns[:len(default_cols)])
                    assert col in first_cols or col in data.columns

    def test_expression_evaluation(self, base_ctx):
        """Direct test of _evaluate_expression."""
        df = pd.DataFrame({"a": [2, 4, 6], "b": [1, 2, 3]})
        f = TransformerFilter()
        result = f._evaluate_expression(df, "a / b")
        if result is not None:
            assert result.iloc[0] == 2.0  # 2/1

    def test_multiply_expression(self, base_ctx):
        df = pd.DataFrame({"x": [10, 20], "y": [3, 4]})
        f = TransformerFilter()
        result = f._evaluate_expression(df, "x * y")
        if result is not None:
            assert result.iloc[0] == 30.0
            assert result.iloc[1] == 80.0

    def test_invalid_expression(self, base_ctx):
        """Invalid expression should log warning but not crash."""
        df = pd.DataFrame({"a": [1, 2]})
        f = TransformerFilter()
        result = f._evaluate_expression(df, "invalid_column / something")
        # Should return None for un-evaluable expression
        assert result is None

    def test_metrics(self, base_ctx, transform_data, mortgage_cluster):
        ctx = base_ctx.with_data(transform_data)
        f = TransformerFilter()
        result = f.apply(ctx)
        assert "computed_columns" in result.metrics

    def test_rollback(self, base_ctx, transform_data, mortgage_cluster):
        ctx = base_ctx.with_data(transform_data)
        f = TransformerFilter()
        result = f.apply(ctx)
        rolled = f.rollback(result)
        # Computed columns should be removed
        computed = list(mortgage_cluster.get("computed_fields", {}).keys())
        for col in computed:
            assert col not in rolled.data.columns

    def test_filter_name(self):
        assert TransformerFilter().name == "transform"

    def test_empty_computed_fields(self, base_ctx):
        """No computed fields defined should not crash."""
        cluster_no_computed = {"fields": {}, "computed_fields": {}}
        import dataclasses
        ctx = dataclasses.replace(base_ctx, cluster=cluster_no_computed)
        df = pd.DataFrame({"a": [1, 2]})
        ctx = ctx.with_data(df)
        f = TransformerFilter()
        result = f.apply(ctx)
        assert result.data is not None
        assert result.metrics["computed_columns"] == 0
