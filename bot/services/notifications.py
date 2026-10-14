"""Отправка карточек клиенту и ассистенту."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup

logger = logging.getLogger(__name__)

_CAPTION_LIMIT = 1024


async def notify_user(
    bot: Bot,
    user_id: int,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    photo_id: str | None = None,
) -> bool:
    try:
        if photo_id and len(text) <= _CAPTION_LIMIT:
            await bot.send_photo(
                user_id,
                photo_id,
                caption=text,
                reply_markup=reply_markup,
            )
        elif photo_id:
            await bot.send_photo(user_id, photo_id)
            await bot.send_message(user_id, text, reply_markup=reply_markup)
        else:
            await bot.send_message(user_id, text, reply_markup=reply_markup)
    except TelegramAPIError:
        logger.warning("Не удалось отправить сообщение пользователю %s", user_id, exc_info=True)
        return False
    return True
