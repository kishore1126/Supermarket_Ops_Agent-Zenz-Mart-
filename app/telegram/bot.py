"""Telegram Bot Application Factory."""

import logging
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.config import settings
from app.telegram.handlers import (
    callback_query_handler,
    help_command,
    new_command,
    start_command,
    text_message_handler,
)

logger = logging.getLogger(__name__)


def create_bot_app(token: str | None = None) -> Application:
    """Initialize and configure the python-telegram-bot Application."""
    bot_token = token or settings.TELEGRAM_BOT_TOKEN
    app = ApplicationBuilder().token(bot_token).build()

    # Command Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("new", new_command))

    # Callback Query Handler (for inline buttons: Confirm, Cancel, Download PDF)
    app.add_handler(CallbackQueryHandler(callback_query_handler))

    # Main Conversational Text Handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))

    logger.info("Telegram Bot handlers registered successfully.")
    return app
