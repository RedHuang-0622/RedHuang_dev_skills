"""f01_index: 索引查找 Filter — TC1.

从 index.json 加载资产目录，解析属性簇（含继承），
将 cluster 快照写入 PipelineContext。

Author: asset-data-skill
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..context import PipelineContext
from ..pipeline import Filter

logger = logging.getLogger(__name__)

MAX_INHERIT_DEPTH = 3


class IndexLookupFilter:
    """索引查找 Filter — 加载属性簇并冻结到 Context。

    职责:
    1. 从 index.json 查找 asset_type 对应的 cluster_ref
    2. 加载属性簇 JSON
    3. 解析继承链（深度限制 ≤3）
    4. 将合并后的 cluster 写入 ctx.cluster
    """

    name = "index_lookup"

    def __init__(self, config_dir: str | Path):
        self._config_dir = Path(config_dir)
        self._index_path = self._config_dir / "index.json"
        if not self._index_path.exists():
            raise FileNotFoundError(f"index.json not found: {self._index_path}")

        with open(self._index_path, encoding="utf-8") as f:
            self._index = json.load(f)

    def apply(self, ctx: PipelineContext) -> PipelineContext:
        catalog = self._index.get("asset_catalog", {})
        entry = catalog.get(ctx.asset_type)

        if entry is None:
            raise ValueError(
                f"Asset type '{ctx.asset_type}' not found in index.json. "
                f"Available: {list(catalog.keys())}"
            )

        cluster = self._load_with_inheritance(
            self._config_dir / entry["cluster_ref"]
        )
        logger.info(
            f"[{self.name}] Loaded cluster: {cluster.get('cluster_id')}, "
            f"{len(cluster.get('fields', {}))} fields"
        )

        return object.__replace__(ctx, cluster=cluster)

    def _load_with_inheritance(self, cluster_path: Path, depth: int = 0) -> dict:
        """加载属性簇并解析继承链。"""
        if depth > MAX_INHERIT_DEPTH:
            raise RecursionError(
                f"Inheritance depth exceeds {MAX_INHERIT_DEPTH} for {cluster_path}"
            )

        with open(cluster_path, encoding="utf-8") as f:
            cluster = json.load(f)

        parent_id = cluster.get("inherits_from")
        if not parent_id:
            return cluster

        # 查找基类文件
        base_path = self._find_base_cluster(parent_id)
        if base_path is None:
            logger.warning(f"Base cluster '{parent_id}' not found, skipping inheritance")
            return cluster

        parent = self._load_with_inheritance(base_path, depth + 1)

        # 合并：子覆盖父
        merged = deepcopy(parent)
        merged["cluster_id"] = cluster["cluster_id"]
        merged["is_base"] = False

        # 合并 fields
        parent_fields = merged.get("fields", {})
        child_fields = cluster.get("fields", {})
        for fname, fdef in child_fields.items():
            parent_fields[fname] = {**parent_fields.get(fname, {}), **fdef}
        merged["fields"] = parent_fields

        # 合并 computed_fields
        merged["computed_fields"] = {
            **parent.get("computed_fields", {}),
            **cluster.get("computed_fields", {}),
        }

        # 合并 lifecycle（子覆盖父）
        merged["lifecycle"] = {
            **parent.get("lifecycle", {}),
            **cluster.get("lifecycle", {}),
        }

        # 合并 table_mapping
        merged["table_mapping"] = {
            **parent.get("table_mapping", {}),
            **cluster.get("table_mapping", {}),
        }

        return merged

    def _find_base_cluster(self, cluster_id: str) -> Path | None:
        """在 clusters/ 目录下递归查找基类文件。"""
        clusters_dir = self._config_dir / "clusters"
        for candidate in clusters_dir.rglob("*.json"):
            try:
                with open(candidate, encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("cluster_id") == cluster_id:
                    return candidate
            except (json.JSONDecodeError, OSError):
                continue
        return None

    def rollback(self, ctx: PipelineContext) -> PipelineContext:
        return object.__replace__(ctx, cluster={})
