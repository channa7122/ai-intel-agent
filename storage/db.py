"""
storage/db.py
SQLite persistence layer for Story objects.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from storage.schema import Story

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"


def get_connection() -> sqlite3.Connection:
    """Returns a connection to the SQLite database with row factory enabled."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Creates the stories table if it does not already exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stories (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                source TEXT NOT NULL,
                category TEXT NOT NULL,
                published_at TEXT,
                raw_summary TEXT,
                is_duplicate_of TEXT,
                relevance_score REAL,
                verified_facts TEXT,
                primary_source_url TEXT,
                dev_impact_notes TEXT,
                tldr TEXT,
                embedding_id TEXT,
                posted_to_discord_at TEXT
            )
        """)
        conn.commit()


def story_to_row(story: Story) -> tuple:
    """Converts a Story object into a database row tuple."""
    pub_at_str = story.published_at.isoformat() if isinstance(story.published_at, datetime) else story.published_at
    posted_at_str = story.posted_to_discord_at.isoformat() if isinstance(story.posted_to_discord_at, datetime) else story.posted_to_discord_at

    return (
        story.id,
        story.title,
        story.url,
        story.source,
        story.category,
        pub_at_str,
        story.raw_summary,
        story.is_duplicate_of,
        story.relevance_score,
        json.dumps(story.verified_facts if isinstance(story.verified_facts, list) else []),
        story.primary_source_url,
        story.dev_impact_notes,
        story.tldr,
        story.embedding_id,
        posted_at_str,
    )


def row_to_story(row: sqlite3.Row) -> Story:
    """Reconstructs a Story object from an SQLite Row."""
    pub_at = None
    if row["published_at"]:
        try:
            pub_at = datetime.fromisoformat(row["published_at"])
        except ValueError:
            pub_at = None

    posted_at = None
    if row["posted_to_discord_at"]:
        try:
            posted_at = datetime.fromisoformat(row["posted_to_discord_at"])
        except ValueError:
            posted_at = None

    verified_facts = []
    if row["verified_facts"]:
        try:
            verified_facts = json.loads(row["verified_facts"])
        except json.JSONDecodeError:
            verified_facts = [row["verified_facts"]]

    return Story(
        id=row["id"],
        title=row["title"],
        url=row["url"],
        source=row["source"],
        category=row["category"],
        published_at=pub_at,
        raw_summary=row["raw_summary"] or "",
        is_duplicate_of=row["is_duplicate_of"],
        relevance_score=float(row["relevance_score"] or 0.0),
        verified_facts=verified_facts,
        primary_source_url=row["primary_source_url"],
        dev_impact_notes=row["dev_impact_notes"] or "",
        tldr=row["tldr"] or "",
        embedding_id=row["embedding_id"],
        posted_to_discord_at=posted_at,
    )


def save_story(story: Story):
    """Inserts or updates a single story in SQLite."""
    init_db()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO stories (
                id, title, url, source, category, published_at, raw_summary,
                is_duplicate_of, relevance_score, verified_facts, primary_source_url,
                dev_impact_notes, tldr, embedding_id, posted_to_discord_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                is_duplicate_of=excluded.is_duplicate_of,
                relevance_score=excluded.relevance_score,
                verified_facts=excluded.verified_facts,
                primary_source_url=excluded.primary_source_url,
                dev_impact_notes=excluded.dev_impact_notes,
                tldr=excluded.tldr,
                embedding_id=excluded.embedding_id,
                posted_to_discord_at=excluded.posted_to_discord_at
        """, story_to_row(story))
        conn.commit()


def save_stories(stories: list[Story]):
    """Batch saves multiple stories."""
    for s in stories:
        save_story(s)


def get_story(story_id: str) -> Story | None:
    """Fetches a single story by ID."""
    init_db()
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM stories WHERE id = ?", (story_id,))
        row = cursor.fetchone()
        return row_to_story(row) if row else None


def is_story_stored(story_id: str) -> bool:
    """Checks if a story ID already exists in the database."""
    init_db()
    with get_connection() as conn:
        cursor = conn.execute("SELECT 1 FROM stories WHERE id = ?", (story_id,))
        return cursor.fetchone() is not None


def get_recent_stories(limit: int = 20, category: str | None = None) -> list[Story]:
    """Retrieves recent stories sorted by published date descending."""
    init_db()
    with get_connection() as conn:
        if category:
            cursor = conn.execute(
                "SELECT * FROM stories WHERE category = ? ORDER BY rowid DESC LIMIT ?",
                (category, limit),
            )
        else:
            cursor = conn.execute("SELECT * FROM stories ORDER BY rowid DESC LIMIT ?", (limit,))
        return [row_to_story(r) for r in cursor.fetchall()]