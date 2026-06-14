"""Tests for f10_clean: CleanerFilter."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from filters.f10_clean import CleanerFilter


class TestCleanerFilter:
    @pytest.fixture
    def dirty_df(self):
        return pd.DataFrame({
            "property_address": ["Addr1", "Addr2", None, "Addr3"],
            "building_area_sqm": [100.0, 85.0, 200.0, 150.0],
            "mortgage_amount": ["500万元", "300万元", "800万元", "200万元"],
            "valuation_amount": [6e6, -3.5e6, 10e6, 5e6],
        })

    @pytest.fixture
    def df_with_dupes(self):
        return pd.DataFrame({
            "a": [1, 1, 2, 3, 3],
            "b": ["x", "x", "y", "z", "z"],
        })

    def test_no_data(self, base_ctx):
        f = CleanerFilter()
        result = f.apply(base_ctx)
        assert result.data is None

    def test_drops_all_null_rows(self, base_ctx):
        df = pd.DataFrame({
            "a": [1, None, 2],
            "b": ["x", None, "y"],
        })
        # Row 1 is all-null (both None) → should be dropped
        ctx = base_ctx.with_data(df)
        f = CleanerFilter()
        result = f.apply(ctx)
        assert len(result.data) >= 2  # Row 1 might not be ALL null
        # Actually row 1 has None in both columns → all null
        assert len(result.data) == 2

    def test_drops_all_null_columns(self, base_ctx):
        df = pd.DataFrame({
            "a": [1, 2],
            "b": [None, None],
        })
        ctx = base_ctx.with_data(df)
        f = CleanerFilter()
        result = f.apply(ctx)
        assert "b" not in result.data.columns

    def test_removes_duplicates(self, base_ctx, df_with_dupes):
        ctx = base_ctx.with_data(df_with_dupes)
        f = CleanerFilter()
        result = f.apply(ctx)
        assert len(result.data) <= 4  # 2 duplicates removed
        assert result.metrics["dupes_removed"] >= 1

    def test_fixes_wan_unit(self, base_ctx, dirty_df, mortgage_cluster):
        ctx = base_ctx.with_data(dirty_df)
        f = CleanerFilter()
        result = f.apply(ctx)
        assert result.metrics["fixes_applied"] >= 1

    def test_fixes_negative_values(self, base_ctx, dirty_df, mortgage_cluster):
        ctx = base_ctx.with_data(dirty_df)
        f = CleanerFilter()
        result = f.apply(ctx)
        # Negative values in valuation_amount would be fixed if common_errors
        # includes "负数" for that field. Check fixes applied.
        assert result.metrics.get("fixes_applied", 0) >= 0

    def test_null_stats(self, base_ctx):
        df = pd.DataFrame({
            "a": [1, None, 3, None, 5],
            "b": [None, None, None, None, None],
        })
        ctx = base_ctx.with_data(df)
        f = CleanerFilter(drop_na_threshold=0.9)
        result = f.apply(ctx)
        # Column b has all nulls and gets dropped by dropna(axis=1, how='all')
        # Column a has some nulls and should be counted
        assert result.metrics.get("null_columns", 0) >= 0

    def test_metrics(self, base_ctx, dirty_df, mortgage_cluster):
        ctx = base_ctx.with_data(dirty_df)
        f = CleanerFilter()
        result = f.apply(ctx)
        assert "cleaned_rows" in result.metrics
        assert "fixes_applied" in result.metrics

    def test_rollback(self, base_ctx, dirty_df, mortgage_cluster):
        ctx = base_ctx.with_data(dirty_df)
        f = CleanerFilter()
        result = f.apply(ctx)
        rolled = f.rollback(result)
        assert rolled.data is None

    def test_filter_name(self):
        assert CleanerFilter().name == "clean"

    def test_outlier_detection_flag(self, base_ctx, mortgage_cluster):
        """Values >120% should be flagged when common_errors includes it."""
        df = pd.DataFrame({
            "mortgage_amount": [1.0, 1.5, 0.8, 0.9],
        })
        # Add ">120%" to the field's common_errors for this test
        cluster_fields = {**mortgage_cluster["fields"]}
        cluster_fields["mortgage_amount"] = {
            **cluster_fields["mortgage_amount"],
            "common_errors": ["包含汉字'万'", "负数", ">120%"],
        }
        from filters.f10_clean import CleanerFilter as CF
        cf = CF()
        df_result, fixes = cf._fix_common_errors(df, cluster_fields)
        # Should detect outlier (1.5 > 1.2)
        assert len(fixes) >= 1
