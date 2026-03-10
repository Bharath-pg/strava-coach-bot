from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """Pluggable LLM interface -- swap Groq/Gemini for any other provider."""

    @abstractmethod
    async def parse_intent(self, user_message: str) -> dict:
        """Parse a natural-language message and return a structured intent dict."""

    @abstractmethod
    async def generate_response(self, prompt: str) -> str:
        """Generate a free-form text response."""

    @abstractmethod
    async def run_agent(self, user_message: str, user_id: int) -> str:
        """Run the tool-calling agent loop and return a final text response."""
