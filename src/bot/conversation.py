from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.config import settings
from src.llm.parser import run_agent

logger = logging.getLogger(__name__)


async def conversation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch-all handler: routes every natural-language message through the agent loop."""
    msg = update.effective_message
    if not msg or not msg.text or not update.effective_user:
        return

    user_id = update.effective_user.id
    if settings.allowed_users and user_id not in settings.allowed_users:
        await msg.reply_text("Sorry, you're not authorized to use this bot.")
        return

    text = msg.text
    logger.info("User %d: '%s'", user_id, text[:80])

    reply = await run_agent(text, user_id)
    await msg.reply_text(reply)
