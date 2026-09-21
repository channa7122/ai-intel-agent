"""
ingestion/sources.py
Phase 1: Source definitions and fetch functions.
"""

import feedparser
import requests
from config.settings import GITHUB_TOKEN

# ---------------------------------------------------------------------
# TECH SOURCES
# ---------------------------------------------------------------------

TECH_SOURCES = [
    {"name": "arxiv_cs_ai", "type": "rss", "url": "http://export.arxiv.org/rss/cs.AI"},
    {"name": "arxiv_cs_cl", "type": "rss", "url": "http://export.arxiv.org/rss/cs.CL"},
    {"name": "arxiv_cs_lg", "type": "rss", "url": "http://export.arxiv.org/rss/cs.LG"},
    {"name": "openai_blog", "type": "rss", "url": "https://openai.com/news/rss.xml"},
    {"name": "huggingface_blog", "type": "rss", "url": "https://huggingface.co/blog/feed.xml"},
    {
        "name": "hackernews_ai",
        "type": "hn_api",
        "url": "https://hn.algolia.com/api/v1/search?query=AI&tags=story&hitsPerPage=20",
    },
    {
        "name": "github_releases",
        "type": "github_releases",
        "repos": ["huggingface/transformers", "pytorch/pytorch", "vllm-project/vllm"],
    },
]

# ---------------------------------------------------------------------
# WORLD NEWS SOURCES
# ---------------------------------------------------------------------

WORLD_SOURCES = [
    {"name": "bbc_world", "type": "rss", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "reuters_world", "type": "rss", "url": "https://www.reutersagency.com/feed/?best-topics=world"},
]

# ---------------------------------------------------------------------
# FETCH FUNCTIONS
# ---------------------------------------------------------------------

def fetch_rss(source: dict) -> list[dict]:
    """Parses any RSS/Atom feed into a plain list of item dicts."""
    parsed = feedparser.parse(source["url"])
    items = []
    for entry in parsed.entries:
        items.append({
            "source": source["name"],
            "title": entry.get("title", ""),
            "url": entry.get("link", ""),
            "published": entry.get("published", ""),
            "summary": entry.get("summary", ""),
        })
    return items


def fetch_hn(source: dict) -> list[dict]:
    """Fetches Hacker News stories via the Algolia search API."""
    headers = {"User-Agent": "ai-intel-agent/1.0"}
    resp = requests.get(source["url"], headers=headers, timeout=10)
    resp.raise_for_status()
    items = []
    for hit in resp.json().get("hits", []):
        items.append({
            "source": source["name"],
            "title": hit.get("title", ""),
            "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
            "published": hit.get("created_at", ""),
            "summary": "",
        })
    return items


def fetch_github_releases(source: dict) -> list[dict]:
    """Fetches the latest release for each repo in source['repos']."""
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
    headers["User-Agent"] = "ai-intel-agent/1.0"
    items = []
    for repo in source["repos"]:
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            continue
        data = resp.json()
        items.append({
            "source": source["name"],
            "title": f"{repo}: {data.get('name') or data.get('tag_name')}",
            "url": data.get("html_url", ""),
            "published": data.get("published_at", ""),
            "summary": (data.get("body") or "")[:500],
        })
    return items


FETCHERS = {
    "rss": fetch_rss,
    "hn_api": fetch_hn,
    "github_releases": fetch_github_releases,
}


def fetch_all(sources: list[dict]) -> list[dict]:
    """Runs the right fetcher for each source, skips failing ones."""
    all_items = []
    for source in sources:
        fetcher = FETCHERS[source["type"]]
        try:
            all_items.extend(fetcher(source))
        except Exception as e:
            print(f"[warn] {source['name']} failed: {e}")
    return all_items