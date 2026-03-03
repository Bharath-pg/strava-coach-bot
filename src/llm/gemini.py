from __future__ import annotations

import json
import logging

from google import genai
from google.genai import types

from src.config import settings
from src.llm.base import BaseLLM

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a personal assistant that parses user messages into structured intents.
Today's date context will be provided. Respond ONLY with valid JSON, no markdown fences.

Possible intents and their required fields:

1. add_expense:
   {"intent": "add_expense", "amount": <number>,
    "currency": "<3-letter>", "category": "<string>",
    "description": "<string>", "date": "<YYYY-MM-DD>"}

2. query_expenses:
   {"intent": "query_expenses", "category": "<string|null>",
    "start_date": "<YYYY-MM-DD|null>",
    "end_date": "<YYYY-MM-DD|null>"}

3. expense_summary:
   {"intent": "expense_summary",
    "period": "<today|week|month|year|all>"}

4. set_reminder:
   {"intent": "set_reminder", "message": "<what to remind>",
    "remind_at": "<ISO-8601 datetime>",
    "recurrence": "<none|daily|weekly|monthly>"}

5. list_reminders:
   {"intent": "list_reminders"}

6. cancel_reminder:
   {"intent": "cancel_reminder", "reminder_id": <int>}

7. help:
   {"intent": "help"}

8. unknown:
   {"intent": "unknown", "reply": "<friendly response to the user>"}

Rules:
- Default currency to USD if not mentioned.
- Default category to "other" if not clear.
- If the user is just chatting, use "unknown" with a friendly reply.
- Dates should be inferred relative to today.
- For reminders, always produce a full ISO-8601 datetime with timezone offset.
"""


class GeminiLLM(BaseLLM):
    def __init__(self) -> None:
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = "gemini-2.0-flash"

    async def parse_intent(self, user_message: str, today: str | None = None) -> dict:
        today = today or __import__("datetime").date.today().isoformat()
        prompt = f"Today is {today}.\n\nUser message: {user_message}"

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.1,
                    max_output_tokens=500,
                ),
            )
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("LLM parse failed: %s", exc)
            return {"intent": "unknown", "reply": "Sorry, I didn't understand that. Try /help."}

    async def generate_response(self, prompt: str) -> str:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.7, max_output_tokens=1000),
            )
            return response.text.strip()
        except Exception as exc:
            logger.warning("LLM generation failed: %s", exc)
            return "Sorry, I couldn't generate a response right now."
