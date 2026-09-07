"""Keep-Alive Background Worker for Cloud Hosting (Render / Koyeb / HF).

Prevents free-tier instances (like Render Free Web Service) from spinning down
after 15 minutes of inactivity by sending an HTTP GET request to its public URL
every 10 minutes (600 seconds).
"""

import logging
import os
import threading
import time
import urllib.request

logger = logging.getLogger(__name__)

# Ping every 10 minutes (600 seconds) - well under Render's 15-minute inactivity limit
PING_INTERVAL_SECONDS = int(os.getenv("KEEP_ALIVE_INTERVAL", "600"))


def _ping_loop(url: str, interval: int):
    """Background worker loop that periodically pings the public URL to prevent sleep."""
    logger.info(f"🔄 Keep-alive worker started. Pinging {url} every {interval // 60}m.")
    # Wait 30 seconds after startup before the first ping
    time.sleep(30)

    while True:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "ZenzMart-KeepAlive/1.0"}
            )
            with urllib.request.urlopen(req, timeout=25) as response:
                status = response.getcode()
                logger.info(f"💓 Keep-alive ping successful -> {url} [HTTP {status}]")
        except Exception as e:
            logger.warning(f"⚠️ Keep-alive ping to {url} encountered: {e}")

        time.sleep(interval)


def start_keep_alive_if_configured():
    """Starts the keep-alive background daemon thread if running in a cloud environment."""
    target_url = (
        os.getenv("KEEP_ALIVE_URL")
        or os.getenv("RENDER_EXTERNAL_URL")
        or "https://zenz-mart-bot.onrender.com"
    )

    # Start if running in cloud (PORT or RENDER set) or if explicitly requested
    is_cloud = bool(
        os.getenv("PORT")
        or os.getenv("RENDER")
        or os.getenv("RENDER_EXTERNAL_URL")
        or os.getenv("KEEP_ALIVE_ENABLED") == "1"
    )

    if not is_cloud:
        logger.info("Local environment detected. Self-ping keep-alive worker is disabled.")
        return

    thread = threading.Thread(
        target=_ping_loop,
        args=(target_url, PING_INTERVAL_SECONDS),
        daemon=True,
        name="KeepAliveThread",
    )
    thread.start()
    logger.info(f"Keep-alive thread initialized for {target_url}")
