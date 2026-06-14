"""f14_snapshot: 快照保存 Filter — TC5 任务缓存。

职责: 将当前数据状态保存为快照文件（data.csv + schema.json + summary.md）
写入 task_cache/{task_id}/steps/ 目录。

Author: asset-data-skill
"""

from __future__ import annotations
import dataclasses

import json
import logging
from pathlib import Path

import pandas as pd

from .context import PipelineContext
from .pipeline import Filter

logger = logging.getLogger(__name__)


class SnapshotFilter:
    """快照保存 Filter — 将数据包三件套持久化到 task_cache。

    输出:
    - {task_cache}/{task_id}/normalized/data.csv
    - {task_cache}/{task_id}/normalized/schema.json
    - {task_cache}/{task_id}/normalized/summary.md
    """

    name = "snapshot"

    def __init__(self, task_cache_dir: str | Path):
        self._cache_dir = Path(task_cache_dir)

    def apply(self, ctx: PipelineContext) -> PipelineContext:
        task_dir = self._cache_dir / ctx.task_id / "normalized"
        task_dir.mkdir(parents=True, exist_ok=True)

        artifacts: dict[str, str] = {}

        # 保存 data.csv
        if ctx.data is not None:
            csv_path = task_dir / "data.csv"
            ctx.data.to_csv(csv_path, index=False, encoding="utf-8-sig")
            artifacts["data_csv"] = str(csv_path)
            logger.info(f"[{self.name}] Saved data.csv: {len(ctx.data)} rows")

        # 保存 schema.json
        if ctx.schema is not None:
            schema_path = task_dir / "schema.json"
            with open(schema_path, "w", encoding="utf-8") as f:
                json.dump(ctx.schema, f, ensure_ascii=False, indent=2)
            artifacts["schema_json"] = str(schema_path)

        # 保存 summary.md
        if ctx.summary is not None:
            summary_path = task_dir / "summary.md"
            summary_path.write_text(ctx.summary, encoding="utf-8")
            artifacts["summary_md"] = str(summary_path)

        # 保存 raw_entries.json（如果存在）
        if ctx.entries is not None:
            entries_path = task_dir / "raw_entries.json"
            with open(entries_path, "w", encoding="utf-8") as f:
                json.dump(ctx.entries, f, ensure_ascii=False, indent=2)
            artifacts["raw_entries"] = str(entries_path)

        new_artifacts = {**ctx.artifacts, **artifacts}
        logger.info(
            f"[{self.name}] Snapshot saved: {list(artifacts.keys())}"
        )

        result = ctx.with_artifact("snapshot", str(task_dir))
        return dataclasses.replace(result, artifacts=new_artifacts)

    def rollback(self, ctx: PipelineContext) -> PipelineContext:
        # 不删除文件（数据安全），仅从 artifacts 中移除
        new_artifacts = {
            k: v for k, v in ctx.artifacts.items()
            if k not in ("data_csv", "schema_json", "summary_md", "raw_entries")
        }
        return dataclasses.replace(ctx, artifacts=new_artifacts)
