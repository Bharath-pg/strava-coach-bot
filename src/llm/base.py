from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """Pluggable LLM interface -- swap Gemini for any other provider."""

    @abstractmethod
    async def parse_intent(self, user_message: str) -> dict:
        """Parse a natural-language message and return a structured intent dict.

        Expected return shape:
        {
            "intent": str,       # one of the known intent names
            "confidence": float,  # 0-1
            ...extra fields depending on intent
        }
        """

    @abstractmethod
    async def generate_response(self, prompt: str) -> str:
        """Generate a free-form text response."""
