"""f04_deduplicate: 条目去重 Filter — TC2 条目化预处理第三步。

基于字段相似度去重（地址、金额、名称等），
低置信度条目标记 needs_review。

Author: asset-data-skill
"""

from __future__ import annotations

import hashlib
import logging

from ..context import PipelineContext
from ..pipeline import Filter

logger = logging.getLogger(__name__)

DEFAULT_SIMILARITY_THRESHOLD = 0.85
LOW_CONFIDENCE_THRESHOLD = 0.7


class DeduplicateFilter:
    """条目去重 Filter。

    策略:
    1. 提取关键字段生成指纹 hash
    2. 相同指纹 → 保留置信度最高的
    3. 模糊匹配（基于地址/名称的编辑距离）— 阈值内 → 合并
    4. 低置信度条目标记 needs_review=True
    """

    name = "deduplicate"

    def __init__(self, similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD):
        self._threshold = similarity_threshold

    def apply(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.entries:
            logger.info(f"[{self.name}] No entries to deduplicate")
            return ctx

        entries = ctx.entries
        original_count = len(entries)

        # 1. 标记低置信度
        for entry in entries:
            if entry.get("confidence", 1.0) < LOW_CONFIDENCE_THRESHOLD:
                entry["needs_review"] = True

        # 2. 精确去重：基于字段指纹
        seen: dict[str, dict] = {}
        for entry in entries:
            fingerprint = self._compute_fingerprint(entry)
            if fingerprint in seen:
                # 保留置信度更高的
                existing = seen[fingerprint]
                if entry.get("confidence", 0) > existing.get("confidence", 0):
                    seen[fingerprint] = entry
            else:
                seen[fingerprint] = entry

        deduped = list(seen.values())

        # 3. 模糊去重：基于关键字段相似度
        final = self._fuzzy_dedup(deduped)

        removed = original_count - len(final)
        logger.info(
            f"[{self.name}] {original_count} → {len(final)} entries "
            f"({removed} duplicates removed, "
            f"{sum(1 for e in final if e.get('needs_review'))} flagged for review)"
        )

        return ctx.with_entries(final).with_metric("dedup_removed", removed)

    def _compute_fingerprint(self, entry: dict) -> str:
        """基于关键字段值计算指纹 hash。"""
        fields = entry.get("fields", {})
        # 使用地址、名称等稳定字段
        key_parts = []
        for fname in ("property_address", "ship_name", "equipment_name", "地址", "名称"):
            val = fields.get(fname, "")
            if val:
                key_parts.append(str(val).strip().lower())
        if not key_parts:
            # 回退：整个 fields 的 JSON
            key_parts = [json.dumps(fields, sort_keys=True, ensure_ascii=False)]

        import json
        raw = "|".join(key_parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _fuzzy_dedup(self, entries: list[dict]) -> list[dict]:
        """基于编辑距离的模糊去重。"""
        if len(entries) <= 1:
            return entries

        result: list[dict] = []
        merged_indices: set[int] = set()

        for i, entry in enumerate(entries):
            if i in merged_indices:
                continue

            for j in range(i + 1, len(entries)):
                if j in merged_indices:
                    continue

                similarity = self._compute_similarity(entry, entries[j])
                if similarity >= self._threshold:
                    # 保留置信度更高的
                    if entries[j].get("confidence", 0) > entry.get("confidence", 0):
                        entry = entries[j]
                    merged_indices.add(j)
                    entry["_merged_from"] = entry.get("_merged_from", 0) + 1

            result.append(entry)

        return result

    def _compute_similarity(self, a: dict, b: dict) -> float:
        """计算两个条目关键字段的 Jaccard 相似度。"""
        fields_a = a.get("fields", {})
        fields_b = b.get("fields", {})

        all_keys = set(fields_a.keys()) & set(fields_b.keys())
        if not all_keys:
            return 0.0

        matches = 0
        for key in all_keys:
            val_a = str(fields_a.get(key, "")).strip().lower()
            val_b = str(fields_b.get(key, "")).strip().lower()
            if val_a and val_b and val_a == val_b:
                matches += 1

        return matches / len(all_keys) if all_keys else 0.0

    def rollback(self, ctx: PipelineContext) -> PipelineContext:
        return ctx.with_entries(None)
