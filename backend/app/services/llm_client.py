"""
Optional LLM client for knowledge extraction refinement.

Design principle: NOTHING in this platform requires an API key to run.
Every caller of this module checks `is_available()` first and falls back to
the heuristic extraction path when it's False. Once ANTHROPIC_API_KEY is
set, the exact same call sites get LLM-quality extraction with zero code
changes elsewhere -- this module is the only thing that changes behavior.

Uses the Anthropic Messages API directly via httpx rather than the SDK, to
keep the dependency footprint small and the request/response shape fully
visible and testable.
"""
from __future__ import annotations

import json
import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-4-6"


class LLMError(RuntimeError):
    pass


def is_available() -> bool:
    return bool(get_settings().ANTHROPIC_API_KEY)


async def complete_json(system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> dict | list:
    """Sends a prompt instructing the model to respond with ONLY JSON, and
    parses the result. Raises LLMError (never returns silently-wrong data)
    if the key is missing or the response isn't valid JSON -- callers must
    explicitly check is_available() first and have a fallback path; this
    function does not fall back on its own, so failures are never mistaken
    for "the model said there's nothing here"."""
    settings = get_settings()
    if not settings.ANTHROPIC_API_KEY:
        raise LLMError("ANTHROPIC_API_KEY is not set")

    headers = {
        "x-api-key": settings.ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    payload = {
        "model": DEFAULT_MODEL,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(ANTHROPIC_API_URL, headers=headers, json=payload)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise LLMError(f"Anthropic API request failed: {exc}") from exc

    data = resp.json()
    text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
    raw_text = "\n".join(text_blocks).strip()

    # Models sometimes wrap JSON in markdown fences despite instructions --
    # strip defensively rather than failing on an otherwise-correct response.
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Model did not return valid JSON: {exc}. Raw: {raw_text[:200]}") from exc
