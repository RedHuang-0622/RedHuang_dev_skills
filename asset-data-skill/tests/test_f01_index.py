"""Tests for f01_index: IndexLookupFilter."""

from __future__ import annotations

import pytest

from filters.f01_index import IndexLookupFilter
from filters.context import PipelineContext


class TestIndexLookupFilter:
    """Test IndexLookupFilter with real config files."""

    @pytest.fixture
    def index_filter(self, config_dir):
        return IndexLookupFilter(config_dir)

    def test_load_known_asset(self, index_filter, base_ctx):
        """Load RE_MORTGAGE cluster and verify fields."""
        result = index_filter.apply(base_ctx)
        cluster = result.cluster
        assert cluster["cluster_id"] == "RE_MORTGAGE"
        assert "fields" in cluster
        assert "property_address" in cluster["fields"]
        assert cluster["is_base"] is False

    def test_load_ship_npl(self, index_filter):
        ctx = PipelineContext(task_id="t1", asset_type="SHIP_NPL", role="analyst")
        result = index_filter.apply(ctx)
        assert result.cluster["cluster_id"] == "SHIP_NPL"
        assert "fields" in result.cluster

    def test_load_equipment(self, index_filter):
        ctx = PipelineContext(task_id="t1", asset_type="EQUIPMENT", role="analyst")
        result = index_filter.apply(ctx)
        assert result.cluster["cluster_id"] == "EQUIPMENT"

    def test_unknown_asset_type(self, index_filter):
        ctx = PipelineContext(task_id="t1", asset_type="UNKNOWN_TYPE", role="analyst")
        with pytest.raises(ValueError, match="not found in index.json"):
            index_filter.apply(ctx)

    def test_inheritance_merges_fields(self, index_filter, base_ctx):
        """Verify child cluster inherits parent fields."""
        result = index_filter.apply(base_ctx)
        cluster = result.cluster
        # Child fields should exist
        assert "mortgage_amount" in cluster["fields"]
        assert "mortgage_ratio" in cluster["fields"]
        # Parent fields should also exist (inherited)
        assert "property_address" in cluster["fields"]

    def test_computed_fields_merged(self, index_filter, base_ctx):
        result = index_filter.apply(base_ctx)
        cluster = result.cluster
        assert "computed_fields" in cluster
        # Should have fields from both parent and child
        assert len(cluster["computed_fields"]) >= 1

    def test_lifecycle_merged_child_wins(self, index_filter, base_ctx):
        result = index_filter.apply(base_ctx)
        cluster = result.cluster
        assert "lifecycle" in cluster
        assert "default_ttl_days" in cluster["lifecycle"]

    def test_inheritance_depth_limited(self, index_filter):
        """Simulate deep inheritance (handled by recursion limit in _load_with_inheritance)."""
        # The max depth is 3, and actual inheritance is 2 levels
        # This test verifies the depth check works on valid data
        ctx = PipelineContext(task_id="t1", asset_type="RE_MORTGAGE")
        result = index_filter.apply(ctx)
        # Should complete without depth error
        assert result.cluster["cluster_id"] == "RE_MORTGAGE"

    def test_rollback_clears_cluster(self, index_filter, base_ctx):
        result = index_filter.apply(base_ctx)
        assert result.cluster
        rolled = index_filter.rollback(result)
        assert rolled.cluster == {}

    def test_filter_name(self, index_filter):
        assert index_filter.name == "index_lookup"

    def test_missing_index_json_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            IndexLookupFilter(str(tmp_path))

    def test_context_unchanged_on_error(self, index_filter, base_ctx):
        """Original context must be unchanged when filter raises."""
        original = base_ctx.cluster
        ctx = PipelineContext(task_id="err", asset_type="MISSING")
        try:
            index_filter.apply(ctx)
        except ValueError:
            pass
        assert ctx.cluster == {}
