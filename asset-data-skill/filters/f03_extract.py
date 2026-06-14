"""f03_extract: LLM 条目提取 Filter — TC2 条目化预处理第二步。

职责: 将分块文本通过 LLM 提取为结构化条目。
使用 Jinja2 模板注入字段定义，支持重试和 Schema 校验。

Author: asset-data-skill
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

from .context import PipelineContext
from .pipeline import Filter

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


@runtime_checkable
class LLMBackend(Protocol):
    """LLM 后端协议 — 抽象 LLM 调用。具体实现由部署环境注入。"""

    def complete(self, prompt: str, **kwargs) -> str: ...


class LLMExtractorFilter:
    """LLM 条目提取 Filter。

    流程:
    1. 加载 Prompt 模板（Jinja2）
    2. 对每个 chunk 填入字段定义和文本
    3. 调用 LLM → 解析 JSON
    4. 聚合所有块结果
    5. 写入 ctx.entries
    """

    name = "extract"

    def __init__(
        self,
        prompt_dir: str | Path,
        llm_backend: LLMBackend,
        template_name: str = "extract_entries_generic.md",
    ):
        self._prompt_dir = Path(prompt_dir)
        self._llm = llm_backend
        self._template_name = template_name

    def apply(self, ctx: PipelineContext) -> PipelineContext:
        chunks: list[str] = ctx.meta.get("chunks", [])
        if not chunks:
            logger.warning(f"[{self.name}] No chunks found in context, skipping")
            return ctx

        # 加载 Prompt 模板
        template = self._load_template()

        # 构建字段描述表
        fields_table = self._build_fields_table(ctx.cluster)

        all_entries: list[dict] = []

        for i, chunk in enumerate(chunks):
            prompt = self._fill_template(
                template,
                asset_type_name=ctx.cluster.get("cluster_id", ctx.asset_type),
                fields_table=fields_table,
                raw_text=chunk,
            )

            entries = self._extract_with_retry(prompt, chunk_index=i)
            all_entries.extend(entries)

        logger.info(
            f"[{self.name}] Extracted {len(all_entries)} entries from {len(chunks)} chunks"
        )

        return ctx.with_entries(all_entries).with_metric(
            "raw_entry_count", len(all_entries)
        )

    def _load_template(self) -> str:
        template_path = self._prompt_dir / "extraction" / self._template_name
        if not template_path.exists():
            # Fallback to generic template
            template_path = self._prompt_dir / "extraction" / "extract_entries_generic.md"
        if not template_path.exists():
            raise FileNotFoundError(
                f"Prompt template not found: {template_path}"
            )
        return template_path.read_text(encoding="utf-8")

    def _build_fields_table(self, cluster: dict) -> str:
        """构建 Markdown 表格格式的字段描述。"""
        lines = ["| 字段名 | 类型 | 别名 | 必填 |",
                 "|--------|------|------|------|"]
        for fname, fdef in cluster.get("fields", {}).items():
            aliases = ", ".join(fdef.get("aliases", []))
            required = "是" if fdef.get("required") else "否"
            ftype = fdef.get("type", "string")
            lines.append(f"| {fname} | {ftype} | {aliases} | {required} |")
        return "\n".join(lines)

    def _fill_template(
        self, template: str, asset_type_name: str, fields_table: str, raw_text: str
    ) -> str:
        """Jinja2 风格的变量替换（简化实现）。"""
        return (
            template
            .replace("{{ asset_type_name }}", asset_type_name)
            .replace("{{ fields_table }}", fields_table)
            .replace("{{ raw_text }}", raw_text)
        )

    def _extract_with_retry(self, prompt: str, chunk_index: int) -> list[dict]:
        """带重试的 LLM 提取，最多 3 次。"""
        for attempt in range(MAX_RETRIES):
            try:
                response = self._llm.complete(prompt)
                # 从 response 中提取 JSON 数组
                entries = self._parse_json_response(response)
                # 标记 chunk 来源
                for entry in entries:
                    entry["_chunk_index"] = chunk_index
                return entries
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(
                    f"[{self.name}] Chunk {chunk_index} attempt {attempt + 1}/{MAX_RETRIES} failed: {e}"
                )
                if attempt == MAX_RETRIES - 1:
                    logger.error(
                        f"[{self.name}] Chunk {chunk_index} exhausted retries, returning empty"
                    )
        return []

    def _parse_json_response(self, response: str) -> list[dict]:
        """从 LLM 响应中提取 JSON 数组。"""
        # 尝试直接解析
        try:
            result = json.loads(response)
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                return [result]
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 代码块
        import re
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
        if match:
            result = json.loads(match.group(1))
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                return [result]

        raise ValueError(f"Unable to parse JSON from LLM response")

    def rollback(self, ctx: PipelineContext) -> PipelineContext:
        return ctx.with_entries(None)
