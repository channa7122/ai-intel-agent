"""
tests/test_enrichment.py
Phase 3 test script -- validates Groq LLM enrichment (Fact-checking, TL;DR, Developer Impact).

Usage:
    python -m tests.test_enrichment
"""

from groq import Groq
from config.settings import GROQ_API_KEY
from storage.schema import Story
from ingestion.sources import TECH_SOURCES, WORLD_SOURCES, fetch_all
from ingestion.normalize import normalize_all
from enrichment.dedup import run_filter_pipeline
from enrichment.dev_impact import enrich_story, enrich_all


def test_single_story_enrichment(client: Groq):
    print("=== TEST 1: Single Story Enrichment ===")
    sample_story = Story(
        id="sample_test_01",
        title="vLLM releases v0.6.0 with FlashAttention-3 support and multi-GPU chunked prefill",
        url="https://github.com/vllm-project/vllm/releases/tag/v0.6.0",
        source="github_releases",
        category="tech",
        published_at=None,
        raw_summary="Major release adding FP8 KV cache support, FlashAttention-3 integration, and chunked prefill improvements for LLaMA 3.1.",
    )

    enriched = enrich_story(sample_story, client=client)

    print("\n--- Enriched Output ---")
    print(f"Title: {enriched.title}")
    print(f"Primary Source URL: {enriched.primary_source_url}")
    print(f"\nTL;DR:\n{enriched.tldr}")
    print(f"\nDeveloper Impact Notes:\n{enriched.dev_impact_notes}")
    print(f"\nVerified Facts:\n{enriched.verified_facts}")

    assert enriched.tldr != "", "TL;DR must not be empty"
    assert enriched.dev_impact_notes != "", "dev_impact_notes must not be empty"
    assert len(enriched.verified_facts) > 0, "verified_facts must not be empty"
    print("\n✓ Single story enrichment passed.")


def test_live_enrichment_pipeline(client: Groq):
    print("\n=== TEST 2: Live Pipeline Integration ===")
    print("1. Fetching raw items...")
    raw_tech = fetch_all(TECH_SOURCES)
    raw_world = fetch_all(WORLD_SOURCES)

    print("2. Normalizing & Filtering...")
    all_stories = normalize_all(raw_tech + raw_world)
    curated = run_filter_pipeline(
        all_stories,
        max_age_hours=24,
        min_tech_score=0.45,
        min_world_score=0.45,
        target_tech_count=3,   # Keep small for quick test run
        target_world_count=2,
    )
    print(f"   Curated {len(curated)} stories for enrichment.")

    print("3. Running Groq enrichment on curated stories...")
    enriched_stories = enrich_all(curated, client=client)

    print("\n=== ENRICHMENT SUMMARY ===")
    for s in enriched_stories:
        print(f"\n[{s.category.upper()}] [{s.source}] {s.title}")
        print(f"TL;DR: {s.tldr}")
        print(f"Dev Impact:\n{s.dev_impact_notes}")
        print("-" * 60)

    print("\n✓ Live pipeline enrichment test complete.")


if __name__ == "__main__":
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set. Please add it to your config/.env file.")

    client = Groq(api_key=GROQ_API_KEY)
    test_single_story_enrichment(client)
    test_live_enrichment_pipeline(client)