"""Tests for f13_analyze: AnalyzerFilter."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from filters.f13_analyze import AnalyzerFilter


class TestAnalyzerFilter:
    @pytest.fixture
    def numeric_data(self):
        np.random.seed(42)
        return pd.DataFrame({
            "a": np.random.normal(100, 15, 100),
            "b": np.random.normal(200, 30, 100),
            "c": ["x"] * 100,  # Non-numeric
        })

    def test_no_data(self, base_ctx):
        f = AnalyzerFilter()
        result = f.apply(base_ctx)
        assert result.data is None

    def test_no_numeric_columns(self, base_ctx):
        df = pd.DataFrame({"text": ["a", "b", "c"], "more_text": ["x", "y", "z"]})
        ctx = base_ctx.with_data(df)
        f = AnalyzerFilter()
        result = f.apply(ctx)
        # Should skip without error
        assert result is not None

    def test_descriptive_statistics(self, base_ctx, numeric_data):
        ctx = base_ctx.with_data(numeric_data)
        f = AnalyzerFilter()
        result = f.apply(ctx)
        analysis = result.meta["analysis_result"]
        assert "descriptive" in analysis
        assert "a" in analysis["descriptive"]
        assert "mean" in analysis["descriptive"]["a"]
        assert "std" in analysis["descriptive"]["a"]

    def test_outlier_detection(self, base_ctx):
        """IQR outlier detection."""
        df = pd.DataFrame({
            "a": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100, 200],  # 100, 200 are outliers
        })
        ctx = base_ctx.with_data(df)
        f = AnalyzerFilter()
        result = f.apply(ctx)
        analysis = result.meta["analysis_result"]
        assert "outliers" in analysis

    def test_correlation_matrix(self, base_ctx, numeric_data):
        ctx = base_ctx.with_data(numeric_data)
        f = AnalyzerFilter()
        result = f.apply(ctx)
        analysis = result.meta["analysis_result"]
        assert "correlation" in analysis

    def test_strong_correlations(self, base_ctx):
        """Create correlated data to detect strong pairs."""
        np.random.seed(0)
        x = np.random.normal(0, 1, 100)
        df = pd.DataFrame({
            "a": x,
            "b": x * 0.9 + np.random.normal(0, 0.1, 100),  # Strong correlation
            "c": np.random.normal(0, 1, 100),  # Independent
        })
        ctx = base_ctx.with_data(df)
        f = AnalyzerFilter()
        result = f.apply(ctx)
        analysis = result.meta["analysis_result"]
        strong = analysis["correlation"].get("strong_pairs", [])
        # a and b should be strongly correlated (r > 0.7)
        assert len(strong) >= 1

    def test_metrics(self, base_ctx, numeric_data):
        ctx = base_ctx.with_data(numeric_data)
        f = AnalyzerFilter()
        result = f.apply(ctx)
        assert "outlier_columns" in result.metrics
        assert "strong_correlations" in result.metrics

    def test_small_data_handled(self, base_ctx):
        """Very small datasets should not crash."""
        df = pd.DataFrame({"a": [1.0, 2.0]})
        ctx = base_ctx.with_data(df)
        f = AnalyzerFilter()
        result = f.apply(ctx)
        # Should complete without errors
        assert result is not None

    def test_rollback(self, base_ctx, numeric_data):
        ctx = base_ctx.with_data(numeric_data)
        f = AnalyzerFilter()
        result = f.apply(ctx)
        rolled = f.rollback(result)
        assert "analysis_result" not in rolled.meta

    def test_filter_name(self):
        assert AnalyzerFilter().name == "analyze"
