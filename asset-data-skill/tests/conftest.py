"""Shared fixtures and helpers for asset-data-skill tests."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from filters.context import PipelineContext


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Create a sample DataFrame with real estate mortgage data."""
    return pd.DataFrame({
        "房产地址": ["北京市朝阳区XX路1号", "上海市浦东新区YY路2号", "广州市天河区ZZ路3号"],
        "建筑面积": ["120.5", "85.3", "200.0"],
        "抵押金额": ["500万元", "300万元", "800万元"],
        "估值金额": [6000000, 3500000, 10000000],
        "登记日期": ["2023-01-15", "2023/06/20", "2023年12月01日"],
        "用途": ["商业", "住宅", "商业"],
    })


@pytest.fixture
def mortgage_cluster() -> dict:
    """Load the mortgage property cluster."""
    return {
        "cluster_id": "RE_MORTGAGE",
        "inherits_from": "real_estate_base",
        "sensitivity": "sensitive",
        "is_base": False,
        "fields": {
            "property_address": {
                "type": "string",
                "required": True,
                "aliases": ["房产地址", "物业地址", "坐落"],
                "access_level": "internal",
            },
            "building_area_sqm": {
                "type": "float",
                "aliases": ["建筑面积", "面积(㎡)"],
                "unit": "平方米",
                "min": 0,
                "normalization_available": ["zscore", "minmax"],
            },
            "mortgage_amount": {
                "type": "float",
                "aliases": ["抵押金额", "担保债权额"],
                "unit": "元",
                "common_errors": ["包含汉字'万'", "负数"],
            },
            "valuation_amount": {
                "type": "float",
                "aliases": ["估值金额"],
                "unit": "元",
            },
            "registration_date": {
                "type": "date",
                "aliases": ["登记日期"],
            },
            "property_type": {
                "type": "string",
                "aliases": ["用途"],
                "enum": ["住宅", "商业", "办公"],
            },
        },
        "computed_fields": {
            "抵押率": "mortgage_amount / valuation_amount",
        },
        "table_mapping": {
            "default_columns": [
                "property_address",
                "building_area_sqm",
                "mortgage_amount",
                "valuation_amount",
                "registration_date",
            ],
        },
        "lifecycle": {
            "default_ttl_days": 90,
            "backup_required": True,
        },
    }


@pytest.fixture
def base_ctx(mortgage_cluster) -> PipelineContext:
    """Create a base PipelineContext for testing."""
    return PipelineContext(
        task_id="test-task-001",
        asset_type="RE_MORTGAGE",
        role="analyst",
        cluster=mortgage_cluster,
    )


@pytest.fixture
def base_ctx_with_data(base_ctx, sample_df) -> PipelineContext:
    """Create a context with data loaded."""
    return base_ctx.with_data(sample_df)


@pytest.fixture
def config_dir() -> Path:
    """Path to the configs directory."""
    return Path(__file__).parent.parent / "configs"


@pytest.fixture
def temp_cache_dir() -> Path:
    """Create a temporary task cache directory."""
    with tempfile.TemporaryDirectory(prefix="task_cache_") as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_output_dir() -> Path:
    """Create a temporary output directory for snapshots."""
    with tempfile.TemporaryDirectory(prefix="output_") as tmpdir:
        yield Path(tmpdir)
