"""
The Story object — the single data structure that flows through the whole
pipeline: ingestion -> enrichment -> storage -> delivery.

Every module in this project reads or writes a Story. Defining it early
(even before ingestion logic exists) keeps every phase compatible with
every other phase.

We'll flesh this out with real fields in Phase 2, once we know exactly
what our sources give us and what our enrichment steps need to add.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Story:
    # --- Filled by ingestion (Phase 1-2) ---
    id: str                          # stable hash of url or title+source
    title: str
    url: str
    source: str                      # e.g. "arxiv", "github", "reuters"
    category: str                    # "tech" or "world"
    published_at: datetime
    raw_summary: str                 # original snippet/abstract from the source

    # --- Filled by Filter & Deduplicator (Phase 2) ---
    is_duplicate_of: Optional[str] = None   # id of the canonical story, if merged
    relevance_score: Optional[float] = None

    # --- Filled by Enrichment (Phase 3) ---
    verified_facts: list[str] = field(default_factory=list)
    primary_source_url: Optional[str] = None
    dev_impact_notes: Optional[str] = None   # breaking changes, benchmarks, licensing
    tldr: Optional[str] = None

    # --- Filled by Storage layer (Phase 4) ---
    embedding_id: Optional[str] = None       # pointer into the Chroma vector store

    # --- Filled by Delivery (Phase 5) ---
    posted_to_discord_at: Optional[datetime] = None
