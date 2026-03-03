from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from src.bot.conversation import conversation_handler
from src.bot.handlers.expense import expense_handler, recent_handler, summary_handler
from src.bot.handlers.reminder import cancel_handler, remind_handler, reminders_handler
from src.bot.handlers.start import help_handler, start_handler
from src.config import settings
from src.db.session import async_session_factory
from src.services.reminder import advance_or_deactivate, get_due_reminders

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
)
logger = logging.getLogger(__name__)


async def check_reminders(app) -> None:  # type: ignore[no-untyped-def]
    """Periodic job: fire due reminders and notify users."""
    async with async_session_factory() as session:
        due = await get_due_reminders(session)
        for reminder in due:
            try:
                await app.bot.send_message(
                    chat_id=reminder.user_id,
                    text=f"Reminder: {reminder.message}",
                )
                await advance_or_deactivate(session, reminder)
            except Exception:
                logger.exception("Failed to send reminder %d", reminder.id)


def main() -> None:
    app = ApplicationBuilder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("expense", expense_handler))
    app.add_handler(CommandHandler("summary", summary_handler))
    app.add_handler(CommandHandler("recent", recent_handler))
    app.add_handler(CommandHandler("remind", remind_handler))
    app.add_handler(CommandHandler("reminders", reminders_handler))
    app.add_handler(CommandHandler("cancel", cancel_handler))

    # Catch-all for natural language
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, conversation_handler))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders, "interval", seconds=30, args=[app])
    scheduler.start()

    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
