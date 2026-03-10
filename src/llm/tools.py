"""Tool schemas (OpenAI function-calling format) and executor for the agent loop.

user_id is deliberately excluded from schemas -- it is injected server-side
so the LLM cannot fabricate or guess other users' IDs.
"""
from __future__ import annotations

import datetime
import json
import logging

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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool schemas (OpenAI function-calling format)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict] = [
    # -- Reminders --
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Create a new reminder at a specific date/time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "What to remind about"},
                    "remind_at": {
                        "type": "string",
                        "description": "ISO-8601 datetime for when to fire (e.g. 2026-03-05T15:00:00+05:30)",
                    },
                    "recurrence": {
                        "type": "string",
                        "enum": ["none", "daily", "weekly", "monthly"],
                        "description": "Recurrence pattern (default none)",
                    },
                },
                "required": ["message", "remind_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "List all active reminders.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_reminder",
            "description": "Cancel (deactivate) a reminder by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reminder_id": {"type": "integer", "description": "ID of the reminder to cancel"},
                },
                "required": ["reminder_id"],
            },
        },
    },
    # -- Strava --
    {
        "type": "function",
        "function": {
            "name": "get_strava_activities",
            "description": "Fetch Strava running activities within a date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "after_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                    "before_date": {"type": "string", "description": "End date YYYY-MM-DD"},
                    "activity_type": {
                        "type": "string",
                        "description": "Strava activity type filter (default Run)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_run_details",
            "description": "Get details of runs recorded on a specific date, compared against the training plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format. Defaults to today.",
                    },
                },
                "required": [],
            },
        },
    },
    # -- Training plan (read) --
    {
        "type": "function",
        "function": {
            "name": "get_training_plan",
            "description": "Get the planned training session for a specific date from the user's active plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format. Defaults to today.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_training_status",
            "description": "Get a weekly training check-in report comparing actual Strava activities against the training plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reference_date": {
                        "type": "string",
                        "description": "Any date within the target week (YYYY-MM-DD). Defaults to today.",
                    },
                },
                "required": [],
            },
        },
    },
    # -- Training plan (write) --
    {
        "type": "function",
        "function": {
            "name": "create_training_plan",
            "description": (
                "Create a complete training plan with all sessions. "
                "This deactivates any existing active plan. "
                "Generate a full, periodized plan with progressive overload, rest days, "
                "and a taper week before the target race date."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Plan name (e.g. 'Sub-50 10K Plan')"},
                    "goal": {"type": "string", "description": "Goal description (e.g. 'Run a 10K in under 50 minutes')"},
                    "start_date": {"type": "string", "description": "Plan start date YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "Plan end date / race date YYYY-MM-DD"},
                    "sessions": {
                        "type": "array",
                        "description": "Array of training sessions for the entire plan",
                        "items": {
                            "type": "object",
                            "properties": {
                                "date": {"type": "string", "description": "Session date YYYY-MM-DD"},
                                "session_type": {
                                    "type": "string",
                                    "enum": ["easy", "rest", "tempo", "intervals", "strides", "long", "race"],
                                    "description": "Type of session",
                                },
                                "distance_km": {"type": "number", "description": "Distance in km"},
                                "pace_target": {"type": "string", "description": "Target pace (e.g. '6:00/km')"},
                                "description": {"type": "string", "description": "Human-readable session description"},
                            },
                            "required": ["date", "session_type", "distance_km", "description"],
                        },
                    },
                },
                "required": ["name", "goal", "start_date", "end_date", "sessions"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_training_session",
            "description": "Add a single session to the user's active training plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Session date YYYY-MM-DD"},
                    "session_type": {
                        "type": "string",
                        "enum": ["easy", "rest", "tempo", "intervals", "strides", "long", "race"],
                    },
                    "distance_km": {"type": "number", "description": "Distance in km"},
                    "pace_target": {"type": "string", "description": "Target pace"},
                    "description": {"type": "string", "description": "Session description"},
                },
                "required": ["date", "session_type", "distance_km", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_training_session",
            "description": "Update a session in the active plan by its session ID. Only provide fields to change.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer", "description": "ID of the training session to update"},
                    "date": {"type": "string", "description": "New date YYYY-MM-DD"},
                    "session_type": {
                        "type": "string",
                        "enum": ["easy", "rest", "tempo", "intervals", "strides", "long", "race"],
                    },
                    "distance_km": {"type": "number", "description": "New distance in km"},
                    "pace_target": {"type": "string", "description": "New target pace"},
                    "description": {"type": "string", "description": "New description"},
                },
                "required": ["session_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_training_session",
            "description": "Delete a session from the active plan by its session ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer", "description": "ID of the training session to delete"},
                },
                "required": ["session_id"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool executor -- maps tool names to service-layer calls
# ---------------------------------------------------------------------------

async def execute_tool(name: str, args: dict | None, user_id: int) -> str:
    """Execute a tool by name, injecting user_id, and return a string result."""
    if args is None:
        args = {}
    try:
        executor = _TOOL_EXECUTORS.get(name)
        if not executor:
            return f"Unknown tool: {name}"
        return await executor(args, user_id)
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        return f"Tool error ({name}): {exc}"


# -- Reminder executors --

async def _exec_set_reminder(args: dict, user_id: int) -> str:
    dt = datetime.datetime.fromisoformat(args["remind_at"])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.UTC)
    recurrence = args.get("recurrence", "none")
    async with async_session_factory() as session:
        reminder = await svc_set_reminder(
            session, user_id=user_id, message=args["message"], remind_at=dt, recurrence=recurrence
        )
    recur_text = f" (repeats {recurrence})" if recurrence != "none" else ""
    return f"Reminder #{reminder.id}: \"{reminder.message}\" at {reminder.remind_at:%Y-%m-%d %H:%M}{recur_text}"


