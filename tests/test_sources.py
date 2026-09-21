"""
Phase 1 test script -- run this on your own machine (not in a sandbox)
to confirm every source is reachable and returning real items.

Usage:
    python -m tests.test_sources
"""

from ingestion.sources import TECH_SOURCES, WORLD_SOURCES, fetch_all


def preview(label: str, sources: list[dict]):
    print(f"\n=== {label} ===")
    items = fetch_all(sources)
    print(f"Total items: {len(items)}")
    for item in items[:5]:  # just show the first 5 per group
        print(f"- [{item['source']}] {item['title'][:80]}")
    if len(items) > 5:
        print(f"  ...and {len(items) - 5} more")


if __name__ == "__main__":
    preview("TECH SOURCES", TECH_SOURCES)
    preview("WORLD SOURCES", WORLD_SOURCES)
