"""MCP server exposing reminder and Strava tools via stdio transport."""
from __future__ import annotations

import datetime
import logging

from mcp.server.fastmcp import FastMCP

from src.db.session import async_session_factory
from src.services.reminder import (
    cancel_reminder as svc_cancel_reminder,
    list_reminders as svc_list_reminders,
    set_reminder as svc_set_reminder,
)
from src.services.strava import get_activities, get_day_activities
from src.services.training_plan import (
    get_session as get_plan_session,
    get_week_number,
    get_week_sessions,
)
from src.services.weekly_checkin import generate_weekly_checkin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("strava-coach")


# ---------------------------------------------------------------------------
# Reminder tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def set_reminder(
    user_id: int,
    message: str,
    remind_at: str,
    recurrence: str = "none",
) -> str:
    """Create a new reminder.

    Args:
        user_id: Telegram user ID
        message: Reminder message text
        remind_at: ISO-8601 datetime for when to fire
        recurrence: One of none, daily, weekly, monthly
    """
    dt = datetime.datetime.fromisoformat(remind_at)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.UTC)

    async with async_session_factory() as session:
        reminder = await svc_set_reminder(
            session, user_id=user_id, message=message, remind_at=dt, recurrence=recurrence
        )
    recur_text = f" (repeats {recurrence})" if recurrence != "none" else ""
    return f"Reminder #{reminder.id}: \"{reminder.message}\" at {reminder.remind_at}{recur_text}"


@mcp.tool()
async def list_reminders(user_id: int) -> str:
    """List all active reminders for a user.

    Args:
        user_id: Telegram user ID
    """
    async with async_session_factory() as session:
        reminders = await svc_list_reminders(session, user_id=user_id)

    if not reminders:
        return "No active reminders."

    lines = ["Active reminders:"]
    for r in reminders:
        recur = f" (repeats {r.recurrence})" if r.recurrence != "none" else ""
        lines.append(f"  [{r.id}] {r.remind_at:%Y-%m-%d %H:%M} | {r.message}{recur}")
    return "\n".join(lines)


@mcp.tool()
async def cancel_reminder(user_id: int, reminder_id: int) -> str:
    """Cancel (deactivate) a reminder.

    Args:
        user_id: Telegram user ID
        reminder_id: ID of the reminder to cancel
    """
    async with async_session_factory() as session:
        cancelled = await svc_cancel_reminder(
            session, reminder_id=reminder_id, user_id=user_id
        )
    if cancelled:
        return f"Reminder {reminder_id} cancelled."
    return f"Reminder {reminder_id} not found or already cancelled."


# ---------------------------------------------------------------------------
# Strava / Training tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_strava_activities(
    after_date: str | None = None,
    before_date: str | None = None,
    activity_type: str = "Run",
) -> str:
    """Fetch Strava running activities within a date range.

    Args:
        after_date: Start date YYYY-MM-DD
        before_date: End date YYYY-MM-DD
        activity_type: Strava activity type filter (default Run)
    """
    after = datetime.date.fromisoformat(after_date) if after_date else None
    before = datetime.date.fromisoformat(before_date) if before_date else None
    activities = await get_activities(after=after, before=before, activity_type=activity_type)

    if not activities:
        return "No activities found for the given period."

    lines = [f"Found {len(activities)} activities:"]
    for a in activities:
        lines.append(
            f"  {a.start_date:%Y-%m-%d} | {a.name} | {a.distance_km} km "
            f"| {a.moving_time_formatted} | {a.pace_per_km}"
        )
    return "\n".join(lines)


@mcp.tool()
async def get_run_details(date: str | None = None) -> str:
    """Get details of runs recorded on a specific date, compared against the training plan.

    Args:
        date: Date in YYYY-MM-DD format (default today)
    """
    target_date = datetime.date.fromisoformat(date) if date else datetime.date.today()
    planned = get_plan_session(target_date)

    try:
        activities = await get_day_activities(target_date)
    except Exception:
        return "Could not fetch Strava data. Check API credentials."

    day_label = target_date.strftime("%A, %b %d")
    if not activities:
        plan_text = f"\nPlanned: {planned.description}" if planned else ""
        return f"No runs recorded on {day_label}.{plan_text}"

    lines = [f"Runs on {day_label}:"]
    for act in activities:
        lines.append(
            f"  {act.name}: {act.distance_km} km in {act.moving_time_formatted} | {act.pace_per_km}"
        )
        if planned and planned.session_type != "rest":
            dist_diff = act.distance_km - planned.distance_km
            sign = "+" if dist_diff > 0 else ""
            lines.append(f"  Plan: {planned.description} | Distance vs plan: {sign}{dist_diff:.1f} km")
            if planned.pace_target:
                lines.append(f"  Pace target: {planned.pace_target} | Actual: {act.pace_per_km}")
    return "\n".join(lines)


@mcp.tool()
async def get_training_plan(date: str | None = None) -> str:
    """Get the planned training session for a specific date.

    Args:
        date: Date in YYYY-MM-DD format (default today)
    """
    target_date = datetime.date.fromisoformat(date) if date else datetime.date.today()
    session = get_plan_session(target_date)

    if not session:
        return f"No plan data for {target_date.strftime('%A, %b %d')}."

    day_label = target_date.strftime("%A, %b %d")
    week_num = get_week_number(target_date)

    if session.session_type == "rest":
        return f"{day_label} (Week {week_num}): Rest day. {session.description}"

    lines = [
        f"{day_label} (Week {week_num}):",
        f"  {session.description}",
        f"  Distance: {session.distance_km} km | Pace: {session.pace_target} | Type: {session.session_type}",
    ]

    week_sessions = get_week_sessions(target_date)
    remaining = [s for s in week_sessions if s.date > target_date and s.session_type != "rest"]
    if remaining:
        lines.append("Upcoming this week:")
        for s in remaining:
            lines.append(f"  {s.date:%a} | {s.description}")
    return "\n".join(lines)


@mcp.tool()
async def get_training_status(reference_date: str | None = None) -> str:
    """Get a weekly training check-in comparing actual Strava activities against the plan.

    Args:
        reference_date: Any date within the target week (YYYY-MM-DD). Defaults to today.
    """
    ref = datetime.date.fromisoformat(reference_date) if reference_date else None
    return await generate_weekly_checkin(ref)


def main() -> None:
    logger.info("Starting MCP server (stdio)...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
