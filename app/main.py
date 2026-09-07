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


import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from app.core.keep_alive import start_keep_alive_if_configured


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(b'{"status":"ok","service":"Zenz Mart Supermarket Ops Agent","bot":"online"}\n')

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()

    def log_message(self, format, *args):
        # Suppress access logs to keep bot terminal clean
        pass


def start_health_server_if_needed():
    """Start a lightweight background HTTP server if PORT environment variable is present."""
    port_env = os.getenv("PORT") or os.getenv("SERVER_PORT")
    if port_env:
        try:
            port = int(port_env)
            server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            logger.info(f"Health check HTTP server started on port {port}")
        except Exception as e:
            logger.warning(f"Could not start health server on port {port_env}: {e}")


def main():
    """Main execution function."""
    print("=" * 60)
    print("🚀 Starting Supermarket Ops Agent (Kirana Store Telegram Bot)")
    print(f"🏪 Shop: {settings.DEFAULT_SHOP_NAME}")
    print(f"🧾 GSTIN: {settings.DEFAULT_SHOP_GSTIN}")
    print("=" * 60)

    # Start health server for cloud platforms (Render / Koyeb / Hugging Face)
    start_health_server_if_needed()

    # Start automatic self-ping keep-alive loop to prevent Render sleeping
    start_keep_alive_if_configured()

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
