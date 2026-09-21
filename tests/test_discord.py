"""
tests/test_discord.py
Phase 5 test script -- validates Discord Push Mode (Embeds + Threads) and Pull Mode (Interactive RAG Q&A).

Usage:
    python -m tests.test_discord
"""

import discord
from groq import Groq
from config.settings import DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID, GROQ_API_KEY
from storage.schema import Story
from discord_bot.push_mode import publish_stories
from discord_bot.pull_mode import handle_thread_reply

# Setup Discord Client with required Intents
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
groq_client = Groq(api_key=GROQ_API_KEY)


@bot.event
async def on_ready():
    print(f"\n✓ Discord Bot connected as: {bot.user} (ID: {bot.user.id})")

    if not bot.guilds:
        print("\n[warning] The bot is NOT currently inside any Discord server!")
        print("Please invite the bot using this URL template in your browser:")
        print(f"https://discord.com/oauth2/authorize?client_id={bot.user.id}&permissions=397284558912&scope=bot\n")
        await bot.close()
        return

    channel = bot.get_channel(int(DISCORD_CHANNEL_ID))
    if not channel:
        print(f"\n[error] Could not find channel with ID {DISCORD_CHANNEL_ID}.")
        print("Here are the servers and text channels your bot can currently access:")
        for guild in bot.guilds:
            print(f"\n  Server: {guild.name} (ID: {guild.id})")
            for ch in guild.text_channels:
                print(f"    • #{ch.name} -> ID: {ch.id}")
        print("\nCopy the correct channel ID into config/.env and re-run.\n")
        await bot.close()
        return

    print(f"✓ Found target channel: #{channel.name}")

    # Prepare sample tech and world test stories
    test_stories = [
        Story(
            id="disc_test_001",
            title="vLLM v0.6.0 Released: FP8 KV-Cache and FlashAttention-3 Support",
            url="https://github.com/vllm-project/vllm/releases/tag/v0.6.0",
            source="github_releases",
            category="tech",
            published_at=None,
            raw_summary="vLLM 0.6.0 introduces major throughput gains.",
            tldr="vLLM released version 0.6.0 adding FP8 KV-cache support and FlashAttention-3 integration. It optimizes throughput and reduces memory for LLaMA 3.1.",
            dev_impact_notes="- Upgrades attention backend to FlashAttention-3.\n- Lowers VRAM footprint via FP8 quantization.\n- Requires CUDA 12+ updates.",
            verified_facts=["Added FP8 KV cache support", "Integrated FlashAttention-3", "Targeted for LLaMA 3.1"],
            primary_source_url="https://github.com/vllm-project/vllm",
        ),
        Story(
            id="disc_test_002",
            title="UN Holds Emergency Summit on Global AI Safety Frameworks",
            url="https://bbc.co.uk/news/world/ai-summit",
            source="bbc_world",
            category="world",
            published_at=None,
            raw_summary="Global leaders meet to discuss cross-border AI governance.",
            tldr="Delegates from 40 nations gathered in Geneva to draft baseline safety protocols for autonomous systems. The accord seeks to align cross-border standards on model audits.",
            dev_impact_notes="- May establish international compliance standards for tier-1 frontier models.\n- Potential export and auditing requirements for cross-border deployments.",
            verified_facts=["Summit held in Geneva", "40 nations participating"],
        )
    ]

    print("\n--- Testing Push Mode: Sending Embeds & Threads to Discord ---")
    count = await publish_stories(channel, test_stories, create_threads=True)
    print(f"✓ Successfully published {count} story embeds with threads to #{channel.name}!")
    print("\n--- Testing Pull Mode: Bot is listening for questions in threads! ---")
    print("👉 Go to your Discord channel, open one of the created threads, and type a question!")
    print("   Example: 'How does FlashAttention-3 help memory?' or 'Who attended the summit?'")
    print("   (Press CTRL+C in this terminal when finished to stop the test).\n")


@bot.event
async def on_message(message: discord.Message):
    """Listens for user replies in threads to trigger Pull Mode RAG."""
    if message.author.bot:
        return

    # If message is inside a thread, trigger RAG reply
    if isinstance(message.channel, discord.Thread):
        print(f"[received] Query in thread '{message.channel.name}': {message.content}")
        await handle_thread_reply(message, client=groq_client)


def main():
    if not DISCORD_BOT_TOKEN or not DISCORD_CHANNEL_ID:
        raise ValueError("DISCORD_BOT_TOKEN or DISCORD_CHANNEL_ID is missing in config/.env")

    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()