"""Tests for f15_adapt_format: FormatAdapterFilter."""

from __future__ import annotations

import pandas as pd
import pytest

from filters.f15_adapt_format import FormatAdapterFilter


class TestFormatAdapterFilter:
    @pytest.fixture
    def data_for_adapt(self):
        return pd.DataFrame({
            "property_address": ["北京路1号", "上海路2号"],
            "building_area_sqm": [120.5, 85.3],
            "valuation_amount": [6000000, 3500000],
        })

    def test_no_data(self, base_ctx):
        f = FormatAdapterFilter()
        result = f.apply(base_ctx)
        assert result is not None  # Should not crash

    def test_generates_documents_for_llm(self, base_ctx, data_for_adapt, mortgage_cluster):
        """When cluster has llm_reasoning agent_preference, generate documents."""
        import dataclasses
        cluster = {**mortgage_cluster, "agent_preference": "llm_reasoning"}
        ctx = dataclasses.replace(base_ctx, cluster=cluster)
        ctx = ctx.with_data(data_for_adapt)
        f = FormatAdapterFilter()
        result = f.apply(ctx)
        assert "documents" in result.meta
        docs = result.meta["documents"]
        assert len(docs) == 2
        assert "id" in docs[0]
        assert "text" in docs[0]

    def test_document_text_content(self, base_ctx, data_for_adapt, mortgage_cluster):
        import dataclasses
        cluster = {**mortgage_cluster, "agent_preference": "llm_reasoning"}
        ctx = dataclasses.replace(base_ctx, cluster=cluster)
        ctx = ctx.with_data(data_for_adapt)
        f = FormatAdapterFilter()
        result = f.apply(ctx)
        docs = result.meta["documents"]
        # Text should contain field values
        assert "北京路" in docs[0]["text"]

    def test_generates_enhanced_report(self, base_ctx, data_for_adapt, mortgage_cluster):
        ctx = base_ctx.with_data(data_for_adapt)
        f = FormatAdapterFilter()
        result = f.apply(ctx)
        assert "enhanced_report" in result.meta
        report = result.meta["enhanced_report"]
        assert "Enhanced Report" in report
        assert "Data Profile" in report
        assert "Column Details" in report

    def test_enhanced_report_with_analysis(self, base_ctx, data_for_adapt, mortgage_cluster):
        """Enhanced report should include analysis results when available."""
        import dataclasses
        ctx = base_ctx.with_data(data_for_adapt)
        ctx = dataclasses.replace(
            ctx,
            meta={
                **ctx.meta,
                "analysis_result": {
                    "outliers": {
                        "valuation_amount": {
                            "count": 1,
                            "rate": 0.5,
                            "extreme_min": 6000000.0,
                            "extreme_max": 6000000.0,
                        }
                    },
                    "correlation": {
                        "strong_pairs": [
                            {"col_a": "a", "col_b": "b", "correlation": 0.85},
                        ],
                    },
                },
            },
        )
        f = FormatAdapterFilter()
        result = f.apply(ctx)
        report = result.meta["enhanced_report"]
        assert "Outlier Summary" in report
        assert "Strong Correlations" in report

    def test_csv_batch_no_documents(self, base_ctx, data_for_adapt, mortgage_cluster):
        """For csv_batch preference, documents should NOT be generated."""
        import dataclasses
        cluster = {**mortgage_cluster, "agent_preference": "csv_batch"}
        ctx = dataclasses.replace(base_ctx, cluster=cluster)
        ctx = ctx.with_data(data_for_adapt)
        f = FormatAdapterFilter()
        result = f.apply(ctx)
        assert "documents" not in result.meta

    def test_document_handles_na(self, base_ctx, mortgage_cluster):
        """Documents should handle NaN values gracefully."""
        import dataclasses, numpy as np
        cluster = {**mortgage_cluster, "agent_preference": "llm_reasoning"}
        ctx = dataclasses.replace(base_ctx, cluster=cluster)
        df = pd.DataFrame({
            "property_address": ["Addr1", None],
            "building_area_sqm": [100.0, 200.0],
        })
        ctx = ctx.with_data(df)
        f = FormatAdapterFilter()
        result = f.apply(ctx)
        docs = result.meta["documents"]
        # NaN values should be skipped in text generation
        assert len(docs) == 2

    def test_rollback(self, base_ctx, data_for_adapt, mortgage_cluster):
        ctx = base_ctx.with_data(data_for_adapt)
        f = FormatAdapterFilter()
        result = f.apply(ctx)
        rolled = f.rollback(result)
        assert "documents" not in rolled.meta
        assert "enhanced_report" not in rolled.meta

    def test_filter_name(self):
        assert FormatAdapterFilter().name == "adapt_format"
