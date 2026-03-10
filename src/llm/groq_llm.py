from __future__ import annotations

import datetime
import json
import logging

from groq import AsyncGroq

from src.config import settings
from src.llm.base import BaseLLM
from src.llm.prompts import get_system_prompt
from src.llm.tools import TOOL_SCHEMAS, execute_tool

logger = logging.getLogger(__name__)

MAX_AGENT_ITERATIONS = 5


class GroqLLM(BaseLLM):
    def __init__(self) -> None:
        self.client = AsyncGroq(api_key=settings.groq_api_key)
        self.model = "llama-3.3-70b-versatile"

    async def parse_intent(self, user_message: str, today: str | None = None) -> dict:
        """Legacy intent parser -- kept for backward compatibility."""
        today = today or datetime.date.today().isoformat()
        prompt = f"Today is {today}.\n\nUser message: {user_message}"

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": get_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=500,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()
            logger.info("Groq raw response: %s", raw[:200])
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse Groq JSON: %s | raw: %s", exc, raw[:300])
            return {
                "intent": "unknown",
                "reply": "I had trouble parsing that. Could you rephrase?",
            }
        except Exception as exc:
            logger.error("Groq API call failed: %s: %s", type(exc).__name__, exc)
            return {
                "intent": "unknown",
                "reply": "Sorry, I'm having trouble right now. Try a /command instead.",
            }

    async def generate_response(self, prompt: str) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1000,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logger.error("Groq generation failed: %s: %s", type(exc).__name__, exc)
            return "Sorry, I couldn't generate a response right now."

    async def run_agent(self, user_message: str, user_id: int) -> str:
        """Tool-calling agent loop.

        Sends the user message along with tool schemas to the LLM, executes any
        requested tool calls, feeds results back, and repeats until the model
        produces a final text response or we hit MAX_AGENT_ITERATIONS.
        """
        messages: list[dict] = [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_message},
        ]

        for iteration in range(MAX_AGENT_ITERATIONS):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                    tool_choice="auto",
                    temperature=0.2,
                    max_tokens=1500,
                )
            except Exception as exc:
                logger.error("Groq agent call failed (iter %d): %s", iteration, exc)
                return "Sorry, I'm having trouble processing that right now."

            choice = response.choices[0]
            assistant_msg = choice.message

            if not assistant_msg.tool_calls:
                return assistant_msg.content or "I'm not sure how to help with that."

            messages.append({
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in assistant_msg.tool_calls
                ],
            })

            for tc in assistant_msg.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                logger.info("Agent tool call: %s(%s)", tool_name, json.dumps(tool_args)[:200])
                result = await execute_tool(tool_name, tool_args, user_id)
                logger.info("Agent tool result (%s): %s", tool_name, result[:200])

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        logger.warning("Agent hit max iterations (%d) for user %d", MAX_AGENT_ITERATIONS, user_id)
        return "I took too many steps processing that. Could you simplify your request?"
