"""Фильтры ролей."""

from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject

from bot.config import Settings


class IsAdmin(BaseFilter):
    """Пропускает только ассистента из ADMIN_ID."""

    async def __call__(self, event: TelegramObject, settings: Settings) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user is not None and user.id == settings.admin_id)
