"""
enrichment/dedup.py
Filtering, scoring, and deduplication of stories.
"""

from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
import re
from storage.schema import Story

# Source quality/priority weights
SOURCE_WEIGHTS = {
    "openai_blog": 1.0,
    "huggingface_blog": 1.0,
    "github_releases": 0.95,
    "arxiv_cs_ai": 0.85,
    "arxiv_cs_cl": 0.85,
    "arxiv_cs_lg": 0.85,
    "hackernews_ai": 0.80,
    "reuters_world": 0.90,
    "bbc_world": 0.90,
}

# High-signal keywords that boost relevance
TECH_BOOST_KEYWORDS = [
    "release", "launch", "weights", "benchmark", "open-source",
    "breakthrough", "architecture", "llm", "vulnerability",
    "agent", "transformer", "fine-tuning", "inference", "quantization",
]

WORLD_BOOST_KEYWORDS = [
    "summit", "election", "treaty", "sanctions", "crisis",
    "war", "accord", "economy", "trade", "climate", "un",
]


def filter_by_rules(
    stories: list[Story],
    max_age_hours: int = 24,
    reference_time: datetime | None = None,
) -> list[Story]:
    """
    Drops stories with empty titles/URLs and stories published older than max_age_hours.
    Stories without a published date are kept by default.
    """
    now = reference_time or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)
    filtered = []

    for story in stories:
        if not story.title.strip() or not story.url.strip():
            continue
        if story.published_at and story.published_at < cutoff:
            continue
        filtered.append(story)

    return filtered


def calculate_relevance(story: Story) -> float:
    """
    Calculates a relevance score from 0.0 to 1.0.
    Combines source weight, keyword density, and summary completeness.
    """
    base_score = SOURCE_WEIGHTS.get(story.source, 0.6)
    text_content = f"{story.title} {story.raw_summary}".lower()

    # Keyword match boost
    keywords = TECH_BOOST_KEYWORDS if story.category == "tech" else WORLD_BOOST_KEYWORDS
    matched_count = sum(1 for kw in keywords if re.search(r"\b" + re.escape(kw) + r"\b", text_content))
    keyword_boost = min(0.30, matched_count * 0.06)

    # Content length bonus (having some summary details helps)
    content_bonus = 0.05 if len(story.raw_summary) > 60 else 0.0

    final_score = min(1.0, round(base_score * 0.65 + keyword_boost + content_bonus, 3))
    return final_score


def score_and_filter_relevance(stories: list[Story], min_score: float = 0.50) -> list[Story]:
    """Assigns relevance scores and filters out items below min_score."""
    passed = []
    for story in stories:
        story.relevance_score = calculate_relevance(story)
        if story.relevance_score >= min_score:
            passed.append(story)

    # Sort descending by relevance
    passed.sort(key=lambda s: s.relevance_score, reverse=True)
    return passed


def are_similar(title_a: str, title_b: str, threshold: float = 0.70) -> bool:
    """Checks if two titles refer to the same event using SequenceMatcher."""
    # Normalize strings: lowercase and remove special characters
    clean_a = re.sub(r"[^\w\s]", "", title_a.lower()).strip()
    clean_b = re.sub(r"[^\w\s]", "", title_b.lower()).strip()
    return SequenceMatcher(None, clean_a, clean_b).ratio() >= threshold


def deduplicate(stories: list[Story], similarity_threshold: float = 0.70) -> list[Story]:
    """
    Groups near-duplicate stories, keeping the one with higher relevance
    and marking duplicates with `is_duplicate_of`.
    """
    canonical_stories: list[Story] = []
    all_processed: list[Story] = []

    # Sort so highest quality stories are checked first
    sorted_stories = sorted(stories, key=lambda s: s.relevance_score, reverse=True)

    for story in sorted_stories:
        matched_canonical = None
        for canonical in canonical_stories:
            if canonical.category == story.category and are_similar(
                canonical.title, story.title, similarity_threshold
            ):
                matched_canonical = canonical
                break

        if matched_canonical:
            story.is_duplicate_of = matched_canonical.id
            all_processed.append(story)
        else:
            canonical_stories.append(story)
            all_processed.append(story)

    # Return only unique canonical stories
    return canonical_stories


def run_filter_pipeline(
    raw_stories: list[Story],
    max_age_hours: int = 24,
    min_tech_score: float = 0.50,
    min_world_score: float = 0.50,
    target_tech_count: int = 10,
    target_world_count: int = 5,
) -> list[Story]:
    """
    End-to-end Phase 2 filter:
    1. Recency and validity check
    2. Category split & relevance scoring
    3. Deduplication
    4. Curation down to target quota
    """
    valid = filter_by_rules(raw_stories, max_age_hours=max_age_hours)

    tech = [s for s in valid if s.category == "tech"]
    world = [s for s in valid if s.category == "world"]

    tech_scored = score_and_filter_relevance(tech, min_score=min_tech_score)
    world_scored = score_and_filter_relevance(world, min_score=min_world_score)

    tech_deduped = deduplicate(tech_scored)[:target_tech_count]
    world_deduped = deduplicate(world_scored)[:target_world_count]

    return tech_deduped + world_deduped