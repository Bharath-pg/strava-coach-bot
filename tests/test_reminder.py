from __future__ import annotations

import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.reminder import (
    advance_or_deactivate,
    cancel_reminder,
    get_due_reminders,
    list_reminders,
    set_reminder,
)


@pytest.mark.asyncio
async def test_set_and_list_reminder(db_session: AsyncSession) -> None:
    remind_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)
    reminder = await set_reminder(
        db_session,
        user_id=100,
        message="Call dentist",
        remind_at=remind_at,
    )
    assert reminder.id is not None
    assert reminder.message == "Call dentist"
    assert reminder.is_active is True
    assert reminder.recurrence == "none"

    reminders = await list_reminders(db_session, user_id=100)
    assert len(reminders) == 1
    assert reminders[0].id == reminder.id


@pytest.mark.asyncio
async def test_cancel_reminder(db_session: AsyncSession) -> None:
    remind_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)
    reminder = await set_reminder(
        db_session, user_id=200, message="Test", remind_at=remind_at
    )

    cancelled = await cancel_reminder(db_session, reminder_id=reminder.id, user_id=200)
    assert cancelled is True

    reminders = await list_reminders(db_session, user_id=200, active_only=True)
    assert len(reminders) == 0


@pytest.mark.asyncio
async def test_cancel_wrong_user(db_session: AsyncSession) -> None:
    remind_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)
    reminder = await set_reminder(
        db_session, user_id=300, message="Secret", remind_at=remind_at
    )
    cancelled = await cancel_reminder(db_session, reminder_id=reminder.id, user_id=999)
    assert cancelled is False


@pytest.mark.asyncio
async def test_get_due_reminders(db_session: AsyncSession) -> None:
    past = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=5)
    future = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=2)

    await set_reminder(db_session, user_id=400, message="Due now", remind_at=past)
    await set_reminder(db_session, user_id=400, message="Not yet", remind_at=future)

    due = await get_due_reminders(db_session)
    assert len(due) == 1
    assert due[0].message == "Due now"


@pytest.mark.asyncio
async def test_advance_recurring_reminder(db_session: AsyncSession) -> None:
    past = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=5)
    reminder = await set_reminder(
        db_session,
        user_id=500,
        message="Daily standup",
        remind_at=past,
        recurrence="daily",
    )
    original_time = reminder.remind_at

    await advance_or_deactivate(db_session, reminder)
    assert reminder.is_active is True
    assert reminder.remind_at == original_time + datetime.timedelta(days=1)


@pytest.mark.asyncio
async def test_deactivate_one_time_reminder(db_session: AsyncSession) -> None:
    past = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=5)
    reminder = await set_reminder(
        db_session, user_id=600, message="One-off", remind_at=past
    )
    await advance_or_deactivate(db_session, reminder)
    assert reminder.is_active is False
