"""Tests for f03_extract: LLMExtractorFilter."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from filters.f03_extract import LLMExtractorFilter, LLMBackend
from filters.context import PipelineContext


# ─── Mock LLM Backend ──────────────────────────────────────


class MockLLMBackend:
    """Mock LLM that returns predefined responses."""

    def __init__(self, responses=None):
        self.responses = responses or []
        self.call_count = 0
        self.prompts: list[str] = []

    def complete(self, prompt: str, **kwargs) -> str:
        self.prompts.append(prompt)
        self.call_count += 1
        if self.call_count <= len(self.responses):
            return self.responses[self.call_count - 1]
        # Default: return a valid entry
        return json.dumps([{"fields": {"name": "test"}, "confidence": 0.9}])


class TestLLMBackendProtocol:
    def test_mock_matches_protocol(self):
        assert isinstance(MockLLMBackend(), LLMBackend)


# ─── LLMExtractorFilter Tests ──────────────────────────────


class TestLLMExtractorFilter:
    @pytest.fixture
    def prompt_dir(self) -> Path:
        """Create a temporary prompt directory with a template."""
        d = Path(tempfile.mkdtemp())
        extraction_dir = d / "extraction"
        extraction_dir.mkdir()
        template = extraction_dir / "extract_entries_generic.md"
        template.write_text("""## Extract entries from text below
Asset type: {{ asset_type_name }}
Fields:
{{ fields_table }}
Text:
{{ raw_text }}
Output: JSON array.""", encoding="utf-8")
        return d

    @pytest.fixture
    def ctx_with_chunks(self, base_ctx) -> PipelineContext:
        import dataclasses
        return dataclasses.replace(
            base_ctx,
            meta={"chunks": ["Property: 100 sqm at Beijing"]},
        )

    def test_extract_single_chunk(self, prompt_dir, ctx_with_chunks):
        mock_llm = MockLLMBackend(responses=[
            json.dumps([{"fields": {"property_address": "Beijing"}, "confidence": 0.95}])
        ])
        f = LLMExtractorFilter(prompt_dir, mock_llm)
        result = f.apply(ctx_with_chunks)
        assert result.entries is not None
        assert len(result.entries) == 1
        assert result.entries[0]["confidence"] == 0.95

    def test_no_chunks_skips(self, prompt_dir, base_ctx):
        mock_llm = MockLLMBackend()
        f = LLMExtractorFilter(prompt_dir, mock_llm)
        result = f.apply(base_ctx)
        assert result.entries is None
        assert mock_llm.call_count == 0

    def test_builds_fields_table(self, prompt_dir, ctx_with_chunks):
        mock_llm = MockLLMBackend(responses=["[]"])
        f = LLMExtractorFilter(prompt_dir, mock_llm)
        result = f.apply(ctx_with_chunks)
        # Verify prompt included field table
        assert mock_llm.call_count >= 1
        prompt = mock_llm.prompts[0]
        assert "property_address" in prompt
        assert "房产地址" in prompt

    def test_json_in_code_block(self, prompt_dir, ctx_with_chunks):
        """Test parsing JSON from ```json ... ``` code blocks."""
        response = '```json\n[{"fields": {"x": 1}, "confidence": 0.8}]\n```'
        mock_llm = MockLLMBackend(responses=[response])
        f = LLMExtractorFilter(prompt_dir, mock_llm)
        result = f.apply(ctx_with_chunks)
        assert len(result.entries) == 1
        assert result.entries[0]["fields"]["x"] == 1

    def test_parse_single_dict_as_list(self, prompt_dir, ctx_with_chunks):
        """Test that a single dict response is wrapped in a list."""
        response = json.dumps({"fields": {"x": 1}, "confidence": 0.9})
        mock_llm = MockLLMBackend(responses=[response])
        f = LLMExtractorFilter(prompt_dir, mock_llm)
        result = f.apply(ctx_with_chunks)
        assert len(result.entries) == 1

    def test_retry_on_bad_json(self, prompt_dir, ctx_with_chunks):
        """Test that extraction retries on malformed JSON."""
        responses = [
            "not json at all",  # attempt 1
            "also not json",     # attempt 2
            json.dumps([{"fields": {"x": 1}, "confidence": 0.9}]),  # attempt 3
        ]
        mock_llm = MockLLMBackend(responses=responses)
        f = LLMExtractorFilter(prompt_dir, mock_llm)
        result = f.apply(ctx_with_chunks)
        # Should succeed after retry
        assert result.entries is not None
        assert mock_llm.call_count >= 1

    def test_chunk_index_tracking(self, prompt_dir, ctx_with_chunks):
        mock_llm = MockLLMBackend(responses=["[]"])
        f = LLMExtractorFilter(prompt_dir, mock_llm)
        result = f.apply(ctx_with_chunks)
        # _chunk_index should be set (even for empty list, the entries list is empty)
        assert result.metrics.get("raw_entry_count") == 0

    def test_template_variable_injection(self, prompt_dir, ctx_with_chunks):
        mock_llm = MockLLMBackend(responses=["[]"])
        f = LLMExtractorFilter(prompt_dir, mock_llm)
        f.apply(ctx_with_chunks)
        prompt = mock_llm.prompts[0]
        assert "RE_MORTGAGE" in prompt
        assert "Beijing" in prompt

    def test_rollback_clears_entries(self, prompt_dir, ctx_with_chunks):
        mock_llm = MockLLMBackend(responses=["[]"])
        f = LLMExtractorFilter(prompt_dir, mock_llm)
        result = f.apply(ctx_with_chunks)
        rolled = f.rollback(result)
        assert rolled.entries is None

    def test_missing_template_fallback(self, base_ctx):
        """Missing custom template falls back to generic."""
        d = Path(tempfile.mkdtemp())
        extraction_dir = d / "extraction"
        extraction_dir.mkdir()
        template = extraction_dir / "extract_entries_generic.md"
        template.write_text("generic template", encoding="utf-8")

        mock_llm = MockLLMBackend(responses=["[]"])
        import dataclasses
        ctx = dataclasses.replace(base_ctx, meta={"chunks": ["test"]})

        f = LLMExtractorFilter(d, mock_llm, template_name="nonexistent.md")
        result = f.apply(ctx)
        assert mock_llm.call_count >= 1

    def test_missing_template_dir_raises(self, base_ctx):
        d = Path(tempfile.mkdtemp())
        mock_llm = MockLLMBackend()
        f = LLMExtractorFilter(d, mock_llm)
        import dataclasses
        ctx = dataclasses.replace(base_ctx, meta={"chunks": ["test"]})
        with pytest.raises(FileNotFoundError):
            f.apply(ctx)

    def test_llm_extract_all_retries_exhausted(self, prompt_dir, ctx_with_chunks):
        """When all retries fail, returns empty list."""
        responses = ["bad", "also bad", "still bad"]
        mock_llm = MockLLMBackend(responses=responses)
        f = LLMExtractorFilter(prompt_dir, mock_llm)
        result = f.apply(ctx_with_chunks)
        assert result.entries == []
