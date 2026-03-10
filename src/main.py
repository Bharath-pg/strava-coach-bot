from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)

from src.bot.conversation import conversation_handler
from src.bot.handlers.reminder import cancel_handler, remind_handler, reminders_handler
from src.bot.handlers.start import help_handler, start_handler
from src.config import settings
from src.db.session import async_session_factory
from src.services.reminder import advance_or_deactivate, get_due_reminders
from src.services.weekly_checkin import send_weekly_checkin

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


async def weekly_checkin_job(app) -> None:  # type: ignore[no-untyped-def]
    """Scheduled job: send weekly Strava training check-in."""
    if not settings.allowed_user_ids.strip():
        logger.warning("No ALLOWED_USER_IDS set, skipping weekly check-in")
        return
    for uid in settings.allowed_users:
        try:
            await send_weekly_checkin(app, chat_id=uid)
        except Exception:
            logger.exception("Failed to send weekly check-in to %d", uid)


async def post_init(app) -> None:  # type: ignore[no-untyped-def]
    """Called after the Application is initialized and the event loop is running."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders, "interval", seconds=30, args=[app])

    if settings.strava_client_id:
        scheduler.add_job(
            weekly_checkin_job,
            "cron",
            day_of_week="sun",
            hour=13,
            minute=30,
            args=[app],
        )
        logger.info("Weekly Strava check-in scheduled (Sun 13:30 UTC / 7:00 PM IST)")

    scheduler.start()
    logger.info("Reminder scheduler started (30s interval)")


def main() -> None:
    app = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("remind", remind_handler))
    app.add_handler(CommandHandler("reminders", reminders_handler))
    app.add_handler(CommandHandler("cancel", cancel_handler))

    # Catch-all for natural language → agent loop
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, conversation_handler))

    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
