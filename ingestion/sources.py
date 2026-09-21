"""
Phase 1: the list of sources we pull from, and the fetch functions
for each one. Every source is either:
  - "rss"  -> parsed with feedparser (arXiv, blogs, news outlets)
  - "api"  -> a plain HTTP GET returning JSON (GitHub, Hacker News)

Nothing here does filtering, dedup, or scoring yet — that's Phase 2.
This file's only job: reliably pull raw items and hand back a plain
list of dicts (title, url, published, summary, source name).
"""

import feedparser
import requests
from config.settings import GITHUB_TOKEN


# ---------------------------------------------------------------------
# TECH SOURCES
# ---------------------------------------------------------------------

TECH_SOURCES = [
    # arXiv: new research papers, split by category so we can tag them.
    # cs.AI = general AI, cs.CL = language/NLP, cs.LG = machine learning
    {"name": "arxiv_cs_ai", "type": "rss", "url": "http://export.arxiv.org/rss/cs.AI"},
    {"name": "arxiv_cs_cl", "type": "rss", "url": "http://export.arxiv.org/rss/cs.CL"},
    {"name": "arxiv_cs_lg", "type": "rss", "url": "http://export.arxiv.org/rss/cs.LG"},

    # Official lab blogs -- where model releases and policy changes are announced first
    {"name": "openai_blog",      "type": "rss", "url": "https://openai.com/news/rss.xml"},
    {"name": "huggingface_blog", "type": "rss", "url": "https://huggingface.co/blog/feed.xml"},

    # Hacker News: community signal on what's actually being discussed.
    # Uses the free Algolia HN Search API, no key required.
    {"name": "hackernews_ai", "type": "hn_api",
     "url": "https://hn.algolia.com/api/v1/search?query=AI&tags=story&hitsPerPage=20"},

    # GitHub: release activity for the repos that matter most.
    # Token in config/.env raises rate limit from 60/hr to 5000/hr.
    {"name": "github_releases", "type": "github_releases",
     "repos": ["huggingface/transformers", "pytorch/pytorch", "vllm-project/vllm"]},
]


# ---------------------------------------------------------------------
# WORLD NEWS SOURCES
# ---------------------------------------------------------------------

WORLD_SOURCES = [
    # BBC World: fast, reliable, free RSS -- no key needed
    {"name": "bbc_world", "type": "rss",
     "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},

    # Reuters world news RSS -- clean, curated, no key
    {"name": "reuters_world", "type": "rss",
     "url": "https://www.reutersagency.com/feed/?best-topics=world"},
]


# ---------------------------------------------------------------------
# FETCH FUNCTIONS -- one per source "type"
# ---------------------------------------------------------------------

def fetch_rss(source: dict) -> list[dict]:
    """Parses any RSS/Atom feed into a plain list of item dicts."""
    parsed = feedparser.parse(source["url"])
    items = []
    for entry in parsed.entries:
        items.append({
            "source":    source["name"],
            "title":     entry.get("title", ""),
            "url":       entry.get("link", ""),
            "published": entry.get("published", ""),
            "summary":   entry.get("summary", ""),
        })
    return items


def fetch_hn(source: dict) -> list[dict]:
    """Fetches Hacker News stories via the Algolia search API."""
    resp = requests.get(source["url"], timeout=10)
    resp.raise_for_status()
    items = []
    for hit in resp.json().get("hits", []):
        items.append({
            "source":    source["name"],
            "title":     hit.get("title", ""),
            "url":       hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
            "published": hit.get("created_at", ""),
            "summary":   "",
        })
    return items


def fetch_github_releases(source: dict) -> list[dict]:
    """Fetches the latest release for each repo in source['repos']."""
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
    items = []
    for repo in source["repos"]:
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            continue
        data = resp.json()
        items.append({
            "source":    source["name"],
            "title":     f"{repo}: {data.get('name') or data.get('tag_name')}",
            "url":       data.get("html_url", ""),
            "published": data.get("published_at", ""),
            "summary":   (data.get("body") or "")[:500],
        })
    return items


FETCHERS = {
    "rss":             fetch_rss,
    "hn_api":          fetch_hn,
    "github_releases": fetch_github_releases,
}


def fetch_all(sources: list[dict]) -> list[dict]:
    """Runs the right fetcher for each source, skips ones that fail
    (a single broken feed should never crash the whole pipeline),
    and returns one flat list of raw items."""
    all_items = []
    for source in sources:
        fetcher = FETCHERS[source["type"]]
        try:
            all_items.extend(fetcher(source))
        except Exception as e:
            print(f"[warn] {source['name']} failed: {e}")
    return all_items