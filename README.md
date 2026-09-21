# AI Intel Agent

An autonomous agent that ingests tech + world news, filters and deduplicates it,
enriches it with fact-checking and developer-impact analysis, and delivers it
through Discord (push + pull mode) and a web dashboard.

## Architecture (matches the diagram we built in Phase 0.5)

```
[Tech sources]  [World news sources]
        \            /
         v          v
     Filter & Deduplicator
              |
              v
   Enrichment (fact-check + dev impact, via Groq)
              |
              v
      Storage (SQLite + Chroma vector store)
             / \
            v   v
    Discord bot   Web dashboard
  (push + pull)   (browse/search)
```

## Folder map

| Folder | Responsibility | Phase built |
|---|---|---|
| `ingestion/` | Pulls raw items from RSS/APIs, normalizes them into a common schema | Phase 1-2 |
| `enrichment/` | Dedup scoring, fact-checking, developer impact analysis (LLM calls) | Phase 2-3 |
| `storage/` | SQLite models + Chroma vector store wrapper | Phase 4 |
| `discord_bot/` | Push mode (daily post) + Pull mode (mention/thread replies) | Phase 5 |
| `dashboard/` | Web UI to browse/search past digests | Phase 7 |
| `config/` | API keys, source lists, settings (never commit real keys) | All phases |
| `data/` | Local SQLite file + Chroma persistence directory (gitignored) | Phase 4+ |
| `tests/` | Tests per module as we build them | All phases |

## Status

Currently at: **Phase 0.5 complete (scaffold done)**. Next: Phase 1 (source mapping).

## Setup (once we start Phase 1)

```bash
python -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate
pip install -r requirements.txt
cp config/.env.example config/.env   # then fill in your GROQ_API_KEY
```