async def _exec_list_reminders(args: dict, user_id: int) -> str:
    async with async_session_factory() as session:
        reminders = await svc_list_reminders(session, user_id=user_id)
    if not reminders:
        return "No active reminders."
    lines = ["Active reminders:"]
    for r in reminders:
        recur = f" (repeats {r.recurrence})" if r.recurrence != "none" else ""
        lines.append(f"  [{r.id}] {r.remind_at:%Y-%m-%d %H:%M} | {r.message}{recur}")
    return "\n".join(lines)


async def _exec_cancel_reminder(args: dict, user_id: int) -> str:
    reminder_id = int(args["reminder_id"])
    async with async_session_factory() as session:
        cancelled = await svc_cancel_reminder(session, reminder_id=reminder_id, user_id=user_id)
    if cancelled:
        return f"Reminder {reminder_id} cancelled."
    return f"Reminder {reminder_id} not found or already cancelled."


# -- Strava executors --

async def _exec_get_strava_activities(args: dict, user_id: int) -> str:
    after = datetime.date.fromisoformat(args["after_date"]) if args.get("after_date") else None
    before = datetime.date.fromisoformat(args["before_date"]) if args.get("before_date") else None
    activity_type = args.get("activity_type", "Run")
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


async def _exec_get_run_details(args: dict, user_id: int) -> str:
    target_date = (
        datetime.date.fromisoformat(args["date"]) if args.get("date") else datetime.date.today()
    )
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
        lines.append(f"  {act.name}: {act.distance_km} km in {act.moving_time_formatted} | {act.pace_per_km}")
        if planned and planned.session_type != "rest":
            dist_diff = act.distance_km - planned.distance_km
            sign = "+" if dist_diff > 0 else ""
            lines.append(f"  Plan: {planned.description} | Distance vs plan: {sign}{dist_diff:.1f} km")
            if planned.pace_target:
                lines.append(f"  Pace target: {planned.pace_target} | Actual: {act.pace_per_km}")
    return "\n".join(lines)


# -- Training plan (read) executors --

async def _exec_get_training_plan(args: dict, user_id: int) -> str:
    target_date = (
        datetime.date.fromisoformat(args["date"]) if args.get("date") else datetime.date.today()
    )
    async with async_session_factory() as session:
        plan = await get_active_plan(session, user_id)
        planned_session = await get_plan_session(session, user_id, target_date)

    if not plan:
        return "No active training plan. Tell me your goal and I'll create one!"

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


async def _exec_get_training_status(args: dict, user_id: int) -> str:
    ref = (
        datetime.date.fromisoformat(args["reference_date"])
        if args.get("reference_date")
        else None
    )
    return await generate_weekly_checkin(user_id, ref)


# -- Training plan (write) executors --

async def _exec_create_training_plan(args: dict, user_id: int) -> str:
    sessions_data = args["sessions"]
    if isinstance(sessions_data, str):
        sessions_data = json.loads(sessions_data)

    async with async_session_factory() as session:
        plan = await create_plan(
            session,
            user_id=user_id,
            name=args["name"],
            goal=args["goal"],
            start_date=datetime.date.fromisoformat(args["start_date"]),
            end_date=datetime.date.fromisoformat(args["end_date"]),
            sessions_data=sessions_data,
        )

    run_count = sum(1 for s in sessions_data if s.get("session_type") != "rest")
    total_km = sum(s.get("distance_km", 0) for s in sessions_data)
    return (
        f"Training plan '{plan.name}' created with {len(sessions_data)} sessions "
        f"({run_count} runs, {total_km:.1f} km total) "
        f"from {plan.start_date} to {plan.end_date}."
    )


async def _exec_add_training_session(args: dict, user_id: int) -> str:
    date_val = datetime.date.fromisoformat(args["date"])
    async with async_session_factory() as session:
        ts = await add_session_to_plan(
            session,
            user_id=user_id,
            date_val=date_val,
            session_type=args["session_type"],
            distance_km=args.get("distance_km", 0),
            pace_target=args.get("pace_target", ""),
            description=args.get("description", ""),
        )
    if not ts:
        return "No active training plan. Create one first!"
    return f"Session added (ID {ts.id}): {ts.date} | {ts.description}"


async def _exec_update_training_session(args: dict, user_id: int) -> str:
    session_id = int(args["session_id"])
    updates = {k: v for k, v in args.items() if k != "session_id"}
    async with async_session_factory() as session:
        ok = await update_session(session, user_id=user_id, session_id=session_id, **updates)
    if ok:
        return f"Session {session_id} updated."
    return f"Session {session_id} not found in your active plan."


async def _exec_delete_training_session(args: dict, user_id: int) -> str:
    session_id = int(args["session_id"])
    async with async_session_factory() as session:
        ok = await delete_session(session, user_id=user_id, session_id=session_id)
    if ok:
        return f"Session {session_id} deleted."
    return f"Session {session_id} not found in your active plan."


_TOOL_EXECUTORS: dict[str, callable] = {
    "set_reminder": _exec_set_reminder,
    "list_reminders": _exec_list_reminders,
    "cancel_reminder": _exec_cancel_reminder,
    "get_strava_activities": _exec_get_strava_activities,
    "get_run_details": _exec_get_run_details,
    "get_training_plan": _exec_get_training_plan,
    "get_training_status": _exec_get_training_status,
    "create_training_plan": _exec_create_training_plan,
    "add_training_session": _exec_add_training_session,
    "update_training_session": _exec_update_training_session,
    "delete_training_session": _exec_delete_training_session,
}
