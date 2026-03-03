from __future__ import annotations

from unittest.mock import patch

import pytest

from src.llm.base import BaseLLM
from src.llm.parser import parse_user_message


class MockLLM(BaseLLM):
    def __init__(self, responses: dict[str, dict] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[str] = []

    async def parse_intent(self, user_message: str, **kwargs) -> dict:  # type: ignore[override]
        self.calls.append(user_message)
        return self.responses.get(
            user_message,
            {"intent": "unknown", "reply": "I don't understand."},
        )

    async def generate_response(self, prompt: str) -> str:
        return "Mock response"


@pytest.mark.asyncio
async def test_parse_expense_intent() -> None:
    mock_llm = MockLLM(
        responses={
            "I spent 45 dollars on groceries": {
                "intent": "add_expense",
                "amount": 45,
                "currency": "USD",
                "category": "groceries",
                "description": "groceries",
                "date": "2026-03-03",
            }
        }
    )

    with patch("src.llm.parser.get_llm", return_value=mock_llm):
        result = await parse_user_message("I spent 45 dollars on groceries")

    assert result["intent"] == "add_expense"
    assert result["amount"] == 45
    assert result["category"] == "groceries"


@pytest.mark.asyncio
async def test_parse_reminder_intent() -> None:
    mock_llm = MockLLM(
        responses={
            "remind me to call mom tomorrow at 5pm": {
                "intent": "set_reminder",
                "message": "call mom",
                "remind_at": "2026-03-04T17:00:00+00:00",
                "recurrence": "none",
            }
        }
    )

    with patch("src.llm.parser.get_llm", return_value=mock_llm):
        result = await parse_user_message("remind me to call mom tomorrow at 5pm")

    assert result["intent"] == "set_reminder"
    assert result["message"] == "call mom"


@pytest.mark.asyncio
async def test_parse_unknown_falls_back() -> None:
    mock_llm = MockLLM()

    with patch("src.llm.parser.get_llm", return_value=mock_llm):
        result = await parse_user_message("banana phone")

    assert result["intent"] == "unknown"


@pytest.mark.asyncio
async def test_mock_llm_tracks_calls() -> None:
    mock_llm = MockLLM()

    with patch("src.llm.parser.get_llm", return_value=mock_llm):
        await parse_user_message("hello")
        await parse_user_message("world")

    assert mock_llm.calls == ["hello", "world"]
