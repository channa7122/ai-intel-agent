"""
main.py
AI Intel Agent -- Full Orchestration Pipeline & Discord Service.

Usage:
    python main.py             # Runs scheduled loop + Discord listener
    python main.py --run-now   # Runs digest immediately on startup, then listens
"""

import asyncio
import sys
from datetime import datetime, time, timezone
import discord
from discord.ext import tasks
from groq import Groq

from config.settings import (
    DISCORD_BOT_TOKEN,
    DISCORD_CHANNEL_ID,
    GROQ_API_KEY,
)
from storage.db import init_db, is_story_stored, save_stories
from storage.vector_store import index_stories
from ingestion.sources import TECH_SOURCES, WORLD_SOURCES, fetch_all
from ingestion.normalize import normalize_all
from enrichment.dedup import run_filter_pipeline
from enrichment.dev_impact import enrich_all
from discord_bot.push_mode import publish_stories
from discord_bot.pull_mode import handle_thread_reply

# Initialize Clients
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
groq_client = Groq(api_key=GROQ_API_KEY)

# Daily Schedule Time (07:00 UTC)
SCHEDULE_TIME = time(hour=7, minute=0, tzinfo=timezone.utc)
RUN_NOW_FLAG = "--run-now" in sys.argv


async def execute_daily_pipeline(channel: discord.TextChannel) -> int:
    """Runs the full autonomous data engineering & intelligence pipeline without blocking the event loop."""
    print(f"\n[{datetime.now(timezone.utc).isoformat()}] Starting Daily Intelligence Run...")

    # 1. Fetch raw items (offloaded to thread)
    print("1/6 Fetching from sources...")
    raw_tech = await asyncio.to_thread(fetch_all, TECH_SOURCES)
    raw_world = await asyncio.to_thread(fetch_all, WORLD_SOURCES)
    total_raw = len(raw_tech) + len(raw_world)
    print(f"    Fetched {total_raw} items ({len(raw_tech)} tech, {len(raw_world)} world).")

    # 2. Normalize (offloaded to thread)
    print("2/6 Normalizing into Story objects...")
    stories = await asyncio.to_thread(normalize_all, raw_tech + raw_world)

    # 3. Filter out previously processed items from SQLite
    new_stories = [s for s in stories if not is_story_stored(s.id)]
    print(f"    {len(new_stories)} new stories after historical duplicate check.")

    if not new_stories:
        print("    No new stories found today. Skipping enrichment.")
        return 0

    # 4. Filter, score, and deduplicate (offloaded to thread)
    print("3/6 Filtering and deduplicating...")
    curated = await asyncio.to_thread(
        run_filter_pipeline,
        new_stories,
        max_age_hours=24,
        min_tech_score=0.45,
        min_world_score=0.45,
        target_tech_count=6,
        target_world_count=4,
    )
    print(f"    Curated {len(curated)} high-signal stories.")

    if not curated:
        print("    No stories met the score threshold today.")
        return 0

    # 5. Groq LLM Enrichment (offloaded to thread)
    print("4/6 Running Groq LLM enrichment (Fact-checking, TL;DR, Dev Impact)...")
    enriched = await asyncio.to_thread(enrich_all, curated, client=groq_client)

    # 6. Index into ChromaDB & Save to SQLite (offloaded to thread)
    print("5/6 Persisting to ChromaDB vector store and SQLite...")
    await asyncio.to_thread(index_stories, enriched)
    await asyncio.to_thread(save_stories, enriched)

    # 7. Broadcast to Discord
    print(f"6/6 Broadcasting embeds to #{channel.name}...")
    published = await publish_stories(channel, enriched, create_threads=True)
    print(f"✓ Daily run complete! Published {published} stories to #{channel.name}.\n")
    return published


@tasks.loop(time=SCHEDULE_TIME)
async def scheduled_morning_brief():
    """Triggered automatically once every morning at 07:00 UTC."""
    channel = bot.get_channel(int(DISCORD_CHANNEL_ID))
    if channel:
        await execute_daily_pipeline(channel)


@bot.event
async def on_ready():
    init_db()
    print(f"\n=======================================================")
    print(f"  AI INTEL AGENT SERVICE ONLINE")
    print(f"  Connected as: {bot.user} (ID: {bot.user.id})")
    channel = bot.get_channel(int(DISCORD_CHANNEL_ID))
    if channel:
        print(f"  Target Channel: #{channel.name} ({channel.id})")
    print(f"  Scheduled Run Time: 07:00 UTC daily")
    print(f"=======================================================\n")

    if not scheduled_morning_brief.is_running():
        scheduled_morning_brief.start()

    if RUN_NOW_FLAG and channel:
        print("⚡ '--run-now' flag detected: Executing pipeline immediately...")
        await execute_daily_pipeline(channel)


@bot.event
async def on_message(message: discord.Message):
    """Listens for user questions in threads or mentions to run RAG."""
    if message.author.bot:
        return

    if isinstance(message.channel, discord.Thread):
        print(f"[chat] Query from {message.author.name} in thread '{message.channel.name}': {message.content}")
        await handle_thread_reply(message, client=groq_client)


def main():
    if not DISCORD_BOT_TOKEN or not DISCORD_CHANNEL_ID:
        raise ValueError("DISCORD_BOT_TOKEN or DISCORD_CHANNEL_ID is missing in config/.env")
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is missing in config/.env")

    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()