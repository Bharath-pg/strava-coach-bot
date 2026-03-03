from __future__ import annotations

import logging

from src.llm.base import BaseLLM
from src.llm.gemini import GeminiLLM

logger = logging.getLogger(__name__)

_llm_instance: BaseLLM | None = None


def get_llm() -> BaseLLM:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = GeminiLLM()
    return _llm_instance


async def parse_user_message(text: str) -> dict:
    """Parse free-form text into a structured intent using the configured LLM."""
    llm = get_llm()
    return await llm.parse_intent(text)
