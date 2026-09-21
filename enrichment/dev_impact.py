"""
enrichment/dev_impact.py
Analyzes technical/developer impact and generates a 2-sentence TL;DR via Groq LLM.
"""

import json
import re
from groq import Groq
from storage.schema import Story

DEFAULT_MODEL = "openai/gpt-oss-120b"

IMPACT_SYSTEM_PROMPT = """You are a Principal Software Architect and Technology Intelligence Analyst.
Analyze the story and produce two outputs:
1. "tldr": Exactly 2 clear, informative sentences summarizing what happened.
2. "dev_impact_notes": 
   - If Category is 'tech': 2 to 3 concise bullet points focusing on engineering implications: architecture shifts, API changes, licensing (open weights vs closed), compute/memory requirements, or developer workflow impact.
   - If Category is 'world': 2 concise bullet points focusing on macro geopolitical or economic significance.

You must respond ONLY with a valid JSON object matching this structure:
{
  "tldr": "Sentence one. Sentence two.",
  "dev_impact_notes": "- Bullet 1\\n- Bullet 2"
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


def analyze_impact_and_tldr(story: Story, client: Groq, model: str = DEFAULT_MODEL) -> tuple[str, str]:
    """
    Generates a TL;DR and technical developer impact notes for a story.
    Falls back gracefully if the LLM call fails.
    """
    content_payload = (
        f"Category: {story.category}\n"
        f"Title: {story.title}\n"
        f"Source: {story.source}\n"
        f"Summary: {story.raw_summary}\n"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": IMPACT_SYSTEM_PROMPT},
                {"role": "user", "content": content_payload},
            ],
            temperature=0.2,
        )

        output_text = response.choices[0].message.content or "{}"
        data = _extract_json(output_text)

        tldr = data.get("tldr", story.raw_summary[:200] or story.title)
        dev_impact = data.get("dev_impact_notes", "- Details pending verification.")

        return tldr, dev_impact

    except Exception as e:
        print(f"[warn] Impact analysis failed for '{story.title[:40]}': {e}")
        return story.title, "- Details pending verification."


def enrich_story(story: Story, client: Groq, model: str = DEFAULT_MODEL) -> Story:
    """Enriches a single Story object in place with all Phase 3 fields."""
    from enrichment.fact_checker import check_and_extract_facts

    facts, primary_url = check_and_extract_facts(story, client=client, model=model)
    tldr, dev_impact = analyze_impact_and_tldr(story, client=client, model=model)

    story.verified_facts = facts
    story.primary_source_url = primary_url
    story.tldr = tldr
    story.dev_impact_notes = dev_impact

    return story


def enrich_all(stories: list[Story], client: Groq, model: str = DEFAULT_MODEL) -> list[Story]:
    """Sequentially enriches all stories in the list."""
    enriched = []
    total = len(stories)
    for idx, story in enumerate(stories, 1):
        print(f"[{idx}/{total}] Enriching: {story.title[:60]}...")
        enriched.append(enrich_story(story, client=client, model=model))
    return enriched