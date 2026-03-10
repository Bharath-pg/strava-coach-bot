from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

WELCOME_TEXT = (
    "Hey! I'm your running coach & assistant bot.\n\n"
    "Just talk to me naturally -- I'll figure out what to do.\n\n"
    "Things I can help with:\n"
    "  - Training plans: create, view, and edit plans\n"
    "  - Run details: how your runs compare to the plan\n"
    "  - Strava: activity history, weekly check-in\n"
    "  - Reminders: set, list, cancel\n\n"
    "Examples:\n"
    '  "Create a 5K plan for sub-30 starting next Monday"\n'
    '  "What should I run today?"\n'
    '  "How was my run yesterday?"\n'
    '  "How is my training going this week?"\n'
    '  "Move Thursday\'s run to Friday"\n'
    '  "Remind me to stretch at 7am daily"\n\n'
    "Slash commands:\n"
    "  /remind /reminders /cancel\n\n"
    "/help -- show this message"
)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(WELCOME_TEXT)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(WELCOME_TEXT)
