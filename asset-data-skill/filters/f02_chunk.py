"""f02_chunk: 文本分块 Filter — TC2 条目化预处理第一步。

职责: 将原始文本按语义/长度切分为可独立送入 LLM 的块。
支持策略模式替换分块算法。

Author: asset-data-skill
"""

from __future__ import annotations
import dataclasses

import logging
from typing import Protocol, runtime_checkable

from .context import PipelineContext
from .pipeline import Filter

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 2000
DEFAULT_OVERLAP = 200


@runtime_checkable
class ChunkStrategy(Protocol):
    """分块策略协议 — 可替换的分块算法。"""

    def chunk(self, text: str, size: int, overlap: int) -> list[str]: ...


class SemanticChunker:
    """语义分块器 — 优先按段落/句子边界切分。

    策略: 先按 \\n\\n 分段 → 合并短段 → 按句子边界微调。
    """

    def chunk(self, text: str, size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP) -> list[str]:
        paragraphs = text.split("\n\n")
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_len = len(para)

            if current_len + para_len > size and current:
                chunks.append("\n\n".join(current))
                # 滑动窗口重叠：保留最后一个段落
                if overlap > 0 and len(current) > 0:
                    last = current[-1]
                    current = [last] if len(last) < overlap else [last[-overlap:]]
                else:
                    current = []
                current_len = sum(len(p) for p in current)

            current.append(para)
            current_len += para_len

        if current:
            chunks.append("\n\n".join(current))

        return chunks


class SizeChunker:
    """定长分块器 — 按字符数硬切分，保证最大吞吐。"""

    def chunk(self, text: str, size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP) -> list[str]:
        chunks: list[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + size, text_len)
            chunks.append(text[start:end])
            if end >= text_len:
                break
            start = end - overlap
            if start <= 0:
                break

        return chunks


class ChunkFilter:
    """文本分块 Filter。

    将 ctx.raw_text 切分为块，结果存储在 ctx.meta["chunks"]。
    """

    name = "chunk"

    def __init__(
        self,
        strategy: ChunkStrategy | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
    ):
        self._strategy = strategy or SemanticChunker()
        self._chunk_size = chunk_size
        self._overlap = overlap

    def apply(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.raw_text:
            logger.info(f"[{self.name}] No raw_text, skipping")
            return ctx

        chunks = self._strategy.chunk(ctx.raw_text, self._chunk_size, self._overlap)
        logger.info(f"[{self.name}] Produced {len(chunks)} chunks (size={self._chunk_size}, overlap={self._overlap})")

        new_meta = {**ctx.meta, "chunks": chunks, "chunk_count": len(chunks)}
        new_ctx = ctx.with_metric("chunk_count", len(chunks))
        return dataclasses.replace(new_ctx, meta=new_meta)

    def rollback(self, ctx: PipelineContext) -> PipelineContext:
        new_meta = {k: v for k, v in ctx.meta.items() if k not in ("chunks", "chunk_count")}
        return dataclasses.replace(ctx, meta=new_meta)
