"""Общие фикстуры тестов."""

from __future__ import annotations

from bot.config import Settings


def make_settings(**overrides: object) -> Settings:
    payload: dict[str, object] = {
        "bot_token": "123456:TESTTOKEN",
        "admin_id": 42,
        "_env_file": None,
    }
    payload.update(overrides)
    return Settings(**payload)
