from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from src.db.session import async_session_factory
from src.services.reminder import cancel_reminder, list_reminders


async def remind_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /remind -- shows usage. Actual NL parsing happens in conversation handler."""
    if not update.effective_message:
        return
    await update.effective_message.reply_text(
        "To set a reminder, just type naturally:\n"
        '"Remind me to call the dentist tomorrow at 3pm"\n'
        '"Remind me every Monday to submit the report"\n\n'
        "Or use /reminders to list active reminders."
    )


async def reminders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reminders -- list active reminders."""
    if not update.effective_message or not update.effective_user:
        return

    async with async_session_factory() as session:
        reminders = await list_reminders(session, user_id=update.effective_user.id)

    if not reminders:
        await update.effective_message.reply_text("No active reminders.")
        return

    lines = ["Active reminders:\n"]
    for r in reminders:
        recur = f" (repeats {r.recurrence})" if r.recurrence != "none" else ""
        lines.append(f"  [{r.id}] {r.remind_at:%Y-%m-%d %H:%M} | {r.message}{recur}")
    lines.append("\nUse /cancel <id> to cancel a reminder.")

    await update.effective_message.reply_text("\n".join(lines))


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel <reminder_id>."""
    if not update.effective_message or not update.effective_user:
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: /cancel <reminder_id>")
        return

    try:
        reminder_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("Invalid ID. Usage: /cancel <reminder_id>")
        return

    async with async_session_factory() as session:
        cancelled = await cancel_reminder(
            session, reminder_id=reminder_id, user_id=update.effective_user.id
        )

    if cancelled:
        await update.effective_message.reply_text(f"Reminder {reminder_id} cancelled.")
    else:
        await update.effective_message.reply_text(
            f"Reminder {reminder_id} not found or already cancelled."
        )
