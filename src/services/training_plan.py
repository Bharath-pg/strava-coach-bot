from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.training_plan import TrainingPlan, TrainingSession

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlannedSession:
    """Read-only view of a training session (kept for backward compat)."""
    date: date
    session_type: str
    distance_km: float
    pace_target: str
    description: str
    session_id: int | None = None


def _row_to_planned(row: TrainingSession) -> PlannedSession:
    return PlannedSession(
        date=row.date,
        session_type=row.session_type,
        distance_km=row.distance_km,
        pace_target=row.pace_target,
        description=row.description,
        session_id=row.id,
    )


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

async def get_active_plan(session: AsyncSession, user_id: int) -> TrainingPlan | None:
    stmt = (
        select(TrainingPlan)
        .options(selectinload(TrainingPlan.sessions))
        .where(TrainingPlan.user_id == user_id, TrainingPlan.is_active.is_(True))
        .order_by(TrainingPlan.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_session(session: AsyncSession, user_id: int, d: date) -> PlannedSession | None:
    plan = await get_active_plan(session, user_id)
    if not plan:
        return None
    for s in plan.sessions:
        if s.date == d:
            return _row_to_planned(s)
    return None


async def get_week_sessions(session: AsyncSession, user_id: int, reference_date: date) -> list[PlannedSession]:
    monday = reference_date - timedelta(days=reference_date.weekday())
    sunday = monday + timedelta(days=7)
    plan = await get_active_plan(session, user_id)
    if not plan:
        return []
    return [_row_to_planned(s) for s in plan.sessions if monday <= s.date < sunday]


async def get_all_sessions(session: AsyncSession, user_id: int) -> list[PlannedSession]:
    plan = await get_active_plan(session, user_id)
    if not plan:
        return []
    return [_row_to_planned(s) for s in plan.sessions]


def get_week_number(plan_start: date, d: date) -> int:
    plan_monday = plan_start - timedelta(days=plan_start.weekday())
    delta = (d - plan_monday).days
    if delta < 0:
        return 0
    return delta // 7 + 1


def get_planned_distance(sessions: list[PlannedSession]) -> float:
    return sum(s.distance_km for s in sessions if s.session_type != "rest")


def get_planned_run_count(sessions: list[PlannedSession]) -> int:
    return sum(1 for s in sessions if s.session_type != "rest")


# ---------------------------------------------------------------------------
# Daily notification
# ---------------------------------------------------------------------------

async def format_daily_notification(user_id: int, target_date: date) -> str:
    """Build a Telegram message describing the session for *target_date*.

    Returns a human-readable string for every case:
    no plan, rest day, run day, or date outside the plan range.
    """
    from src.db.session import async_session_factory

    async with async_session_factory() as session:
        plan = await get_active_plan(session, user_id)

    if not plan:
        return (
            "\U0001f4cb You don't have an active training plan yet. "
            "Tell me your goal and I'll create one!"
        )

    day_label = target_date.strftime("%A, %b %d")
    week_num = get_week_number(plan.start_date, target_date)

    if target_date < plan.start_date:
        days_until = (plan.start_date - target_date).days
        suffix = "s" if days_until != 1 else ""
        return (
            f"\U0001f4c5 {day_label} \u2014 Your plan ({plan.name}) "
            f"starts in {days_until} day{suffix}. Rest up until then!"
        )

    if target_date > plan.end_date:
        return (
            f"\U0001f3c1 {day_label} \u2014 Your plan ({plan.name}) "
            f"ended on {plan.end_date:%b %d}. Time to set a new goal!"
        )

    async with async_session_factory() as session:
        planned = await get_session(session, user_id, target_date)

    if not planned:
        return (
            f"\U0001f6cc {day_label} (Week {week_num}) \u2014 "
            "No session scheduled. Enjoy the rest!"
        )

    if planned.session_type == "rest":
        return (
            f"\U0001f6cc {day_label} (Week {week_num}) \u2014 "
            "Rest day. Recover and hydrate!"
        )

    pace_info = f" at {planned.pace_target}" if planned.pace_target else ""
    return (
        f"\U0001f3c3 {day_label} (Week {week_num}) \u2014 "
        f"{planned.description}\n"
        f"   {planned.distance_km} km{pace_info} | {planned.session_type}"
    )


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

async def create_plan(
    session: AsyncSession,
    *,
    user_id: int,
    name: str,
    goal: str,
    start_date: date,
    end_date: date,
    sessions_data: list[dict],
) -> TrainingPlan:
    """Create a new training plan, deactivating any existing active plan."""
    await _deactivate_plans(session, user_id)

    plan = TrainingPlan(
        user_id=user_id,
        name=name,
        goal=goal,
        start_date=start_date,
        end_date=end_date,
        is_active=True,
    )
    session.add(plan)
    await session.flush()

    for s in sessions_data:
        ts = TrainingSession(
            plan_id=plan.id,
            date=datetime.date.fromisoformat(s["date"]) if isinstance(s["date"], str) else s["date"],
            session_type=s["session_type"],
            distance_km=s.get("distance_km", 0),
            pace_target=s.get("pace_target", ""),
            description=s.get("description", ""),
        )
        session.add(ts)

    await session.commit()
    await session.refresh(plan)
    return plan


async def add_session_to_plan(
    session: AsyncSession,
    *,
    user_id: int,
    date_val: date,
    session_type: str,
    distance_km: float = 0,
    pace_target: str = "",
    description: str = "",
) -> TrainingSession | None:
    plan = await get_active_plan(session, user_id)
    if not plan:
        return None

    ts = TrainingSession(
        plan_id=plan.id,
        date=date_val,
        session_type=session_type,
        distance_km=distance_km,
        pace_target=pace_target,
        description=description,
    )
    session.add(ts)
    await session.commit()
    await session.refresh(ts)
    return ts


async def update_session(
    session: AsyncSession,
    *,
    user_id: int,
    session_id: int,
    **updates: object,
) -> bool:
    plan = await get_active_plan(session, user_id)
    if not plan:
        return False

    plan_session_ids = {s.id for s in plan.sessions}
    if session_id not in plan_session_ids:
        return False

    allowed = {"date", "session_type", "distance_km", "pace_target", "description"}
    filtered = {k: v for k, v in updates.items() if k in allowed and v is not None}
    if not filtered:
        return False

    if "date" in filtered and isinstance(filtered["date"], str):
        filtered["date"] = datetime.date.fromisoformat(filtered["date"])

    stmt = (
        update(TrainingSession)
        .where(TrainingSession.id == session_id)
        .values(**filtered)
    )
    await session.execute(stmt)
    await session.commit()
    return True


async def delete_session(
    session: AsyncSession,
    *,
    user_id: int,
    session_id: int,
) -> bool:
    plan = await get_active_plan(session, user_id)
    if not plan:
        return False

    target = next((s for s in plan.sessions if s.id == session_id), None)
    if not target:
        return False

    await session.delete(target)
    await session.commit()
    return True


async def _deactivate_plans(session: AsyncSession, user_id: int) -> None:
    stmt = (
        update(TrainingPlan)
        .where(TrainingPlan.user_id == user_id, TrainingPlan.is_active.is_(True))
        .values(is_active=False)
    )
    await session.execute(stmt)
