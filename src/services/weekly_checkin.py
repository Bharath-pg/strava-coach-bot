from __future__ import annotations

import datetime
import logging

from src.services.strava import ActivitySummary, get_week_activities
from src.services.training_plan import (
    PlannedSession,
    get_planned_distance,
    get_planned_run_count,
    get_week_number,
    get_week_sessions,
)

logger = logging.getLogger(__name__)


def _match_activity_to_session(
    activity: ActivitySummary, sessions: list[PlannedSession]
) -> PlannedSession | None:
    activity_date = activity.start_date.date()
    return next((s for s in sessions if s.date == activity_date), None)


def _format_pace_comparison(actual_pace: str, target_pace: str) -> str:
    if not target_pace or target_pace == "":
        return actual_pace
    return f"{actual_pace} (target: {target_pace})"


def build_weekly_report(
    reference_date: datetime.date,
    activities: list[ActivitySummary],
    planned_sessions: list[PlannedSession],
) -> str:
    week_num = get_week_number(reference_date)
    monday = reference_date - datetime.timedelta(days=reference_date.weekday())
    sunday = monday + datetime.timedelta(days=6)

    planned_runs = get_planned_run_count(planned_sessions)
    planned_km = get_planned_distance(planned_sessions)
    actual_runs = len(activities)
    actual_km = round(sum(a.distance_km for a in activities), 2)

    pct = round(actual_km / planned_km * 100) if planned_km > 0 else 0
    pct_bar = "🟢" if pct >= 90 else "🟡" if pct >= 70 else "🔴"

    lines: list[str] = []
    lines.append(f"📊 Week {week_num} Check-in ({monday:%b %d} – {sunday:%b %d})")
    lines.append("")
    lines.append(f"{pct_bar} Runs: {actual_runs}/{planned_runs}")
    lines.append(f"{pct_bar} Distance: {actual_km} / {planned_km} km ({pct}%)")
    lines.append("")

    run_sessions = [s for s in planned_sessions if s.session_type != "rest"]
    activities_by_date = {a.start_date.date(): a for a in activities}

    for session in run_sessions:
        activity = activities_by_date.get(session.date)
        day_name = session.date.strftime("%a %b %d")

        if activity:
            pace_str = _format_pace_comparison(activity.pace_per_km, session.pace_target)
            dist_diff = activity.distance_km - session.distance_km
            dist_indicator = ""
            if abs(dist_diff) > 0.5:
                dist_indicator = f" ({'+' if dist_diff > 0 else ''}{dist_diff:.1f} km)"

            lines.append(
                f"  ✅ {day_name} | {session.description}"
            )
            lines.append(
                f"     {activity.distance_km} km in {activity.moving_time_formatted} | {pace_str}{dist_indicator}"
            )
        else:
            lines.append(f"  ❌ {day_name} | {session.description} — missed")

    # Next week preview
    next_monday = monday + datetime.timedelta(days=7)
    next_sessions = get_week_sessions(next_monday)
    next_run_sessions = [s for s in next_sessions if s.session_type != "rest"]

    if next_run_sessions:
        lines.append("")
        lines.append("📅 Next week preview:")
        for s in next_run_sessions:
            lines.append(f"  {s.date:%a} | {s.description}")

    return "\n".join(lines)


async def generate_weekly_checkin(
    reference_date: datetime.date | None = None,
) -> str:
    if reference_date is None:
        reference_date = datetime.date.today()

    planned = get_week_sessions(reference_date)
    if not planned:
        return "No training plan data for this week."

    try:
        activities = await get_week_activities(reference_date)
    except Exception:
        logger.exception("Failed to fetch Strava activities")
        return "⚠️ Couldn't fetch Strava data. Check your API credentials."

    return build_weekly_report(reference_date, activities, planned)


async def send_weekly_checkin(app, chat_id: int) -> None:  # type: ignore[no-untyped-def]
    report = await generate_weekly_checkin()
    await app.bot.send_message(chat_id=chat_id, text=report)
