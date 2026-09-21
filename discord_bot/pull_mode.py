"""
discord_bot/pull_mode.py
Handles interactive user questions in Discord threads using ChromaDB RAG and Groq LLM.
"""

import discord
from groq import Groq
from config.settings import GROQ_API_KEY
from storage.vector_store import search_similar

RAG_SYSTEM_PROMPT = """You are the AI Intelligence Bot, an expert research assistant for software engineers and tech analysts.
The user is asking a question in a Discord thread about a recent news item.
You are provided with retrieved context from our verified intelligence database.

Rules:
1. Ground your answer strictly in the provided Context.
2. If the user asks for code, benchmarks, or architectural explanations, provide concise, high-value technical answers.
3. If the context does not contain enough info to answer fully, state what is known from the context and offer reasonable engineering context without fabricating facts.
4. Keep the response concise, formatted in clean Markdown suitable for a Discord message (bullet points, bold highlights, code blocks).
"""


def generate_rag_response(user_query: str, client: Groq, model: str = "openai/gpt-oss-120b") -> str:
    """
    Performs semantic search over ChromaDB and prompts Groq LLM with context.
    """
    # 1. Retrieve relevant story chunks from ChromaDB
    matches = search_similar(user_query, n_results=2)
    context_blocks = []
    for m in matches:
        context_blocks.append(
            f"--- Article Context ---\n"
            f"Title: {m['title']}\n"
            f"Category: {m['category']}\n"
            f"Source: {m['source']}\n"
            f"URL: {m['url']}\n"
            f"Details:\n{m['document']}\n"
        )
    context_text = "\n".join(context_blocks) if context_blocks else "No direct database match found."

    # 2. Build Groq payload
    user_prompt = (
        f"Retrieved Database Context:\n{context_text}\n\n"
        f"User Question: {user_query}"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": RAG_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content or "Could not generate a response."
    except Exception as e:
        return f"Error retrieving answer from research model: {e}"


async def handle_thread_reply(message: discord.Message, client: Groq):
    """
    Processes an incoming user message inside a thread or mention.
    """
    # Ignore messages sent by the bot itself
    if message.author.bot:
        return

    # Trigger typing indicator while Groq + ChromaDB generate the answer
    async with message.channel.typing():
        user_query = message.clean_content

        # Include thread title for additional context if in a thread
        if isinstance(message.channel, discord.Thread):
            user_query = f"[Topic: {message.channel.name}] {user_query}"

        answer = generate_rag_response(user_query, client=client)

        # Discord message limit safeguard (2000 chars)
        if len(answer) > 1950:
            answer = answer[:1950] + "\n\n*(Truncated due to Discord character limit)*"

        await message.reply(answer, mention_author=False)