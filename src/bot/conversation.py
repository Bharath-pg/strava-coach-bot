from __future__ import annotations

import datetime
import logging
from decimal import Decimal

from telegram import Update
from telegram.ext import ContextTypes

from src.config import settings
from src.db.session import async_session_factory
from src.llm.parser import parse_user_message
from src.services.expense import add_expense, expense_summary, period_to_dates, query_expenses
from src.services.reminder import cancel_reminder, list_reminders, set_reminder

logger = logging.getLogger(__name__)


async def conversation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch-all handler for natural-language messages routed through the LLM."""
    msg = update.effective_message
    if not msg or not msg.text or not update.effective_user:
        return

    user_id = update.effective_user.id
    if settings.allowed_users and user_id not in settings.allowed_users:
        await update.effective_message.reply_text("Sorry, you're not authorized to use this bot.")
        return

    text = msg.text
    parsed = await parse_user_message(text)
    intent = parsed.get("intent", "unknown")

    logger.info("User %d: intent=%s from '%s'", user_id, intent, text[:80])

    handler = _INTENT_HANDLERS.get(intent, _handle_unknown)
    await handler(update, parsed)


async def _handle_add_expense(update: Update, parsed: dict) -> None:
    user_id = update.effective_user.id  # type: ignore[union-attr]
    try:
        amount = Decimal(str(parsed.get("amount", 0)))
    except Exception:
        await update.effective_message.reply_text("I couldn't parse the amount. Please try again.")  # type: ignore[union-attr]
        return

    date_str = parsed.get("date")
    date = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()

    async with async_session_factory() as session:
        exp = await add_expense(
            session,
            user_id=user_id,
            amount=amount,
            currency=parsed.get("currency", "USD"),
            category=parsed.get("category", "other"),
            description=parsed.get("description", ""),
            date=date,
        )
    await update.effective_message.reply_text(  # type: ignore[union-attr]
        f"Got it! Recorded ${exp.amount} for {exp.category} on {exp.date}."
    )


async def _handle_query_expenses(update: Update, parsed: dict) -> None:
    user_id = update.effective_user.id  # type: ignore[union-attr]
    start = parsed.get("start_date")
    end = parsed.get("end_date")
    start_date = datetime.date.fromisoformat(start) if start else None
    end_date = datetime.date.fromisoformat(end) if end else None

    async with async_session_factory() as session:
        expenses = await query_expenses(
            session,
            user_id=user_id,
            category=parsed.get("category"),
            start_date=start_date,
            end_date=end_date,
        )

    if not expenses:
        await update.effective_message.reply_text("No matching expenses found.")  # type: ignore[union-attr]
        return

    lines = [f"Found {len(expenses)} expenses:\n"]
    for e in expenses:
        lines.append(f"  [{e.id}] {e.date} | ${e.amount} | {e.category} | {e.description}")
    await update.effective_message.reply_text("\n".join(lines))  # type: ignore[union-attr]


async def _handle_expense_summary(update: Update, parsed: dict) -> None:
    user_id = update.effective_user.id  # type: ignore[union-attr]
    period = parsed.get("period", "month")
    start_date, end_date = period_to_dates(period)

    async with async_session_factory() as session:
        summary = await expense_summary(
            session, user_id=user_id, start_date=start_date, end_date=end_date
        )

    if not summary["categories"]:
        await update.effective_message.reply_text(f"No expenses found for {period}.")  # type: ignore[union-attr]
        return

    lines = [f"Spending ({period}):\n"]
    for cat, data in summary["categories"].items():
        lines.append(f"  {cat}: ${data['total']:.2f} ({data['count']} items)")
    lines.append(f"\nTotal: ${summary['grand_total']:.2f}")
    await update.effective_message.reply_text("\n".join(lines))  # type: ignore[union-attr]


async def _handle_set_reminder(update: Update, parsed: dict) -> None:
    user_id = update.effective_user.id  # type: ignore[union-attr]
    message = parsed.get("message", "Reminder")
    remind_at_str = parsed.get("remind_at")

    if not remind_at_str:
        await update.effective_message.reply_text(  # type: ignore[union-attr]
            "I need a time for the reminder. Try: 'Remind me to X at 3pm tomorrow'"
        )
        return

    try:
        remind_at = datetime.datetime.fromisoformat(remind_at_str)
        if remind_at.tzinfo is None:
            remind_at = remind_at.replace(tzinfo=datetime.UTC)
    except ValueError:
        await update.effective_message.reply_text("I couldn't parse that time. Please try again.")  # type: ignore[union-attr]
        return

    recurrence = parsed.get("recurrence", "none")

    async with async_session_factory() as session:
        reminder = await set_reminder(
            session,
            user_id=user_id,
            message=message,
            remind_at=remind_at,
            recurrence=recurrence,
        )

    recur_text = f" (repeats {recurrence})" if recurrence != "none" else ""
    await update.effective_message.reply_text(  # type: ignore[union-attr]
        f"Reminder set: \"{reminder.message}\" at {reminder.remind_at:%Y-%m-%d %H:%M}{recur_text}\n"
        f"ID: {reminder.id}"
    )


async def _handle_list_reminders(update: Update, parsed: dict) -> None:
    user_id = update.effective_user.id  # type: ignore[union-attr]
    async with async_session_factory() as session:
        reminders = await list_reminders(session, user_id=user_id)

    if not reminders:
        await update.effective_message.reply_text("No active reminders.")  # type: ignore[union-attr]
        return

    lines = ["Active reminders:\n"]
    for r in reminders:
        recur = f" (repeats {r.recurrence})" if r.recurrence != "none" else ""
        lines.append(f"  [{r.id}] {r.remind_at:%Y-%m-%d %H:%M} | {r.message}{recur}")
    await update.effective_message.reply_text("\n".join(lines))  # type: ignore[union-attr]


async def _handle_cancel_reminder(update: Update, parsed: dict) -> None:
    user_id = update.effective_user.id  # type: ignore[union-attr]
    reminder_id = parsed.get("reminder_id")
    if not reminder_id:
        await update.effective_message.reply_text("Which reminder? Use /reminders to see IDs.")  # type: ignore[union-attr]
        return

    async with async_session_factory() as session:
        cancelled = await cancel_reminder(session, reminder_id=int(reminder_id), user_id=user_id)

    if cancelled:
        await update.effective_message.reply_text(f"Reminder {reminder_id} cancelled.")  # type: ignore[union-attr]
    else:
        await update.effective_message.reply_text(f"Reminder {reminder_id} not found.")  # type: ignore[union-attr]


async def _handle_help(update: Update, parsed: dict) -> None:
    from src.bot.handlers.start import WELCOME_TEXT

    await update.effective_message.reply_text(WELCOME_TEXT)  # type: ignore[union-attr]


async def _handle_unknown(update: Update, parsed: dict) -> None:
    reply = parsed.get("reply", "I'm not sure what you mean. Try /help for available commands.")
    await update.effective_message.reply_text(reply)  # type: ignore[union-attr]


_INTENT_HANDLERS = {
    "add_expense": _handle_add_expense,
    "query_expenses": _handle_query_expenses,
    "expense_summary": _handle_expense_summary,
    "set_reminder": _handle_set_reminder,
    "list_reminders": _handle_list_reminders,
    "cancel_reminder": _handle_cancel_reminder,
    "help": _handle_help,
    "unknown": _handle_unknown,
}
