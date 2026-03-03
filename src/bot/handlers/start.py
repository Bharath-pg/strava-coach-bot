from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

WELCOME_TEXT = (
    "Hey! I'm your personal assistant bot.\n\n"
    "I can help you with:\n"
    "  - Tracking expenses\n"
    "  - Setting reminders\n\n"
    "Just type naturally, or use commands:\n"
    "/expense <amount> <description> -- add an expense\n"
    "/summary [today|week|month] -- spending summary\n"
    "/remind <message> at <time> -- set a reminder\n"
    "/reminders -- list reminders\n"
    "/cancel <id> -- cancel a reminder\n"
    "/help -- show this message"
)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(WELCOME_TEXT)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(WELCOME_TEXT)
