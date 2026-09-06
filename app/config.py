"""Application Configuration using Pydantic Settings."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = "mock_telegram_token"

    # Anthropic / Claude Agent SDK
    ANTHROPIC_API_KEY: str = "mock_anthropic_key"
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./kirana.db"
    TEST_DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"

    # Shop Defaults
    DEFAULT_SHOP_NAME: str = "Zenz Mart"
    DEFAULT_SHOP_GSTIN: str = "27AABCM1234F1Z8"
    DEFAULT_SHOP_ADDRESS: str = "Shop #4, Market Road, Sector 14, Pune, Maharashtra 411044"
    DEFAULT_SHOP_PHONE: str = "+91 98765 43210"
    DEFAULT_PAYMENT_METHOD: str = "UPI"

    # File Storage
    INVOICE_STORAGE_DIR: str = "./generated/invoices"
    REPORT_STORAGE_DIR: str = "./generated/reports"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_invoice_path(self, filename: str) -> Path:
        path = Path(self.INVOICE_STORAGE_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path / filename

    def get_report_path(self, filename: str) -> Path:
        path = Path(self.REPORT_STORAGE_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path / filename


settings = Settings()
