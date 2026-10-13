"""Точка входа: бот, база и напоминания."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from bot.config import get_settings
from bot.database import Database
from bot.handlers.admin import router as admin_router
from bot.handlers.client import router as client_router
from bot.handlers.common import router as common_router
from bot.services.currency import CurrencyService
from bot.services.scheduler import ReminderService, setup_scheduler

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = get_settings()
    database = Database(settings.database_path)
    await database.init()
    currency = CurrencyService(settings)
    reminders = ReminderService()
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(
        storage=MemoryStorage(),
        settings=settings,
        db=database,
        currency=currency,
    )
    dispatcher.include_router(common_router)
    dispatcher.include_router(admin_router)
    dispatcher.include_router(client_router)
    dispatcher.errors.register(on_error)
    scheduler = setup_scheduler(bot, database, settings, reminders)
    scheduler.start()
    logger.info("Бот запущен. Тихая зона: %s", settings.timezone)
    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await database.close()
        await bot.session.close()


async def on_error(event: ErrorEvent) -> None:
    logger.exception("Не удалось обработать апдейт: %s", event.exception)


if __name__ == "__main__":
    asyncio.run(main())
