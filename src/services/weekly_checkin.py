from __future__ import annotations

import datetime
import logging

from src.db.session import async_session_factory
from src.services.strava import ActivitySummary, get_week_activities
from src.services.training_plan import (
    PlannedSession,
    get_active_plan,
    get_planned_distance,
    get_planned_run_count,
    get_week_number,
    get_week_sessions,
)

logger = logging.getLogger(__name__)


def _format_pace_comparison(actual_pace: str, target_pace: str) -> str:
    if not target_pace or target_pace == "":
        return actual_pace
    return f"{actual_pace} (target: {target_pace})"


def build_weekly_report(
    reference_date: datetime.date,
    activities: list[ActivitySummary],
    planned_sessions: list[PlannedSession],
    plan_start: datetime.date,
) -> str:
    week_num = get_week_number(plan_start, reference_date)
    monday = reference_date - datetime.timedelta(days=reference_date.weekday())
    sunday = monday + datetime.timedelta(days=6)

    planned_runs = get_planned_run_count(planned_sessions)
    planned_km = get_planned_distance(planned_sessions)
    actual_runs = len(activities)
    actual_km = round(sum(a.distance_km for a in activities), 2)

    pct = round(actual_km / planned_km * 100) if planned_km > 0 else 0
    pct_bar = "\U0001f7e2" if pct >= 90 else "\U0001f7e1" if pct >= 70 else "\U0001f534"

    lines: list[str] = []
    lines.append(f"\U0001f4ca Week {week_num} Check-in ({monday:%b %d} \u2013 {sunday:%b %d})")
    lines.append("")
    lines.append(f"{pct_bar} Runs: {actual_runs}/{planned_runs}")
    lines.append(f"{pct_bar} Distance: {actual_km} / {planned_km} km ({pct}%)")
    lines.append("")

    run_sessions = [s for s in planned_sessions if s.session_type != "rest"]
    activities_by_date = {a.start_date.date(): a for a in activities}

    for s in run_sessions:
        activity = activities_by_date.get(s.date)
        day_name = s.date.strftime("%a %b %d")

        if activity:
            pace_str = _format_pace_comparison(activity.pace_per_km, s.pace_target)
            dist_diff = activity.distance_km - s.distance_km
            dist_indicator = ""
            if abs(dist_diff) > 0.5:
                dist_indicator = f" ({'+' if dist_diff > 0 else ''}{dist_diff:.1f} km)"

            lines.append(f"  \u2705 {day_name} | {s.description}")
            lines.append(
                f"     {activity.distance_km} km in {activity.moving_time_formatted} | {pace_str}{dist_indicator}"
            )
        else:
            lines.append(f"  \u274c {day_name} | {s.description} \u2014 missed")

    return "\n".join(lines)


async def generate_weekly_checkin(
    user_id: int,
    reference_date: datetime.date | None = None,
) -> str:
    if reference_date is None:
        reference_date = datetime.date.today()

    async with async_session_factory() as session:
        plan = await get_active_plan(session, user_id)

    if not plan:
        return "No active training plan. Create one by telling me your goal!"

    async with async_session_factory() as session:
        planned = await get_week_sessions(session, user_id, reference_date)

    if not planned:
        return "No training sessions scheduled for this week."

    try:
        activities = await get_week_activities(reference_date)
    except Exception:
        logger.exception("Failed to fetch Strava activities")
        return "\u26a0\ufe0f Couldn't fetch Strava data. Check your API credentials."

    return build_weekly_report(reference_date, activities, planned, plan.start_date)


async def send_weekly_checkin(app, chat_id: int, user_id: int) -> None:  # type: ignore[no-untyped-def]
    report = await generate_weekly_checkin(user_id)
    await app.bot.send_message(chat_id=chat_id, text=report)
