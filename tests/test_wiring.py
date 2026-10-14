"""Импорт каркаса и фильтр ассистента."""

import asyncio
from types import SimpleNamespace

from bot.filters import IsAdmin
from bot.handlers.admin import router as admin_router
from bot.handlers.client import router as client_router
from tests.conftest import make_settings


def test_routers_are_wired() -> None:
    assert admin_router.message.handlers
    assert admin_router.callback_query.handlers
    assert client_router.message.handlers
    assert client_router.callback_query.handlers


def test_is_admin_filter() -> None:
    asyncio.run(_is_admin())


async def _is_admin() -> None:
    settings = make_settings(admin_id=5)
    filt = IsAdmin()
    admin = SimpleNamespace(from_user=SimpleNamespace(id=5))
    client = SimpleNamespace(from_user=SimpleNamespace(id=6))
    empty = SimpleNamespace(from_user=None)
    assert await filt(admin, settings) is True
    assert await filt(client, settings) is False
    assert await filt(empty, settings) is False


def test_main_module_imports() -> None:
    import main

    assert callable(main.main)
