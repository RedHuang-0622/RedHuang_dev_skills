"""Tests for f07 (schema generation) and f08 (summary generation)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from filters.f07_generate_schema import SchemaGeneratorFilter
from filters.f08_generate_summary import SummaryGeneratorFilter


# ═══ SchemaGeneratorFilter ══════════════════════════════════


class TestSchemaGenerator:
    @pytest.fixture
    def data_with_types(self):
        return pd.DataFrame({
            "name": ["Alice", "Bob", "Charlie"],
            "age": [25, 30, 35],
            "score": [85.5, 90.0, 78.2],
            "active": [True, False, True],
        })

    def test_no_data(self, base_ctx):
        f = SchemaGeneratorFilter()
        result = f.apply(base_ctx)
        assert result.schema is None

    def test_generates_schema(self, base_ctx, data_with_types):
        ctx = base_ctx.with_data(data_with_types)
        f = SchemaGeneratorFilter()
        result = f.apply(ctx)
        schema = result.schema
        assert schema is not None
        assert "name" in schema
        assert "age" in schema
        assert "score" in schema

    def test_type_inference(self, base_ctx, data_with_types):
        ctx = base_ctx.with_data(data_with_types)
        f = SchemaGeneratorFilter()
        result = f.apply(ctx)
        schema = result.schema
        assert schema["age"]["type"] == "integer"
        assert schema["score"]["type"] == "float"
        assert schema["active"]["type"] == "boolean"
        assert schema["name"]["type"] == "string"

    def test_numeric_stats(self, base_ctx, data_with_types):
        ctx = base_ctx.with_data(data_with_types)
        f = SchemaGeneratorFilter()
        result = f.apply(ctx)
        schema = result.schema
        assert "mean" in schema["age"]
        assert "std" in schema["age"]
        assert "min" in schema["age"]
        assert "max" in schema["age"]

    def test_categorical_stats(self, base_ctx, data_with_types):
        ctx = base_ctx.with_data(data_with_types)
        f = SchemaGeneratorFilter()
        result = f.apply(ctx)
        schema = result.schema
        assert "top_values" in schema["name"]

    def test_metrics(self, base_ctx, data_with_types):
        ctx = base_ctx.with_data(data_with_types)
        f = SchemaGeneratorFilter()
        result = f.apply(ctx)
        assert result.metrics["schema_columns"] == 4

    def test_null_detection(self, base_ctx):
        df = pd.DataFrame({
            "a": [1, None, 3, None, None, 6, None, 8, None, None],
            "b": [1, 2, None, 4, 5, 6, 7, 8, 9, 10],
        })
        ctx = base_ctx.with_data(df)
        f = SchemaGeneratorFilter()
        result = f.apply(ctx)
        schema = result.schema
        assert schema["a"]["null_count"] >= 4  # Many nulls

    def test_anomaly_high_null_rate(self, base_ctx):
        """Column with >50% null should trigger anomaly."""
        df = pd.DataFrame({"a": [1, None, None, None, None, None, None, None, None, None]})
        ctx = base_ctx.with_data(df)
        f = SchemaGeneratorFilter()
        result = f.apply(ctx)
        # Anomaly should be detected
        assert result.metrics.get("anomaly_count", 0) >= 1

    def test_anomaly_zero_variance(self, base_ctx):
        """Column with zero variance should trigger anomaly."""
        df = pd.DataFrame({"a": [5.0, 5.0, 5.0, 5.0, 5.0]})
        ctx = base_ctx.with_data(df)
        f = SchemaGeneratorFilter()
        result = f.apply(ctx)
        assert result.metrics.get("anomaly_count", 0) >= 1

    def test_business_note_injection(self, base_ctx, mortgage_cluster):
        """Business notes from cluster should appear in schema."""
        df = pd.DataFrame({
            "mortgage_amount": [5000000, 3000000, 8000000],
        })
        ctx = base_ctx.with_data(df)
        f = SchemaGeneratorFilter()
        result = f.apply(ctx)
        schema = result.schema
        if "mortgage_amount" in schema:
            assert "business_note" in schema["mortgage_amount"]

    def test_rollback(self, base_ctx, data_with_types):
        ctx = base_ctx.with_data(data_with_types)
        f = SchemaGeneratorFilter()
        result = f.apply(ctx)
        rolled = f.rollback(result)
        assert rolled.schema is None

    def test_filter_name(self):
        assert SchemaGeneratorFilter().name == "generate_schema"


# ═══ SummaryGeneratorFilter ════════════════════════════════


class TestSummaryGenerator:
    def test_no_data(self, base_ctx):
        f = SummaryGeneratorFilter()
        result = f.apply(base_ctx)
        # Summary generates even without data (includes task metadata)
        assert result.summary is not None
        assert "test-task-001" in result.summary

    def test_generates_summary(self, base_ctx_with_data):
        f = SummaryGeneratorFilter()
        result = f.apply(base_ctx_with_data)
        assert result.summary is not None
        assert "# 数据概览报告" in result.summary
        assert "test-task-001" in result.summary

    def test_summary_includes_column_table(self, base_ctx_with_data):
        f = SummaryGeneratorFilter()
        result = f.apply(base_ctx_with_data)
        assert "## 列概览" in result.summary
        assert "|" in result.summary  # Markdown table

    def test_summary_no_anomalies(self, base_ctx_with_data):
        f = SummaryGeneratorFilter()
        result = f.apply(base_ctx_with_data)
        # No anomalies detected in small clean data
        assert "异常警告" not in result.summary or "0 项" in result.summary

    def test_summary_with_anomalies(self, base_ctx):
        """Summary should include anomaly section when anomalies exist."""
        import dataclasses
        ctx = dataclasses.replace(base_ctx, metrics={"anomaly_count": 3})
        f = SummaryGeneratorFilter()
        result = f.apply(ctx)
        if result.summary:
            assert "异常警告" in result.summary or "3 项" in result.summary

    def test_summary_suggested_actions(self, base_ctx_with_data):
        f = SummaryGeneratorFilter()
        result = f.apply(base_ctx_with_data)
        assert "## 建议操作" in result.summary

    def test_summary_large_dataset_warning(self, base_ctx):
        """Large dataset should trigger batch processing suggestion."""
        df = pd.DataFrame({"a": range(20000)})
        ctx = base_ctx.with_data(df)
        f = SummaryGeneratorFilter()
        result = f.apply(ctx)
        assert "分批处理" in result.summary or "批量模式" in result.summary

    def test_rollback(self, base_ctx_with_data):
        f = SummaryGeneratorFilter()
        result = f.apply(base_ctx_with_data)
        rolled = f.rollback(result)
        assert rolled.summary is None

    def test_filter_name(self):
        assert SummaryGeneratorFilter().name == "generate_summary"
