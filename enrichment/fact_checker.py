"""
enrichment/fact_checker.py
Extracts verified core facts and resolves primary sources using Groq LLM.
"""

import json
import re
from groq import Groq
from storage.schema import Story

DEFAULT_MODEL = "openai/gpt-oss-120b"

FACT_CHECK_SYSTEM_PROMPT = """You are an expert technical fact-checker for an engineering intelligence briefing.
Analyze the provided story title, source, and text.
Your task:
1. Extract 2 to 3 concrete, verifiable facts directly grounded in the text (e.g. model parameters, benchmark score, company announcement, policy change). Do NOT speculate.
2. Identify the primary source URL if mentioned (e.g. arXiv link, GitHub repository, or official announcement). If the story URL itself is already the primary source, return it.

You must respond ONLY with a valid JSON object matching this structure:
{
  "verified_facts": ["fact 1", "fact 2", "fact 3"],
  "primary_source_url": "https://..."
}
"""


def _extract_json(text: str) -> dict:
    """Safely extracts JSON from model output even if wrapped in markdown."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return {}


def check_and_extract_facts(story: Story, client: Groq, model: str = DEFAULT_MODEL) -> tuple[list[str], str | None]:
    """
    Extracts verified facts and the primary source URL for a story.
    Falls back gracefully if the LLM call fails.
    """
    content_payload = (
        f"Title: {story.title}\n"
        f"Source: {story.source}\n"
        f"URL: {story.url}\n"
        f"Summary: {story.raw_summary}\n"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": FACT_CHECK_SYSTEM_PROMPT},
                {"role": "user", "content": content_payload},
            ],
            temperature=0.1,
        )

        output_text = response.choices[0].message.content or "{}"
        data = _extract_json(output_text)

        facts = data.get("verified_facts", [])
        if isinstance(facts, str):
            facts = [facts]
        if not facts:
            facts = [story.title]

        primary_url = data.get("primary_source_url") or story.url
        return facts, primary_url

    except Exception as e:
        print(f"[warn] Fact check failed for '{story.title[:40]}': {e}")
        return [story.title], story.url