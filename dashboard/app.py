"""
dashboard/app.py
Flask Web Dashboard for the AI Intel Agent.

Usage:
    python -m dashboard.app
"""

from pathlib import Path
from flask import Flask, render_template, request
from storage.db import get_connection, get_story, row_to_story
from storage.vector_store import search_similar

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
app = Flask(__name__, template_folder=str(TEMPLATE_DIR))


def get_db_stats() -> dict:
    """Calculates story statistics directly from SQLite."""
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
        tech = conn.execute("SELECT COUNT(*) FROM stories WHERE category = 'tech'").fetchone()[0]
        world = conn.execute("SELECT COUNT(*) FROM stories WHERE category = 'world'").fetchone()[0]
    return {"total": total, "tech": tech, "world": world}


def fetch_stories_by_query(search_query: str, category_filter: str | None = None) -> list:
    """Performs semantic search via ChromaDB and resolves full Story objects from SQLite."""
    matches = search_similar(search_query, n_results=15, category=category_filter or None)
    stories = []
    for m in matches:
        story = get_story(m["story_id"])
        if story:
            stories.append(story)
    return stories


def fetch_recent_stories(category_filter: str | None = None, limit: int = 50) -> list:
    """Retrieves recent stories sorted by SQLite rowid descending."""
    with get_connection() as conn:
        if category_filter:
            cursor = conn.execute(
                "SELECT * FROM stories WHERE category = ? ORDER BY rowid DESC LIMIT ?",
                (category_filter, limit),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM stories ORDER BY rowid DESC LIMIT ?",
                (limit,),
            )
        return [row_to_story(r) for r in cursor.fetchall()]


@app.route("/", methods=["GET"])
def index():
    category_filter = request.args.get("cat", "").strip() or None
    search_query = request.args.get("q", "").strip() or None

    # 1. Fetch stats
    stats = get_db_stats()

    # 2. Retrieve stories (Semantic RAG search vs. Recent list)
    if search_query:
        stories = fetch_stories_by_query(search_query, category_filter=category_filter)
    else:
        stories = fetch_recent_stories(category_filter=category_filter, limit=50)

    return render_template(
        "index.html",
        stories=stories,
        stats=stats,
        current_cat=category_filter,
        search_query=search_query,
    )


if __name__ == "__main__":
    print("\n=======================================================")
    print("  AI INTEL DASHBOARD ONLINE")
    print("  Open your browser at: http://127.0.0.1:5000")
    print("=======================================================\n")
    app.run(host="127.0.0.1", port=5000, debug=True)