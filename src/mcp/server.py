"""MCP server exposing reminder, Strava, and training plan tools via stdio transport."""
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
    add_session_to_plan,
    create_plan,
    delete_session,
    get_active_plan,
    get_session as get_plan_session,
    get_week_number,
    get_week_sessions,
    update_session,
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
# Strava / Training tools (read)
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
async def get_run_details(user_id: int, date: str | None = None) -> str:
    """Get details of runs recorded on a specific date, compared against the training plan.

    Args:
        user_id: Telegram user ID
        date: Date in YYYY-MM-DD format (default today)
    """
    target_date = datetime.date.fromisoformat(date) if date else datetime.date.today()

    async with async_session_factory() as session:
        planned = await get_plan_session(session, user_id, target_date)

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
async def get_training_plan(user_id: int, date: str | None = None) -> str:
    """Get the planned training session for a specific date.

    Args:
        user_id: Telegram user ID
        date: Date in YYYY-MM-DD format (default today)
    """
    target_date = datetime.date.fromisoformat(date) if date else datetime.date.today()

    async with async_session_factory() as session:
        plan = await get_active_plan(session, user_id)
        planned_session = await get_plan_session(session, user_id, target_date)

    if not plan:
        return "No active training plan."

    if not planned_session:
        return f"No session scheduled for {target_date.strftime('%A, %b %d')}."

    day_label = target_date.strftime("%A, %b %d")
    week_num = get_week_number(plan.start_date, target_date)

    if planned_session.session_type == "rest":
        return f"{day_label} (Week {week_num}): Rest day. {planned_session.description}"

    lines = [
        f"{day_label} (Week {week_num}):",
        f"  {planned_session.description}",
        f"  Distance: {planned_session.distance_km} km | Pace: {planned_session.pace_target} | Type: {planned_session.session_type}",
    ]

    async with async_session_factory() as session:
        week = await get_week_sessions(session, user_id, target_date)
    remaining = [s for s in week if s.date > target_date and s.session_type != "rest"]
    if remaining:
        lines.append("Upcoming this week:")
        for s in remaining:
            lines.append(f"  {s.date:%a} | {s.description}")
    return "\n".join(lines)


@mcp.tool()
async def get_training_status(user_id: int, reference_date: str | None = None) -> str:
    """Get a weekly training check-in comparing actual Strava activities against the plan.

    Args:
        user_id: Telegram user ID
        reference_date: Any date within the target week (YYYY-MM-DD). Defaults to today.
    """
    ref = datetime.date.fromisoformat(reference_date) if reference_date else None
    return await generate_weekly_checkin(user_id, ref)


# ---------------------------------------------------------------------------
# Training plan tools (write)
# ---------------------------------------------------------------------------

@mcp.tool()
async def create_training_plan(
    user_id: int,
    name: str,
    goal: str,
    start_date: str,
    end_date: str,
    sessions: list[dict],
) -> str:
    """Create a complete training plan with all sessions. Deactivates any existing active plan.

    Args:
        user_id: Telegram user ID
        name: Plan name (e.g. 'Sub-50 10K Plan')
        goal: Goal description
        start_date: Plan start date YYYY-MM-DD
        end_date: Plan end date / race date YYYY-MM-DD
        sessions: Array of session dicts with date, session_type, distance_km, pace_target, description
    """
    async with async_session_factory() as session:
        plan = await create_plan(
            session,
            user_id=user_id,
            name=name,
            goal=goal,
            start_date=datetime.date.fromisoformat(start_date),
            end_date=datetime.date.fromisoformat(end_date),
            sessions_data=sessions,
        )

    run_count = sum(1 for s in sessions if s.get("session_type") != "rest")
    total_km = sum(s.get("distance_km", 0) for s in sessions)
    return (
        f"Training plan '{plan.name}' created with {len(sessions)} sessions "
        f"({run_count} runs, {total_km:.1f} km total) "
        f"from {plan.start_date} to {plan.end_date}."
    )


@mcp.tool()
async def add_training_session(
    user_id: int,
    date: str,
    session_type: str,
    distance_km: float = 0,
    pace_target: str = "",
    description: str = "",
) -> str:
    """Add a single session to the user's active training plan.

    Args:
        user_id: Telegram user ID
        date: Session date YYYY-MM-DD
        session_type: One of easy, rest, tempo, intervals, strides, long, race
        distance_km: Distance in km
        pace_target: Target pace
        description: Session description
    """
    date_val = datetime.date.fromisoformat(date)
    async with async_session_factory() as session:
        ts = await add_session_to_plan(
            session,
            user_id=user_id,
            date_val=date_val,
            session_type=session_type,
            distance_km=distance_km,
            pace_target=pace_target,
            description=description,
        )
    if not ts:
        return "No active training plan. Create one first!"
    return f"Session added (ID {ts.id}): {ts.date} | {ts.description}"


@mcp.tool()
async def update_training_session(
    user_id: int,
    session_id: int,
    date: str | None = None,
    session_type: str | None = None,
    distance_km: float | None = None,
    pace_target: str | None = None,
    description: str | None = None,
) -> str:
    """Update a session in the active plan by its session ID.

    Args:
        user_id: Telegram user ID
        session_id: ID of the training session to update
        date: New date YYYY-MM-DD
        session_type: New session type
        distance_km: New distance in km
        pace_target: New target pace
        description: New description
    """
    updates = {}
    if date is not None:
        updates["date"] = date
    if session_type is not None:
        updates["session_type"] = session_type
    if distance_km is not None:
        updates["distance_km"] = distance_km
    if pace_target is not None:
        updates["pace_target"] = pace_target
    if description is not None:
        updates["description"] = description

    async with async_session_factory() as session:
        ok = await update_session(session, user_id=user_id, session_id=session_id, **updates)
    if ok:
        return f"Session {session_id} updated."
    return f"Session {session_id} not found in your active plan."


@mcp.tool()
async def delete_training_session(user_id: int, session_id: int) -> str:
    """Delete a session from the active plan by its session ID.

    Args:
        user_id: Telegram user ID
        session_id: ID of the training session to delete
    """
    async with async_session_factory() as session:
        ok = await delete_session(session, user_id=user_id, session_id=session_id)
    if ok:
        return f"Session {session_id} deleted."
    return f"Session {session_id} not found in your active plan."


def main() -> None:
    logger.info("Starting MCP server (stdio)...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
