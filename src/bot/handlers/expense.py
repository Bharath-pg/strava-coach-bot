from __future__ import annotations

from decimal import Decimal, InvalidOperation

from telegram import Update
from telegram.ext import ContextTypes

from src.db.session import async_session_factory
from src.services.expense import add_expense, expense_summary, period_to_dates, query_expenses


async def expense_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /expense <amount> [category] [description]."""
    if not update.effective_message or not update.effective_user:
        return

    args = context.args or []
    if not args:
        await update.effective_message.reply_text(
            "Usage: /expense <amount> [category] [description]\n"
            "Example: /expense 25.50 food Lunch at cafe"
        )
        return

    try:
        amount = Decimal(args[0].replace("$", "").replace(",", ""))
    except (InvalidOperation, IndexError):
        await update.effective_message.reply_text("Invalid amount. Example: /expense 25.50 food")
        return

    category = args[1] if len(args) > 1 else "other"
    description = " ".join(args[2:]) if len(args) > 2 else ""

    async with async_session_factory() as session:
        exp = await add_expense(
            session,
            user_id=update.effective_user.id,
            amount=amount,
            category=category,
            description=description,
        )
    await update.effective_message.reply_text(
        f"Recorded: {exp.amount} {exp.currency} on {exp.category}\n"
        f"Date: {exp.date} | ID: {exp.id}"
    )


async def summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /summary [today|week|month|year]."""
    if not update.effective_message or not update.effective_user:
        return

    period = (context.args[0] if context.args else "month").lower()
    start_date, end_date = period_to_dates(period)

    async with async_session_factory() as session:
        summary = await expense_summary(
            session,
            user_id=update.effective_user.id,
            start_date=start_date,
            end_date=end_date,
        )

    if not summary["categories"]:
        await update.effective_message.reply_text(f"No expenses found for period: {period}")
        return

    lines = [f"Spending summary ({period}): {start_date} to {end_date}\n"]
    for cat, data in summary["categories"].items():
        lines.append(f"  {cat}: ${data['total']:.2f} ({data['count']} items)")
    lines.append(f"\nTotal: ${summary['grand_total']:.2f}")

    await update.effective_message.reply_text("\n".join(lines))


async def recent_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /recent [N] -- show N most recent expenses."""
    if not update.effective_message or not update.effective_user:
        return

    limit = 10
    if context.args:
        try:
            limit = min(int(context.args[0]), 50)
        except ValueError:
            pass

    async with async_session_factory() as session:
        expenses = await query_expenses(
            session, user_id=update.effective_user.id, limit=limit
        )

    if not expenses:
        await update.effective_message.reply_text("No expenses recorded yet.")
        return

    lines = [f"Last {len(expenses)} expenses:\n"]
    for e in expenses:
        lines.append(f"  [{e.id}] {e.date} | ${e.amount} | {e.category} | {e.description}")

    await update.effective_message.reply_text("\n".join(lines))
