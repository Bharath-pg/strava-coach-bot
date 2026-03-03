"""MCP server exposing expense and reminder tools via stdio transport."""
from __future__ import annotations

import asyncio
import datetime
import logging
from decimal import Decimal

from mcp.server.fastmcp import FastMCP

from src.db.session import async_session_factory
from src.services.expense import (
    add_expense as svc_add_expense,
)
from src.services.expense import (
    expense_summary as svc_expense_summary,
)
from src.services.expense import (
    period_to_dates,
)
from src.services.expense import (
    query_expenses as svc_query_expenses,
)
from src.services.reminder import (
    cancel_reminder as svc_cancel_reminder,
)
from src.services.reminder import (
    list_reminders as svc_list_reminders,
)
from src.services.reminder import (
    set_reminder as svc_set_reminder,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("personal-assistant")


@mcp.tool()
async def add_expense(
    user_id: int,
    amount: float,
    currency: str = "USD",
    category: str = "other",
    description: str = "",
    date: str | None = None,
) -> str:
    """Record a new expense for a user.

    Args:
        user_id: Telegram user ID
        amount: Expense amount
        currency: 3-letter currency code (default USD)
        category: Expense category
        description: Free-text description
        date: Date in YYYY-MM-DD format (default today)
    """
    expense_date = datetime.date.fromisoformat(date) if date else datetime.date.today()
    async with async_session_factory() as session:
        exp = await svc_add_expense(
            session,
            user_id=user_id,
            amount=Decimal(str(amount)),
            currency=currency,
            category=category,
            description=description,
            date=expense_date,
        )
    return f"Expense #{exp.id}: {exp.amount} {exp.currency} | {exp.category} | {exp.date}"


@mcp.tool()
async def query_expenses(
    user_id: int,
    category: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 20,
) -> str:
    """Query expenses with optional filters.

    Args:
        user_id: Telegram user ID
        category: Filter by category
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        limit: Max results (default 20)
    """
    sd = datetime.date.fromisoformat(start_date) if start_date else None
    ed = datetime.date.fromisoformat(end_date) if end_date else None

    async with async_session_factory() as session:
        expenses = await svc_query_expenses(
            session, user_id=user_id, category=category, start_date=sd, end_date=ed, limit=limit
        )

    if not expenses:
        return "No matching expenses found."

    lines = [f"Found {len(expenses)} expenses:"]
    for e in expenses:
        lines.append(f"  [{e.id}] {e.date} | ${e.amount} | {e.category} | {e.description}")
    return "\n".join(lines)


@mcp.tool()
async def expense_summary(
    user_id: int,
    period: str = "month",
) -> str:
    """Get an aggregated spending summary grouped by category.

    Args:
        user_id: Telegram user ID
        period: One of today, week, month, year, all
    """
    start_date, end_date = period_to_dates(period)
    async with async_session_factory() as session:
        summary = await svc_expense_summary(
            session, user_id=user_id, start_date=start_date, end_date=end_date
        )

    if not summary["categories"]:
        return f"No expenses for period: {period}"

    lines = [f"Summary ({period}): {start_date} to {end_date}"]
    for cat, data in summary["categories"].items():
        lines.append(f"  {cat}: ${data['total']:.2f} ({data['count']} items)")
    lines.append(f"Total: ${summary['grand_total']:.2f}")
    return "\n".join(lines)


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


def main() -> None:
    logger.info("Starting MCP server (stdio)...")
    asyncio.run(mcp.run_async(transport="stdio"))


if __name__ == "__main__":
    main()
