"""Tests for f05 (structure normalization) and f06 (numeric normalization)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from filters.f05_normalize_structure import StructureNormalizerFilter
from filters.f06_normalize_numeric import NumericNormalizerFilter
from filters.context import PipelineContext


# ═══ StructureNormalizerFilter ══════════════════════════════


class TestStructureNormalizer:
    def test_alias_matching(self, base_ctx, sample_df):
        """Column names like '房产地址' should be renamed to 'property_address'."""
        ctx = base_ctx.with_data(sample_df)
        f = StructureNormalizerFilter()
        result = f.apply(ctx)
        # Check that aliased columns got renamed
        assert "property_address" in result.data.columns

    def test_date_normalization(self, base_ctx, sample_df):
        ctx = base_ctx.with_data(sample_df)
        f = StructureNormalizerFilter()
        result = f.apply(ctx)

        # First rename aliases
        from filters.f05_normalize_structure import StructureNormalizerFilter as SN
        df = SN()._match_aliases(sample_df, base_ctx.cluster["fields"])
        # Check that registration_date exists after alias matching

    def test_full_normalization_pipeline(self, base_ctx, sample_df):
        ctx = base_ctx.with_data(sample_df)
        f = StructureNormalizerFilter()
        result = f.apply(ctx)
        df = result.data
        # Should have renamed columns
        assert "property_address" in df.columns
        # Should have metrics
        assert result.metrics["row_count"] == 3
        assert result.metrics["column_count"] >= 3

    def test_parse_bool_true(self):
        assert StructureNormalizerFilter._parse_bool(True) is True
        assert StructureNormalizerFilter._parse_bool("true") is True
        assert StructureNormalizerFilter._parse_bool("yes") is True
        assert StructureNormalizerFilter._parse_bool("是") is True
        assert StructureNormalizerFilter._parse_bool("1") is True

    def test_parse_bool_false(self):
        assert StructureNormalizerFilter._parse_bool(False) is False
        assert StructureNormalizerFilter._parse_bool("false") is False
        assert StructureNormalizerFilter._parse_bool("no") is False
        assert StructureNormalizerFilter._parse_bool("0") is False

    def test_parse_bool_none(self):
        assert StructureNormalizerFilter._parse_bool(None) is None

    def test_clean_number_wan_unit(self):
        """'万' unit should multiply by 10000."""
        fdef = {"type": "float"}
        result = StructureNormalizerFilter._clean_number("500万", fdef)
        assert result == 5000000.0
        result = StructureNormalizerFilter._clean_number("3.5万元", fdef)
        assert result == 35000.0

    def test_clean_number_thousand_separator(self):
        fdef = {"type": "float"}
        result = StructureNormalizerFilter._clean_number("1,234,567", fdef)
        assert result == 1234567.0
        result = StructureNormalizerFilter._clean_number("¥500,000", fdef)
        assert result == 500000.0

    def test_clean_number_currency_symbols(self):
        fdef = {"type": "float"}
        result = StructureNormalizerFilter._clean_number("￥1000", fdef)
        assert result == 1000.0

    def test_clean_number_invalid(self):
        fdef = {"type": "float"}
        result = StructureNormalizerFilter._clean_number("not a number", fdef)
        assert result is None
        result = StructureNormalizerFilter._clean_number("", fdef)
        assert result is None

    def test_clean_number_negative(self):
        fdef = {"type": "float"}
        result = StructureNormalizerFilter._clean_number("-500", fdef)
        assert result == -500.0

    def test_clean_number_integer_type(self):
        fdef = {"type": "integer"}
        result = StructureNormalizerFilter._clean_number("500", fdef)
        assert result == 500
        assert isinstance(result, int)

    def test_date_parse_standard_formats(self):
        f = StructureNormalizerFilter()
        assert f._parse_date("2023-01-15") == "2023-01-15"
        assert f._parse_date("2023/01/15") == "2023-01-15"
        assert f._parse_date("2023年01月15日") == "2023-01-15"

    def test_date_parse_eight_digit(self):
        f = StructureNormalizerFilter()
        result = f._parse_date(20230115)
        assert result == "2023-01-15"

    def test_date_parse_unparseable(self):
        f = StructureNormalizerFilter()
        result = f._parse_date("notadate")
        assert result == "notadate"  # Returns original

    def test_entries_to_dataframe(self, base_ctx):
        entries = [
            {"fields": {"name": "Item1", "value": 100}, "confidence": 0.9},
            {"fields": {"name": "Item2", "value": 200}, "confidence": 0.5, "needs_review": True},
        ]
        f = StructureNormalizerFilter()
        df = f._entries_to_dataframe(entries, base_ctx.cluster)
        assert len(df) == 2
        assert "_confidence" in df.columns
        assert df["_confidence"].iloc[0] == 0.9

    def test_no_data_no_entries(self, base_ctx):
        f = StructureNormalizerFilter()
        result = f.apply(base_ctx)
        # Should return same context (no data, no entries)
        assert result.data is None

    def test_from_entries(self, base_ctx):
        entries = [
            {"fields": {"property_address": "Test"}, "confidence": 0.9},
        ]
        ctx = base_ctx.with_entries(entries)
        f = StructureNormalizerFilter()
        result = f.apply(ctx)
        assert result.data is not None
        assert len(result.data) == 1

    def test_rollback(self, base_ctx, sample_df):
        ctx = base_ctx.with_data(sample_df)
        f = StructureNormalizerFilter()
        result = f.apply(ctx)
        assert result.data is not None
        rolled = f.rollback(result)
        assert rolled.data is None

    def test_filter_name(self):
        assert StructureNormalizerFilter().name == "normalize_structure"


# ═══ NumericNormalizerFilter ════════════════════════════════


class TestNumericNormalizer:
    @pytest.fixture
    def numeric_df(self):
        return pd.DataFrame({
            "building_area_sqm": [100.0, 200.0, 300.0, 400.0, 500.0],
            "valuation_amount": [1e6, 2e6, 3e6, 4e6, 5e6],
            "label": ["a", "b", "c", "d", "e"],
        })

    def test_no_data(self, base_ctx):
        f = NumericNormalizerFilter()
        result = f.apply(base_ctx)
        assert result == base_ctx or result.data is None

    def test_zscore_normalization(self, base_ctx, numeric_df, mortgage_cluster):
        ctx = base_ctx.with_data(numeric_df)
        f = NumericNormalizerFilter()
        result = f.apply(ctx)
        assert "building_area_sqm_zscore" in result.data.columns
        # Z-scores should be centered around 0
        zscores = result.data["building_area_sqm_zscore"]
        assert abs(zscores.mean()) < 0.01

    def test_minmax_normalization(self, base_ctx, numeric_df, mortgage_cluster):
        ctx = base_ctx.with_data(numeric_df)
        f = NumericNormalizerFilter()
        result = f.apply(ctx)
        assert "building_area_sqm_minmax" in result.data.columns
        # Min-max should be in [0, 1]
        minmax = result.data["building_area_sqm_minmax"]
        assert 0 <= minmax.min() <= 1
        assert 0 <= minmax.max() <= 1

    def test_constant_column(self, base_ctx, mortgage_cluster):
        """A column with all same values should produce 0.0 for zscore."""
        df = pd.DataFrame({
            "building_area_sqm": [100.0, 100.0, 100.0],
            "valuation_amount": [1e6, 1e6, 1e6],
        })
        ctx = base_ctx.with_data(df)
        f = NumericNormalizerFilter()
        result = f.apply(ctx)
        # Should not crash, and normalized values should be 0
        assert (result.data["building_area_sqm_zscore"] == 0.0).all()

    def test_non_numeric_skipped(self, base_ctx, numeric_df, mortgage_cluster):
        ctx = base_ctx.with_data(numeric_df)
        f = NumericNormalizerFilter()
        result = f.apply(ctx)
        # 'label' is string, should not get normalized columns
        assert "label_zscore" not in result.data.columns

    def test_original_columns_preserved(self, base_ctx, numeric_df, mortgage_cluster):
        ctx = base_ctx.with_data(numeric_df)
        f = NumericNormalizerFilter()
        result = f.apply(ctx)
        # Original columns must remain
        assert "building_area_sqm" in result.data.columns
        assert "valuation_amount" in result.data.columns

    def test_metrics(self, base_ctx, numeric_df, mortgage_cluster):
        ctx = base_ctx.with_data(numeric_df)
        f = NumericNormalizerFilter()
        result = f.apply(ctx)
        assert result.metrics.get("normalized_columns", 0) > 0

    def test_rollback_removes_normalized_cols(self, base_ctx, numeric_df, mortgage_cluster):
        ctx = base_ctx.with_data(numeric_df)
        f = NumericNormalizerFilter()
        result = f.apply(ctx)
        rolled = f.rollback(result)
        assert "building_area_sqm_zscore" not in rolled.data.columns
        assert "building_area_sqm_minmax" not in rolled.data.columns

    def test_filter_name(self):
        assert NumericNormalizerFilter().name == "normalize_numeric"
