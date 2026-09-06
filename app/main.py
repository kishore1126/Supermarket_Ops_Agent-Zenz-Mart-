"""Application Entrypoint: Initializes database, seeds SKUs if empty, and starts Telegram bot."""

import asyncio
import logging
import sys
from app.config import settings
from app.core.db import init_db
from app.scripts.seed import seed_database
from app.telegram.bot import create_bot_app

# UTF-8 stdout configuration for Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def startup():
    """Perform startup checks, table initialization, and SKU seeding."""
    logger.info("Initializing database...")
    await init_db()
    
    # Run seed script to ensure catalog has realistic SKUs
    try:
        await seed_database()
    except Exception as e:
        logger.warning(f"Seed note: {e}")


def main():
    """Main execution function."""
    print("=" * 60)
    print("🚀 Starting Supermarket Ops Agent (Kirana Store Telegram Bot)")
    print(f"🏪 Shop: {settings.DEFAULT_SHOP_NAME}")
    print(f"🧾 GSTIN: {settings.DEFAULT_SHOP_GSTIN}")
    print("=" * 60)

    # Run database initialization
    asyncio.run(startup())

    if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN.startswith("mock"):
        logger.warning(
            "TELEGRAM_BOT_TOKEN is not set or using mock value in .env. "
            "Please set a valid token from @BotFather to run live on Telegram."
        )
        print("\nℹ️ To run live: Add TELEGRAM_BOT_TOKEN and ANTHROPIC_API_KEY in .env file.")
        return

    # Build and start the bot polling loop
    logger.info("Starting Telegram bot polling loop...")
    bot_app = create_bot_app()
    bot_app.run_polling()


if __name__ == "__main__":
    main()
