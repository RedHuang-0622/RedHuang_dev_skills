"""Tests for f04_deduplicate: DeduplicateFilter."""

from __future__ import annotations

import copy

import pytest

from filters.f04_deduplicate import DeduplicateFilter
from filters.context import PipelineContext


class TestDeduplicateFilter:
    @pytest.fixture
    def sample_entries(self):
        return [
            {
                "fields": {"property_address": "北京朝阳路1号", "抵押金额": 5000000},
                "confidence": 0.95,
            },
            {
                "fields": {"property_address": "北京朝阳路1号", "抵押金额": 5000000},
                "confidence": 0.85,
            },
            {
                "fields": {"property_address": "上海浦东路2号", "抵押金额": 3000000},
                "confidence": 0.90,
            },
            {
                "fields": {"property_address": "广州天河路3号", "抵押金额": 8000000},
                "confidence": 0.60,  # Low confidence
            },
        ]

    def test_no_entries_skips(self, base_ctx):
        f = DeduplicateFilter()
        result = f.apply(base_ctx)
        assert result == base_ctx or result.entries == base_ctx.entries

    def test_exact_duplicates_removed(self, base_ctx, sample_entries):
        ctx = base_ctx.with_entries(copy.deepcopy(sample_entries))
        f = DeduplicateFilter()
        result = f.apply(ctx)
        # Entry 1 and 2 have same address → one is kept (the higher confidence 0.95)
        assert len(result.entries) < len(sample_entries)
        assert result.metrics["dedup_removed"] >= 1

    def test_low_confidence_flagged(self, base_ctx, sample_entries):
        ctx = base_ctx.with_entries(copy.deepcopy(sample_entries))
        f = DeduplicateFilter()
        result = f.apply(ctx)
        # Entry with confidence 0.60 < 0.70 should be flagged
        needs_review = [e for e in result.entries if e.get("needs_review")]
        assert len(needs_review) >= 1

    def test_higher_confidence_kept(self, base_ctx):
        """When duplicates found, the entry with higher confidence is kept."""
        entries = [
            {"fields": {"property_address": "Addr1"}, "confidence": 0.60},
            {"fields": {"property_address": "Addr1"}, "confidence": 0.95},
        ]
        ctx = base_ctx.with_entries(copy.deepcopy(entries))
        f = DeduplicateFilter()
        result = f.apply(ctx)
        assert len(result.entries) == 1
        assert result.entries[0]["confidence"] == 0.95

    def test_unique_entries_preserved(self, base_ctx):
        entries = [
            {"fields": {"property_address": "A"}, "confidence": 0.9},
            {"fields": {"property_address": "B"}, "confidence": 0.9},
            {"fields": {"property_address": "C"}, "confidence": 0.9},
        ]
        ctx = base_ctx.with_entries(copy.deepcopy(entries))
        f = DeduplicateFilter()
        result = f.apply(ctx)
        assert len(result.entries) == 3
        assert result.metrics.get("dedup_removed", 0) == 0

    def test_fingerprint_case_insensitive(self, base_ctx):
        """Address matching should be case-insensitive."""
        entries = [
            {"fields": {"property_address": "Beijing Road 1"}, "confidence": 0.9},
            {"fields": {"property_address": "beijing road 1"}, "confidence": 0.8},
        ]
        ctx = base_ctx.with_entries(copy.deepcopy(entries))
        f = DeduplicateFilter()
        result = f.apply(ctx)
        assert len(result.entries) == 1

    def test_rollback_clears_entries(self, base_ctx, sample_entries):
        ctx = base_ctx.with_entries(copy.deepcopy(sample_entries))
        f = DeduplicateFilter()
        result = f.apply(ctx)
        rolled = f.rollback(result)
        assert rolled.entries is None

    def test_filter_name(self):
        assert DeduplicateFilter().name == "deduplicate"

    def test_single_entry_no_crash(self, base_ctx):
        entries = [{"fields": {"property_address": "A"}, "confidence": 0.9}]
        ctx = base_ctx.with_entries(entries)
        f = DeduplicateFilter()
        result = f.apply(ctx)
        assert len(result.entries) == 1

    def test_custom_similarity_threshold(self, base_ctx):
        entries = [
            {"fields": {"property_address": "Addr"}, "confidence": 0.9},
            {"fields": {"property_address": "Addr"}, "confidence": 0.85},
        ]
        ctx = base_ctx.with_entries(entries)
        f = DeduplicateFilter(similarity_threshold=0.99)  # Very strict
        result = f.apply(ctx)
        # With very high threshold, exact fingerprint matches still work
        assert len(result.entries) == 1
