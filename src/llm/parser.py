from __future__ import annotations

import logging

from src.config import settings
from src.llm.base import BaseLLM

logger = logging.getLogger(__name__)

_llm_instance: BaseLLM | None = None


def get_llm() -> BaseLLM:
    global _llm_instance
    if _llm_instance is None:
        if settings.llm_provider == "gemini":
            from src.llm.gemini import GeminiLLM

            _llm_instance = GeminiLLM()
            logger.info("Using Gemini LLM")
        else:
            from src.llm.groq_llm import GroqLLM

            _llm_instance = GroqLLM()
            logger.info("Using Groq LLM (llama-3.3-70b)")
    return _llm_instance


async def parse_user_message(text: str) -> dict:
    """Legacy intent parser -- kept for backward compatibility with tests."""
    llm = get_llm()
    return await llm.parse_intent(text)


async def run_agent(text: str, user_id: int) -> str:
    """Run the tool-calling agent loop and return the final text response."""
    llm = get_llm()
    return await llm.run_agent(text, user_id)
