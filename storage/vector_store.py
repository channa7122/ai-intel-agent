"""
storage/vector_store.py
ChromaDB vector store for RAG and semantic retrieval.
"""

from pathlib import Path
import chromadb
from chromadb.config import Settings as ChromaSettings
from storage.schema import Story

CHROMA_PATH = Path(__file__).resolve().parent.parent / "data" / "chroma"
COLLECTION_NAME = "news_stories"


def get_vector_collection():
    """Initializes and returns the persistent ChromaDB collection."""
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(CHROMA_PATH),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Enriched tech and world news stories"},
    )


def create_search_document(story: Story) -> str:
    """
    Creates a rich text document for embedding generation.
    Combines title, TL;DR, developer impact, and verified facts.
    """
    facts_str = "\n".join(story.verified_facts) if isinstance(story.verified_facts, list) else str(story.verified_facts)
    return (
        f"Title: {story.title}\n"
        f"Category: {story.category}\n"
        f"Source: {story.source}\n"
        f"TL;DR: {story.tldr}\n"
        f"Developer Impact: {story.dev_impact_notes}\n"
        f"Key Facts:\n{facts_str}"
    )


def index_story(story: Story) -> str:
    """
    Indexes a single story into ChromaDB and returns the embedding_id.
    """
    collection = get_vector_collection()
    doc_text = create_search_document(story)
    doc_id = f"emb_{story.id}"

    metadata = {
        "story_id": story.id,
        "title": story.title[:100],
        "category": story.category,
        "source": story.source,
        "url": story.url,
        "primary_source_url": story.primary_source_url or story.url,
    }

    collection.upsert(
        ids=[doc_id],
        documents=[doc_text],
        metadatas=[metadata],
    )

    story.embedding_id = doc_id
    return doc_id


def index_stories(stories: list[Story]) -> list[Story]:
    """Indexes a list of stories into ChromaDB and updates their embedding_id."""
    for s in stories:
        index_story(s)
    return stories


def search_similar(query_text: str, n_results: int = 3, category: str | None = None) -> list[dict]:
    """
    Performs semantic vector search across indexed stories.
    Returns matching story metadata and snippets.
    """
    collection = get_vector_collection()
    where_filter = {"category": category} if category else None

    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
        where=where_filter,
    )

    matches = []
    if results and results["ids"] and len(results["ids"][0]) > 0:
        for i in range(len(results["ids"][0])):
            matches.append({
                "embedding_id": results["ids"][0][i],
                "story_id": results["metadatas"][0][i]["story_id"],
                "title": results["metadatas"][0][i]["title"],
                "category": results["metadatas"][0][i]["category"],
                "source": results["metadatas"][0][i]["source"],
                "url": results["metadatas"][0][i]["url"],
                "primary_source_url": results["metadatas"][0][i]["primary_source_url"],
                "document": results["documents"][0][i],
                "distance": results["distances"][0][i] if "distances" in results and results["distances"] else None,
            })

    return matches