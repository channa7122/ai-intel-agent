"""
ingestion/normalize.py
Converts raw item dicts from fetchers into validated Story dataclass objects.
"""

import email.utils
import hashlib
import html
import re
from datetime import datetime, timezone
from storage.schema import Story

TECH_SOURCE_NAMES = {
    "arxiv_cs_ai",
    "arxiv_cs_cl",
    "arxiv_cs_lg",
    "openai_blog",
    "huggingface_blog",
    "hackernews_ai",
    "github_releases",
}


def parse_date(date_str: str | None) -> datetime | None:
    """
    Parses various date strings (RFC 2822, ISO 8601, etc.) into a UTC datetime.
    Returns None if parsing fails.
    """
    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.strip()
    if not date_str:
        return None

    # 1. Try RFC 2822 / 822 (common in RSS feeds)
    try:
        parsed_tuple = email.utils.parsedate_to_datetime(date_str)
        if parsed_tuple:
            return parsed_tuple.astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass

    # 2. Try ISO 8601 formats (Hacker News, GitHub API)
    cleaned_iso = date_str.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned_iso)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass

    # 3. Fallback standard formats
    common_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%a, %d %b %Y %H:%M:%S",
    ]
    for fmt in common_formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def clean_text(raw_text: str | None) -> str:
    """Unescapes HTML entities and strips HTML tags/extra whitespace."""
    if not raw_text:
        return ""
    unescaped = html.unescape(raw_text)
    no_html = re.sub(r"<[^>]+>", " ", unescaped)
    return re.sub(r"\s+", " ", no_html).strip()


def generate_story_id(url: str, title: str) -> str:
    """Generates a stable, deterministic 16-character MD5 hash."""
    seed = (url or "").strip().lower() or (title or "").strip().lower()
    return hashlib.md5(seed.encode("utf-8")).hexdigest()[:16]


def normalize_item(item: dict) -> Story | None:
    """
    Converts a single raw dict into a Story object.
    Returns None if title is missing.
    """
    title = clean_text(item.get("title", ""))
    url = (item.get("url") or "").strip()
    if not title:
        return None

    source = item.get("source", "unknown")
    category = "tech" if source in TECH_SOURCE_NAMES else "world"
    published_at = parse_date(item.get("published"))
    raw_summary = clean_text(item.get("summary", ""))

    story_id = generate_story_id(url, title)

    return Story(
        id=story_id,
        title=title,
        url=url,
        source=source,
        category=category,
        published_at=published_at,
        raw_summary=raw_summary,
    )


def normalize_all(raw_items: list[dict]) -> list[Story]:
    """Converts a list of raw item dicts into validated Story objects."""
    stories: list[Story] = []
    seen_ids: set[str] = set()

    for item in raw_items:
        story = normalize_item(item)
        if story and story.id not in seen_ids:
            seen_ids.add(story.id)
            stories.append(story)

    return stories