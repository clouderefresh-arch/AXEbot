"""SQLite CRUD заявок."""

import asyncio
from pathlib import Path

import pytest

from bot.database import Database


def test_orders_crud(tmp_path: Path) -> None:
    asyncio.run(_orders_crud(tmp_path))


async def _orders_crud(tmp_path: Path) -> None:
    db = Database(str(tmp_path / "bot.db"))
    await db.init()
    try:
        created = await db.create_order(
            user_id=100,
            user_name="Анна (@anna)",
            description="Сумка",
            urgency="medium",
            budget="до 3000",
        )
        assert created.id == 1
        assert created.status == "pending"
        other = await db.create_order(
            user_id=200,
            user_name="Борис",
            description="Часы",
            urgency="urgent",
        )
        own = await db.list_orders(user_id=100)
        assert [item.id for item in own] == [created.id]
        open_orders = await db.list_orders(statuses=("pending", "in_progress"), order="asc")
        assert [item.id for item in open_orders] == [created.id, other.id]
        updated = await db.update_order(
            created.id,
            status="answered",
            price_cny=115.0,
            price_rub=1472.0,
            price_usd=16.1,
            delivery_time="10-14 дней",
            assistant_comment="Нашлась",
        )
        assert updated is not None
        assert updated.price_rub == 1472.0
        assert updated.assistant_comment == "Нашлась"
        assert await db.count_orders(statuses=("answered",)) == 1
        with pytest.raises(ValueError):
            await db.update_order(created.id, status="shipped")
    finally:
        await db.close()
