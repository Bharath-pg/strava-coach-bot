from __future__ import annotations

import datetime
import logging
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.reminder import Reminder

logger = logging.getLogger(__name__)

RECURRENCE_DELTAS: dict[str, timedelta | None] = {
    "none": None,
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
    "monthly": timedelta(days=30),
}


async def set_reminder(
    session: AsyncSession,
    *,
    user_id: int,
    message: str,
    remind_at: datetime.datetime,
    recurrence: str = "none",
) -> Reminder:
    if recurrence not in RECURRENCE_DELTAS:
        recurrence = "none"

    reminder = Reminder(
        user_id=user_id,
        message=message,
        remind_at=remind_at,
        recurrence=recurrence,
        is_active=True,
    )
    session.add(reminder)
    await session.commit()
    await session.refresh(reminder)
    return reminder


async def list_reminders(
    session: AsyncSession,
    *,
    user_id: int,
    active_only: bool = True,
) -> list[Reminder]:
    stmt = select(Reminder).where(Reminder.user_id == user_id)
    if active_only:
        stmt = stmt.where(Reminder.is_active.is_(True))
    stmt = stmt.order_by(Reminder.remind_at.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def cancel_reminder(
    session: AsyncSession,
    *,
    reminder_id: int,
    user_id: int,
) -> bool:
    stmt = (
        update(Reminder)
        .where(Reminder.id == reminder_id, Reminder.user_id == user_id)
        .values(is_active=False)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0  # type: ignore[return-value]


async def get_due_reminders(session: AsyncSession) -> list[Reminder]:
    """Fetch all active reminders whose remind_at is in the past."""
    now = datetime.datetime.now(datetime.UTC)
    stmt = (
        select(Reminder)
        .where(Reminder.is_active.is_(True), Reminder.remind_at <= now)
        .order_by(Reminder.remind_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def advance_or_deactivate(session: AsyncSession, reminder: Reminder) -> None:
    """After firing, either schedule the next recurrence or deactivate."""
    delta = RECURRENCE_DELTAS.get(reminder.recurrence)
    if delta:
        reminder.remind_at = reminder.remind_at + delta
        logger.info("Rescheduled reminder %d to %s", reminder.id, reminder.remind_at)
    else:
        reminder.is_active = False
        logger.info("Deactivated one-time reminder %d", reminder.id)
    await session.commit()
