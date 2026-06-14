"""Tests for f09_read: ReaderFilter."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from filters.f09_read import ReaderFilter
from filters.context import PipelineContext


class TestReaderFilter:
    @pytest.fixture
    def csv_file(self) -> Path:
        """Create a temporary CSV file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("name,age,score\nAlice,25,85.5\nBob,30,90.0\n")
            return Path(f.name)

    @pytest.fixture
    def json_file(self) -> Path:
        """Create a temporary JSON file."""
        import json
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump([
                {"name": "Alice", "age": 25},
                {"name": "Bob", "age": 30},
            ], f)
            return Path(f.name)

    @pytest.fixture
    def xlsx_file(self) -> Path:
        """Create a temporary Excel file."""
        df = pd.DataFrame({"name": ["Alice"], "age": [25]})
        with tempfile.NamedTemporaryFile(
            suffix=".xlsx", delete=False
        ) as f:
            df.to_excel(f.name, index=False)
            return Path(f.name)

    def test_no_input_source(self, base_ctx):
        f = ReaderFilter()
        result = f.apply(base_ctx)
        assert result.data is None

    def test_read_csv(self, base_ctx, csv_file):
        import dataclasses
        ctx = dataclasses.replace(base_ctx, meta={"input_source": str(csv_file)})
        f = ReaderFilter()
        result = f.apply(ctx)
        assert result.data is not None
        assert len(result.data) == 2
        assert list(result.data.columns) == ["name", "age", "score"]

    def test_read_csv_metrics(self, base_ctx, csv_file):
        import dataclasses
        ctx = dataclasses.replace(base_ctx, meta={"input_source": str(csv_file)})
        f = ReaderFilter()
        result = f.apply(ctx)
        assert result.metrics["raw_row_count"] == 2

    def test_read_json(self, base_ctx, json_file):
        import dataclasses
        ctx = dataclasses.replace(base_ctx, meta={"input_source": str(json_file)})
        f = ReaderFilter()
        result = f.apply(ctx)
        assert result.data is not None
        assert len(result.data) == 2

    def test_read_excel(self, base_ctx, xlsx_file):
        import dataclasses
        ctx = dataclasses.replace(base_ctx, meta={"input_source": str(xlsx_file)})
        f = ReaderFilter()
        result = f.apply(ctx)
        assert result.data is not None
        assert len(result.data) == 1

    def test_missing_file(self, base_ctx):
        import dataclasses
        ctx = dataclasses.replace(base_ctx, meta={"input_source": "/nonexistent/file.csv"})
        f = ReaderFilter()
        with pytest.raises(FileNotFoundError):
            f.apply(ctx)

    def test_unknown_extension_reads_as_text(self, base_ctx):
        """Unknown extension should be read as raw text."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("Hello world")
            txt_path = Path(f.name)

        import dataclasses
        ctx = dataclasses.replace(base_ctx, meta={"input_source": str(txt_path)})
        f = ReaderFilter()
        result = f.apply(ctx)
        assert result.raw_text == "Hello world"

    def test_csv_encoding_detection(self, base_ctx):
        """CSV with non-UTF8 encoding should still be readable."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="gbk"
        ) as f:
            f.write("名称,年龄\n张三,25\n")
            gbk_path = Path(f.name)

        import dataclasses
        ctx = dataclasses.replace(base_ctx, meta={"input_source": str(gbk_path)})
        f = ReaderFilter()
        result = f.apply(ctx)
        # GBK should be auto-detected or fall back
        assert result.data is not None or result.raw_text is not None

    def test_rollback(self, base_ctx, csv_file):
        import dataclasses
        ctx = dataclasses.replace(base_ctx, meta={"input_source": str(csv_file)})
        f = ReaderFilter()
        result = f.apply(ctx)
        rolled = f.rollback(result)
        assert rolled.data is None

    def test_filter_name(self):
        assert ReaderFilter().name == "read"

    def test_explicit_encoding(self, base_ctx, csv_file):
        import dataclasses
        ctx = dataclasses.replace(base_ctx, meta={"input_source": str(csv_file)})
        f = ReaderFilter(encoding="utf-8")
        result = f.apply(ctx)
        assert result.data is not None
