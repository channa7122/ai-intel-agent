"""
Phase 1 lives here: the list of sources we pull from, and the fetch
functions for each one (RSS parsing, API calls).

This file will hold something like:

TECH_SOURCES = [
    {"name": "arxiv_cs_ai", "type": "rss", "url": "..."},
    {"name": "github_trending", "type": "api", "url": "..."},
]

WORLD_SOURCES = [
    {"name": "reuters_top", "type": "rss", "url": "..."},
]

def fetch_all(sources: list[dict]) -> list[dict]:
    ...  # returns raw items, not yet Story objects
"""
