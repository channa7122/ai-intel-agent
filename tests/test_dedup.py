"""
tests/test_dedup.py
Phase 2 test script -- validates normalization, filtering, scoring, and deduplication.

Usage:
    python -m tests.test_dedup
"""

from datetime import datetime, timedelta, timezone
from storage.schema import Story
from ingestion.normalize import normalize_all, parse_date
from ingestion.sources import TECH_SOURCES, WORLD_SOURCES, fetch_all
from enrichment.dedup import (
    filter_by_rules,
    calculate_relevance,
    are_similar,
    deduplicate,
    run_filter_pipeline,
)


def test_date_parser():
    print("Testing date parser...")
    # RFC 2822
    d1 = parse_date("Mon, 21 Sep 2026 12:00:00 +0000")
    assert d1 is not None and d1.year == 2026

    # ISO 8601 with Z
    d2 = parse_date("2026-09-21T12:00:00Z")
    assert d2 is not None and d2.tzinfo == timezone.utc

    # Invalid
    assert parse_date("not a date") is None
    print("  ✓ Date parser works")


def test_synthetic_dedup_and_filter():
    print("Testing synthetic filter and dedup...")
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(hours=48)
    recent_time = now - timedelta(hours=2)

    raw_items = [
        # 1. Valid recent tech release
        {
            "source": "openai_blog",
            "title": "OpenAI announces GPT-5 model launch with reasoning benchmarks",
            "url": "https://openai.com/gpt-5",
            "published": recent_time.isoformat(),
            "summary": "Full release weights and benchmark data available.",
        },
        # 2. Duplicate of #1 from Hacker News
        {
            "source": "hackernews_ai",
            "title": "OpenAI announces GPT-5 model launch with reasoning benchmarks!",
            "url": "https://news.ycombinator.com/item?id=9999",
            "published": recent_time.isoformat(),
            "summary": "",
        },
        # 3. Outdated article (> 24 hours old)
        {
            "source": "huggingface_blog",
            "title": "Old Transformer architecture tutorial",
            "url": "https://huggingface.co/blog/old",
            "published": old_time.isoformat(),
            "summary": "Outdated content.",
        },
        # 4. Invalid item (empty title)
        {
            "source": "arxiv_cs_ai",
            "title": "",
            "url": "https://arxiv.org/abs/123",
            "published": recent_time.isoformat(),
            "summary": "No title.",
        },
    ]

    stories = normalize_all(raw_items)
    assert len(stories) == 3, f"Expected 3 valid normalized stories, got {len(stories)}"

    # Filter by recency
    recent_stories = filter_by_rules(stories, max_age_hours=24, reference_time=now)
    assert len(recent_stories) == 2, f"Expected 2 recent stories, got {len(recent_stories)}"

    # Score
    for s in recent_stories:
        s.relevance_score = calculate_relevance(s)
        assert 0.0 <= s.relevance_score <= 1.0

    # Deduplicate
    unique = deduplicate(recent_stories)
    assert len(unique) == 1, f"Expected 1 unique story after dedup, got {len(unique)}"
    assert unique[0].source == "openai_blog"  # Higher weight source should win
    print("  ✓ Synthetic filter and dedup passed")


def test_live_pipeline():
    print("\n=== LIVE PIPELINE TEST ===")
    print("1. Fetching raw items...")
    raw_tech = fetch_all(TECH_SOURCES)
    raw_world = fetch_all(WORLD_SOURCES)
    total_raw = len(raw_tech) + len(raw_world)
    print(f"   Fetched {total_raw} raw items ({len(raw_tech)} tech, {len(raw_world)} world)")

    print("2. Normalizing...")
    all_stories = normalize_all(raw_tech + raw_world)
    print(f"   Normalized into {len(all_stories)} Story objects")

    print("3. Filtering, scoring, and deduplicating...")
    curated = run_filter_pipeline(
        all_stories,
        max_age_hours=24,
        min_tech_score=0.45,
        min_world_score=0.45,
        target_tech_count=10,
        target_world_count=5,
    )

    tech_curated = [s for s in curated if s.category == "tech"]
    world_curated = [s for s in curated if s.category == "world"]

    print(f"\nFinal Curated Count: {len(curated)} items")
    print(f"  • Tech: {len(tech_curated)}")
    print(f"  • World: {len(world_curated)}")

    print("\n--- Curated Tech Stories ---")
    for s in tech_curated:
        print(f"[{s.relevance_score:.2f}] [{s.source}] {s.title[:75]}")

    print("\n--- Curated World Stories ---")
    for s in world_curated:
        print(f"[{s.relevance_score:.2f}] [{s.source}] {s.title[:75]}")


if __name__ == "__main__":
    test_date_parser()
    test_synthetic_dedup_and_filter()
    test_live_pipeline()