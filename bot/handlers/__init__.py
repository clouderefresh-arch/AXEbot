"""Роутеры бота."""

from bot.handlers.admin import router as admin_router
from bot.handlers.client import router as client_router
from bot.handlers.common import router as common_router

__all__ = ["admin_router", "client_router", "common_router"]
