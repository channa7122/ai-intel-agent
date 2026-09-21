"""
tests/test_storage.py
Phase 4 test script -- validates SQLite persistence and ChromaDB RAG vector search.

Usage:
    python -m tests.test_storage
"""

from groq import Groq
from config.settings import GROQ_API_KEY
from storage.schema import Story
from storage.db import save_story, save_stories, get_story, get_recent_stories, is_story_stored
from storage.vector_store import index_story, index_stories, search_similar
from ingestion.sources import TECH_SOURCES, WORLD_SOURCES, fetch_all
from ingestion.normalize import normalize_all
from enrichment.dedup import run_filter_pipeline
from enrichment.dev_impact import enrich_all


def test_sqlite_crud():
    print("=== TEST 1: SQLite Storage CRUD ===")
    sample = Story(
        id="sql_test_001",
        title="vLLM releases v0.6.0 with FlashAttention-3 support",
        url="https://github.com/vllm-project/vllm",
        source="github_releases",
        category="tech",
        published_at=None,
        raw_summary="Summary text here.",
        verified_facts=["vLLM 0.6.0 released", "FlashAttention-3 supported"],
        dev_impact_notes="- Faster inference.\n- FP8 cache support.",
        tldr="vLLM v0.6.0 is released with new attention backend.",
    )

    save_story(sample)
    assert is_story_stored("sql_test_001"), "Story should exist in SQLite"

    retrieved = get_story("sql_test_001")
    assert retrieved is not None, "Retrieved story should not be None"
    assert retrieved.title == sample.title
    assert retrieved.tldr == sample.tldr
    assert len(retrieved.verified_facts) == 2

    recent = get_recent_stories(limit=5)
    assert len(recent) >= 1
    print("  ✓ SQLite save, query, and recent retrieval verified.")


def test_vector_store():
    print("\n=== TEST 2: ChromaDB Vector Store & RAG Search ===")
    sample_a = Story(
        id="vec_test_001",
        title="Pruning LLMs Like a Physicist: Block Removal as an Ising Optimization Problem",
        url="https://huggingface.co/blog/pruning",
        source="huggingface_blog",
        category="tech",
        published_at=None,
        raw_summary="Pruning research paper framing block removal as an Ising solver.",
        tldr="Researchers use Ising physics solvers to prune redundant transformer blocks without retraining.",
        dev_impact_notes="- Cuts inference compute by 30-40%.\n- Works on frozen weights.",
        verified_facts=["Reduces FLOPs without retraining", "Uses Ising optimization"],
    )

    sample_b = Story(
        id="vec_test_002",
        title="UN reports humanitarian crisis as civilians cross Red Sea",
        url="https://bbc.com/world/crisis",
        source="bbc_world",
        category="world",
        published_at=None,
        raw_summary="Civilians flee conflict across the Red Sea into Djibouti.",
        tldr="Thousands flee conflict across the Red Sea into Djibouti as regional tensions escalate.",
        dev_impact_notes="- Strains regional resources.\n- Threatens Red Sea shipping.",
        verified_facts=["Civilians flee to Djibouti", "Shipping lane security concerns"],
    )

    index_stories([sample_a, sample_b])
    assert sample_a.embedding_id == "emb_vec_test_001"

    # Test Tech Query
    tech_results = search_similar("how to prune transformers and speed up inference", n_results=1)
    assert len(tech_results) > 0
    top_match = tech_results[0]
    print(f"  Query: 'how to prune transformers and speed up inference'")
    print(f"  Matched: [{top_match['category']}] {top_match['title']}")
    assert top_match["story_id"] == "vec_test_001", "Should match the pruning story"

    # Test World Query
    world_results = search_similar("Red Sea maritime crisis refugees", n_results=1)
    assert len(world_results) > 0
    top_world = world_results[0]
    print(f"  Query: 'Red Sea maritime crisis refugees'")
    print(f"  Matched: [{top_world['category']}] {top_world['title']}")
    assert top_world["story_id"] == "vec_test_002", "Should match the Red Sea story"

    print("  ✓ ChromaDB indexing and semantic search verified.")


def test_end_to_end_pipeline():
    print("\n=== TEST 3: End-to-End Persistence Pipeline ===")
    print("1. Fetching, Normalizing, Filtering, and Enriching 4 stories...")
    raw = fetch_all(TECH_SOURCES[:2] + WORLD_SOURCES[:1])
    stories = normalize_all(raw)
    curated = run_filter_pipeline(stories, target_tech_count=2, target_world_count=2)

    client = Groq(api_key=GROQ_API_KEY)
    enriched = enrich_all(curated, client=client)

    print("2. Storing in SQLite & Indexing into ChromaDB...")
    for s in enriched:
        index_story(s)
        save_story(s)

    print(f"  ✓ Successfully persisted {len(enriched)} stories to SQLite and ChromaDB.")

    print("3. Validating RAG semantic retrieval on freshly ingested data...")
    rag_matches = search_similar("artificial intelligence models and breakthroughs", n_results=2)
    for idx, match in enumerate(rag_matches, 1):
        print(f"  Result #{idx}: {match['title']} ({match['url']})")


if __name__ == "__main__":
    test_sqlite_crud()
    test_vector_store()
    test_end_to_end_pipeline()