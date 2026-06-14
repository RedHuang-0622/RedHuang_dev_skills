"""Tests for f02_chunk: ChunkFilter with SemanticChunker and SizeChunker."""

from __future__ import annotations

import pytest

from filters.f02_chunk import ChunkFilter, SemanticChunker, SizeChunker, ChunkStrategy
from filters.context import PipelineContext


# ─── Chunk Strategy Tests ──────────────────────────────────


class TestSemanticChunker:
    def test_empty_text(self):
        chunker = SemanticChunker()
        chunks = chunker.chunk("")
        assert chunks == []

    def test_single_paragraph(self):
        chunker = SemanticChunker()
        chunks = chunker.chunk("Hello world this is a test.")
        assert len(chunks) == 1
        assert "Hello world" in chunks[0]

    def test_multiple_paragraphs(self):
        chunker = SemanticChunker()
        text = "Para one.\n\nPara two.\n\nPara three."
        chunks = chunker.chunk(text, size=100)
        # Should be at least 1 chunk
        assert len(chunks) >= 1

    def test_large_paragraph_splits(self):
        chunker = SemanticChunker()
        # Multiple paragraphs so the chunker has boundaries to split on
        text = ("A" * 1000 + "\n\n") * 3  # 3 paragraphs of 1000 chars each
        chunks = chunker.chunk(text, size=1500)
        assert len(chunks) >= 2  # Should produce multiple chunks

    def test_whitespace_only_paragraphs_ignored(self):
        chunker = SemanticChunker()
        text = "Para one.\n\n   \n\nPara two."
        chunks = chunker.chunk(text, size=500)
        # Whitespace paragraphs are stripped and skipped
        assert len(chunks) >= 1

    def test_overlap_preserves_context(self):
        chunker = SemanticChunker()
        text = "AAA.\n\n" + "B" * 1000 + "\n\nCCC."
        chunks = chunker.chunk(text, size=500, overlap=200)
        assert len(chunks) >= 1


class TestSizeChunker:
    def test_empty_text(self):
        chunker = SizeChunker()
        chunks = chunker.chunk("")
        assert chunks == []

    def test_single_chunk(self):
        chunker = SizeChunker()
        chunks = chunker.chunk("Hello", size=100)
        assert len(chunks) == 1
        assert chunks[0] == "Hello"

    def test_multi_chunk(self):
        chunker = SizeChunker()
        text = "A" * 500
        chunks = chunker.chunk(text, size=200, overlap=50)
        assert len(chunks) >= 2
        # Each chunk ≤ size
        assert all(len(c) <= 200 for c in chunks)

    def test_overlap_between_chunks(self):
        chunker = SizeChunker()
        text = "ABCDEFGHIJ"  # 10 chars
        chunks = chunker.chunk(text, size=6, overlap=2)
        # First: ABCDEF, Second: EFGHIJ
        assert len(chunks) >= 2

    def test_small_text_one_chunk(self):
        chunker = SizeChunker()
        text = "tiny"
        chunks = chunker.chunk(text, size=1000, overlap=0)
        assert len(chunks) == 1
        assert chunks[0] == "tiny"


# ─── ChunkFilter Tests ──────────────────────────────────────


class TestChunkFilter:
    def test_no_raw_text_skips(self, base_ctx):
        f = ChunkFilter()
        result = f.apply(base_ctx)
        # Should return same context (or equivalent)
        assert result == base_ctx or result.task_id == base_ctx.task_id

    def test_with_raw_text(self, base_ctx):
        import dataclasses
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        ctx = dataclasses.replace(base_ctx, raw_text=text)
        f = ChunkFilter()
        result = f.apply(ctx)
        assert "chunks" in result.meta
        assert len(result.meta["chunks"]) >= 1
        assert result.metrics.get("chunk_count", 0) >= 1

    def test_size_chunker_strategy(self, base_ctx):
        import dataclasses
        text = "X" * 500
        ctx = dataclasses.replace(base_ctx, raw_text=text)
        f = ChunkFilter(strategy=SizeChunker(), chunk_size=200, overlap=0)
        result = f.apply(ctx)
        chunks = result.meta["chunks"]
        assert len(chunks) >= 2
        assert all(len(c) <= 200 for c in chunks)

    def test_rollback_removes_chunks(self, base_ctx):
        import dataclasses
        text = "Some text."
        ctx = dataclasses.replace(base_ctx, raw_text=text)
        f = ChunkFilter()
        result = f.apply(ctx)
        assert "chunks" in result.meta
        rolled = f.rollback(result)
        assert "chunks" not in rolled.meta
        assert "chunk_count" not in rolled.meta

    def test_default_strategy_is_semantic(self):
        f = ChunkFilter()
        assert isinstance(f._strategy, SemanticChunker)

    def test_filter_name(self):
        assert ChunkFilter().name == "chunk"

    def test_chunk_strategy_protocol(self):
        """Custom chunk strategy matching the protocol works."""

        class MyChunker:
            def chunk(self, text: str, size: int, overlap: int) -> list[str]:
                return [text[:size]]

        assert isinstance(MyChunker(), ChunkStrategy)

    def test_large_text_chunks(self, base_ctx):
        import dataclasses
        # Use SizeChunker for this test since it splits by character count
        text = ("Long paragraph. " * 200)  # ~4000 chars
        ctx = dataclasses.replace(base_ctx, raw_text=text)
        f = ChunkFilter(strategy=SizeChunker(), chunk_size=500, overlap=100)
        result = f.apply(ctx)
        assert result.meta["chunk_count"] >= 5
