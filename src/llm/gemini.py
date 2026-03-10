from __future__ import annotations

import datetime
import json
import logging

from google import genai
from google.genai import types

from src.config import settings
from src.llm.base import BaseLLM
from src.llm.prompts import SYSTEM_PROMPT, get_system_prompt

logger = logging.getLogger(__name__)


class GeminiLLM(BaseLLM):
    def __init__(self) -> None:
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = "gemini-2.5-flash-preview-04-17"

    async def parse_intent(self, user_message: str, today: str | None = None) -> dict:
        today = today or datetime.date.today().isoformat()
        prompt = f"Today is {today}.\n\nUser message: {user_message}"

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.1,
                    max_output_tokens=500,
                ),
            )
            raw = response.text.strip()
            logger.info("Gemini raw response: %s", raw[:200])
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse Gemini JSON: %s | raw: %s", exc, raw[:300])
            return {
                "intent": "unknown",
                "reply": "I had trouble parsing that. Could you rephrase?",
            }
        except Exception as exc:
            logger.error("Gemini API call failed: %s: %s", type(exc).__name__, exc)
            return {
                "intent": "unknown",
                "reply": "Sorry, I'm having trouble right now. Try a /command instead.",
            }

    async def generate_response(self, prompt: str) -> str:
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7, max_output_tokens=1000
                ),
            )
            return response.text.strip()
        except Exception as exc:
            logger.error("Gemini generation failed: %s: %s", type(exc).__name__, exc)
            return "Sorry, I couldn't generate a response right now."

    async def run_agent(self, user_message: str, user_id: int) -> str:
        """Gemini doesn't support the tool-calling agent loop yet -- fall back to generate."""
        prompt = f"{get_system_prompt()}\n\nUser message: {user_message}"
        return await self.generate_response(prompt)
