"""
discord_bot/push_mode.py
Formats enriched stories into Discord Embeds and broadcasts them to the target channel.
"""

from datetime import datetime, timezone
import discord
from storage.schema import Story
from storage.db import save_story

# Embed Color Palette
TECH_COLOR = 0x5865F2   # Discord Blurple
WORLD_COLOR = 0x2ECC71  # Emerald Green


def create_story_embed(story: Story) -> discord.Embed:
    """Constructs a structured Discord Rich Embed for an enriched story."""
    is_tech = story.category == "tech"
    color = TECH_COLOR if is_tech else WORLD_COLOR
    category_badge = "🤖 TECH & AI INTELLIGENCE" if is_tech else "🌍 GLOBAL BRIEFING"

    embed = discord.Embed(
        title=story.title[:256],
        url=story.url,
        color=color,
    )
    embed.set_author(name=f"{category_badge} • [{story.source}]")

    # 1. TL;DR
    embed.add_field(
        name="📌 Summary (TL;DR)",
        value=story.tldr or story.raw_summary[:250] or "No summary available.",
        inline=False,
    )

    # 2. Developer Impact or Geopolitical Significance
    impact_title = "⚡ Developer & Architecture Impact" if is_tech else "🌐 Global Significance"
    embed.add_field(
        name=impact_title,
        value=story.dev_impact_notes or "- No immediate breaking impact reported.",
        inline=False,
    )

    # 3. Verified Facts (if available)
    if story.verified_facts and isinstance(story.verified_facts, list):
        facts_text = "\n".join(f"• {f}" for f in story.verified_facts[:3])
        embed.add_field(name="🔍 Verified Key Facts", value=facts_text, inline=False)

    # 4. Primary Source link footer
    footer_text = f"Story ID: {story.id}"
    if story.primary_source_url and story.primary_source_url != story.url:
        footer_text += f" • Primary: {story.primary_source_url[:40]}"
    embed.set_footer(text=footer_text)

    return embed


async def publish_stories(
    channel: discord.TextChannel,
    stories: list[Story],
    create_threads: bool = True,
) -> int:
    """
    Broadcasts each story to the channel, creates a discussion thread,
    and updates the database timestamp. Returns count of published stories.
    """
    published_count = 0

    for story in stories:
        try:
            embed = create_story_embed(story)
            message = await channel.send(embed=embed)

            # Auto-create thread for interactive Q&A
            if create_threads:
                thread_title = f"Discussion: {story.title[:80]}"
                await message.create_thread(name=thread_title)

            # Mark as posted
            story.posted_to_discord_at = datetime.now(timezone.utc)
            save_story(story)
            published_count += 1

        except Exception as e:
            print(f"[error] Failed to post story '{story.title[:30]}' to Discord: {e}")

    return published_count