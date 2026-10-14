"""Настройки бота из окружения и файла .env."""

from __future__ import annotations

from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфиг запуска: токен, ассистент, курсы и тихие часы."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str
    admin_id: int = Field(gt=0)
    cny_to_rub: float = Field(default=12.5, gt=0)
    cny_to_usd: float = Field(default=0.14, gt=0)
    markup_percent: float = Field(default=0, ge=0, le=1000)
    timezone: str = "Europe/Moscow"
    quiet_hours_start: int = Field(default=22, ge=0, le=23)
    quiet_hours_end: int = Field(default=9, ge=0, le=23)
    reminder_interval_minutes: int = Field(default=90, ge=1, le=24 * 60)
    database_path: str = "data/bot.db"

    @field_validator("bot_token")
    @classmethod
    def _token(cls, value: str) -> str:
        cleaned = value.strip()
        if ":" not in cleaned:
            raise ValueError("BOT_TOKEN должен быть токеном Telegram вида 123:ABC")
        return cleaned

    @field_validator("timezone")
    @classmethod
    def _timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Неизвестная временная зона: {value}") from exc
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
