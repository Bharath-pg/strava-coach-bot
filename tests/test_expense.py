from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.expense import add_expense, expense_summary, period_to_dates, query_expenses


@pytest.mark.asyncio
async def test_add_expense(db_session: AsyncSession) -> None:
    exp = await add_expense(
        db_session,
        user_id=12345,
        amount=Decimal("29.99"),
        currency="USD",
        category="food",
        description="Pizza delivery",
    )
    assert exp.id is not None
    assert exp.amount == Decimal("29.99")
    assert exp.category == "food"
    assert exp.currency == "USD"


@pytest.mark.asyncio
async def test_query_expenses_filters(db_session: AsyncSession) -> None:
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    await add_expense(db_session, user_id=1, amount=Decimal("10"), category="food", date=today)
    await add_expense(db_session, user_id=1, amount=Decimal("20"), category="transport", date=today)
    await add_expense(
        db_session, user_id=1, amount=Decimal("15"), category="food", date=yesterday
    )

    food_only = await query_expenses(db_session, user_id=1, category="food")
    assert len(food_only) == 2
    assert all(e.category == "food" for e in food_only)

    today_only = await query_expenses(db_session, user_id=1, start_date=today, end_date=today)
    assert len(today_only) == 2


@pytest.mark.asyncio
async def test_expense_summary(db_session: AsyncSession) -> None:
    today = datetime.date.today()
    await add_expense(db_session, user_id=2, amount=Decimal("50"), category="food", date=today)
    await add_expense(db_session, user_id=2, amount=Decimal("30"), category="food", date=today)
    await add_expense(
        db_session, user_id=2, amount=Decimal("100"), category="rent", date=today
    )

    summary = await expense_summary(db_session, user_id=2, start_date=today, end_date=today)
    assert summary["grand_total"] == 180.0
    assert "food" in summary["categories"]
    assert summary["categories"]["food"]["total"] == 80.0
    assert summary["categories"]["food"]["count"] == 2


def test_period_to_dates() -> None:
    today = datetime.date.today()
    start, end = period_to_dates("today")
    assert start == end == today

    start, end = period_to_dates("month")
    assert start == today.replace(day=1)
    assert end == today
