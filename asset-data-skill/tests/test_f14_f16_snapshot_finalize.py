"""Tests for f14_snapshot and f16_finalize."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from filters.f14_snapshot import SnapshotFilter
from filters.f16_finalize import FinalizeFilter


# ═══ SnapshotFilter ════════════════════════════════════════


class TestSnapshotFilter:
    def test_saves_data_csv(self, base_ctx_with_data, temp_cache_dir):
        f = SnapshotFilter(temp_cache_dir)
        result = f.apply(base_ctx_with_data)
        assert "data_csv" in result.artifacts
        csv_path = Path(result.artifacts["data_csv"])
        assert csv_path.exists()
        # Verify content
        df = pd.read_csv(csv_path)
        assert len(df) == 3

    def test_saves_schema_json(self, base_ctx, temp_cache_dir):
        import dataclasses
        ctx = dataclasses.replace(
            base_ctx,
            schema={"col1": {"type": "string"}},
            data=pd.DataFrame({"col1": ["a", "b"]}),
        )
        f = SnapshotFilter(temp_cache_dir)
        result = f.apply(ctx)
        assert "schema_json" in result.artifacts
        schema_path = Path(result.artifacts["schema_json"])
        assert schema_path.exists()
        with open(schema_path) as fp:
            loaded = json.load(fp)
        assert loaded["col1"]["type"] == "string"

    def test_saves_summary_md(self, base_ctx, temp_cache_dir):
        import dataclasses
        ctx = dataclasses.replace(
            base_ctx,
            summary="# Test Report",
            data=pd.DataFrame({"a": [1]}),
        )
        f = SnapshotFilter(temp_cache_dir)
        result = f.apply(ctx)
        assert "summary_md" in result.artifacts
        summary_path = Path(result.artifacts["summary_md"])
        assert summary_path.exists()
        content = summary_path.read_text()
        assert "Test Report" in content

    def test_saves_raw_entries(self, base_ctx, temp_cache_dir):
        entries = [{"fields": {"x": 1}, "confidence": 0.9}]
        ctx = base_ctx.with_entries(entries)
        f = SnapshotFilter(temp_cache_dir)
        result = f.apply(ctx)
        assert "raw_entries" in result.artifacts
        entries_path = Path(result.artifacts["raw_entries"])
        assert entries_path.exists()

    def test_no_data_skips_csv(self, base_ctx, temp_cache_dir):
        f = SnapshotFilter(temp_cache_dir)
        result = f.apply(base_ctx)
        assert "data_csv" not in result.artifacts

    def test_rollback_does_not_delete_files(self, base_ctx_with_data, temp_cache_dir):
        f = SnapshotFilter(temp_cache_dir)
        result = f.apply(base_ctx_with_data)
        csv_path = result.artifacts["data_csv"]
        rolled = f.rollback(result)
        # File should still exist on disk (data safety)
        assert Path(csv_path).exists()
        # But artifact entries are removed
        assert "data_csv" not in rolled.artifacts

    def test_creates_task_directory(self, base_ctx_with_data, temp_cache_dir):
        f = SnapshotFilter(temp_cache_dir)
        result = f.apply(base_ctx_with_data)
        task_dir = temp_cache_dir / base_ctx_with_data.task_id / "normalized"
        assert task_dir.exists()

    def test_filter_name(self):
        assert SnapshotFilter(tempfile.mkdtemp()).name == "snapshot"


# ═══ FinalizeFilter ════════════════════════════════════════


class TestFinalizeFilter:
    @pytest.fixture
    def ctx_with_snapshot(self, base_ctx, temp_cache_dir):
        """Create context after snapshot has been saved."""
        import dataclasses
        task_dir = temp_cache_dir / base_ctx.task_id / "normalized"
        task_dir.mkdir(parents=True)
        (task_dir / "data.csv").write_text("a,b\n1,2")
        (task_dir / "schema.json").write_text('{"a": {"type": "integer"}}')
        (task_dir / "summary.md").write_text("# Report")
        return dataclasses.replace(
            base_ctx,
            artifacts={
                "data_csv": str(task_dir / "data.csv"),
                "schema_json": str(task_dir / "schema.json"),
                "summary_md": str(task_dir / "summary.md"),
            },
            meta={**base_ctx.meta, "executed_filters": ["read", "clean"]},
        )

    def test_copies_to_final(self, ctx_with_snapshot, temp_cache_dir):
        f = FinalizeFilter(temp_cache_dir)
        result = f.apply(ctx_with_snapshot)
        final_dir = temp_cache_dir / ctx_with_snapshot.task_id / "final"
        assert final_dir.exists()
        assert (final_dir / "data.csv").exists()

    def test_updates_meta_json(self, ctx_with_snapshot, temp_cache_dir):
        f = FinalizeFilter(temp_cache_dir)
        result = f.apply(ctx_with_snapshot)
        meta_path = temp_cache_dir / ctx_with_snapshot.task_id / "meta.json"
        assert meta_path.exists()
        with open(meta_path) as fp:
            meta = json.load(fp)
        assert meta["status"] == "COMPLETED"
        assert "completed_at" in meta

    def test_attaches_lifecycle_policy(self, ctx_with_snapshot, temp_cache_dir):
        f = FinalizeFilter(temp_cache_dir)
        result = f.apply(ctx_with_snapshot)
        meta_path = temp_cache_dir / ctx_with_snapshot.task_id / "meta.json"
        with open(meta_path) as fp:
            meta = json.load(fp)
        assert "lifecycle_policy" in meta

    def test_artifact_recorded(self, ctx_with_snapshot, temp_cache_dir):
        f = FinalizeFilter(temp_cache_dir)
        result = f.apply(ctx_with_snapshot)
        assert "final_dir" in result.artifacts

    def test_rollback(self, ctx_with_snapshot, temp_cache_dir):
        f = FinalizeFilter(temp_cache_dir)
        result = f.apply(ctx_with_snapshot)
        rolled = f.rollback(result)
        meta_path = temp_cache_dir / ctx_with_snapshot.task_id / "meta.json"
        with open(meta_path) as fp:
            meta = json.load(fp)
        assert meta["status"] == "RUNNING"
        assert "completed_at" not in meta

    def test_filter_name(self):
        assert FinalizeFilter(tempfile.mkdtemp()).name == "finalize"

    def test_creates_meta_if_missing(self, base_ctx, temp_cache_dir):
        f = FinalizeFilter(temp_cache_dir)
        result = f.apply(base_ctx)
        meta_path = temp_cache_dir / base_ctx.task_id / "meta.json"
        assert meta_path.exists()
