"""f16_finalize: 任务完结 Filter — TC5 任务缓存。

职责: 更新 meta.json 状态为 COMPLETED，整理最终交付物到 final/ 目录，
附加生命周期策略，记录审计日志。

Author: asset-data-skill
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .context import PipelineContext
from .pipeline import Filter

logger = logging.getLogger(__name__)


class FinalizeFilter:
    """任务完结 Filter — 整理最终交付物并更新任务状态。

    流程:
    1. 将 normalized/ 目录内容复制到 final/（最终交付物）
    2. 更新 meta.json: status=COMPLETED, completed_at=now
    3. 附加生命周期策略到 meta.json
    4. 记录审计事件
    """

    name = "finalize"

    def __init__(self, task_cache_dir: str | Path):
        self._cache_dir = Path(task_cache_dir)

    def apply(self, ctx: PipelineContext) -> PipelineContext:
        task_dir = self._cache_dir / ctx.task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        final_dir = task_dir / "final"
        normalized_dir = task_dir / "normalized"

        # 1. 复制 normalized → final
        if normalized_dir.exists():
            if final_dir.exists():
                shutil.rmtree(final_dir)
            shutil.copytree(normalized_dir, final_dir)
            logger.info(f"[{self.name}] Finalized to: {final_dir}")

        # 2. 更新 meta.json
        meta_path = task_dir / "meta.json"
        meta = self._load_or_create_meta(meta_path, ctx)
        meta["status"] = "COMPLETED"
        meta["completed_at"] = datetime.now(timezone.utc).isoformat()
        meta["executed_filters"] = ctx.meta.get("executed_filters", [])
        meta["final_artifacts"] = ctx.artifacts

        # 3. 附加生命周期策略
        lifecycle = ctx.cluster.get("lifecycle", {})
        if lifecycle:
            meta["lifecycle_policy"] = lifecycle

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        logger.info(
            f"[{self.name}] Task {ctx.task_id} completed. "
            f"Final artifacts: {list(ctx.artifacts.keys())}"
        )

        return ctx.with_artifact("final_dir", str(final_dir))

    def _load_or_create_meta(
        self, meta_path: Path, ctx: PipelineContext
    ) -> dict:
        """加载或创建 meta.json。"""
        if meta_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                return json.load(f)

        return {
            "task_id": ctx.task_id,
            "asset_type": ctx.asset_type,
            "role": ctx.role,
            "status": "RUNNING",
            "current_step": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "step_checksums": {},
        }

    def rollback(self, ctx: PipelineContext) -> PipelineContext:
        # 将 meta.json 状态改回 RUNNING
        meta_path = self._cache_dir / ctx.task_id / "meta.json"
        if meta_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            meta["status"] = "RUNNING"
            meta.pop("completed_at", None)
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        return ctx
