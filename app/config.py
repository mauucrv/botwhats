"""
Application configuration using Pydantic Settings.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="beauty-salon-bot")
    app_env: str = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://beauty_user:password@localhost:5432/beauty_salon"
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")
    cache_ttl_services: int = Field(default=3600)
    cache_ttl_stylists: int = Field(default=3600)
    cache_ttl_info: int = Field(default=3600)

    # OpenAI
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o-mini")
    openai_vision_model: str = Field(default="gpt-4o")
    openai_whisper_model: str = Field(default="whisper-1")

    # Chatwoot
    chatwoot_base_url: str = Field(default="")
    chatwoot_api_token: str = Field(default="")
    chatwoot_account_id: int = Field(default=1)
    chatwoot_inbox_id: int = Field(default=1)
    chatwoot_webhook_secret: Optional[str] = Field(default=None)

    # Google Calendar
    google_credentials_path: str = Field(default="/app/credentials/google_service_account.json")
    google_calendar_id: str = Field(default="")
    calendar_timezone: str = Field(default="America/Mexico_City")

    # Google Drive
    google_drive_folder_id: str = Field(default="")

    # Rate Limiting
    rate_limit_max_messages: int = Field(default=30)
    rate_limit_window_seconds: int = Field(default=3600)

    # Message grouping
    message_group_delay: int = Field(default=3)

    # Scheduled Jobs
    owner_phone_number: str = Field(default="")
    weekly_report_day: int = Field(default=0)  # Monday
    weekly_report_hour: int = Field(default=9)
    weekly_report_minute: int = Field(default=0)
    daily_reminder_hour: int = Field(default=18)
    daily_reminder_minute: int = Field(default=0)
    daily_backup_hour: int = Field(default=3)
    daily_backup_minute: int = Field(default=0)
    calendar_sync_interval_minutes: int = Field(default=15)

    # Salon defaults
    salon_name: str = Field(default="Salón de Belleza")
    salon_address: str = Field(default="")
    salon_phone: str = Field(default="")
    salon_hours: str = Field(default="Lunes a Sábado: 9:00 AM - 8:00 PM")

    # Security
    secret_key: str = Field(default="change-this-secret-key")
    allowed_origins: str = Field(default="*")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
