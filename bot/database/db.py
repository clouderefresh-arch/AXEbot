"""Инициализация SQLite и CRUD заявок."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from bot.constants import STATUSES, URGENCIES

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    user_name TEXT,
    description TEXT NOT NULL,
    user_photo_id TEXT,
    urgency TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    budget TEXT,
    size TEXT,
    color TEXT,
    reference_link TEXT,
    price_cny REAL,
    price_rub REAL,
    price_usd REAL,
    delivery_time TEXT,
    assistant_comment TEXT,
    assistant_photo_id TEXT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    CHECK (urgency IN ('urgent', 'medium', 'low')),
    CHECK (
        status IN (
            'pending',
            'in_progress',
            'answered',
            'approved',
            'completed',
            'canceled'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
"""

_UPDATABLE = frozenset(
    {
        "status",
        "price_cny",
        "price_rub",
        "price_usd",
        "delivery_time",
        "assistant_comment",
        "assistant_photo_id",
    }
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Order:
    """Строка таблицы orders."""

    id: int
    user_id: int
    user_name: str | None
    description: str
    user_photo_id: str | None
    urgency: str
    status: str
    budget: str | None
    size: str | None
    color: str | None
    reference_link: str | None
    price_cny: float | None
    price_rub: float | None
    price_usd: float | None
    delivery_time: str | None
    assistant_comment: str | None
    assistant_photo_id: str | None
    created_at: str
    updated_at: str | None

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Order:
        return cls(
            id=int(row["id"]),
            user_id=int(row["user_id"]),
            user_name=row["user_name"],
            description=str(row["description"]),
            user_photo_id=row["user_photo_id"],
            urgency=str(row["urgency"]),
            status=str(row["status"]),
            budget=row["budget"],
            size=row["size"],
            color=row["color"],
            reference_link=row["reference_link"],
            price_cny=row["price_cny"],
            price_rub=row["price_rub"],
            price_usd=row["price_usd"],
            delivery_time=row["delivery_time"],
            assistant_comment=row["assistant_comment"],
            assistant_photo_id=row["assistant_photo_id"],
            created_at=str(row["created_at"]),
            updated_at=row["updated_at"],
        )


class Database:
    """Асинхронный доступ к SQLite через aiosqlite."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def init(self) -> None:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON")
        await self._conn.execute("PRAGMA journal_mode = WAL")
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def connection(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("База данных не инициализирована")
        return self._conn

    async def create_order(
        self,
        *,
        user_id: int,
        user_name: str | None,
        description: str,
        urgency: str,
        user_photo_id: str | None = None,
        budget: str | None = None,
        size: str | None = None,
        color: str | None = None,
        reference_link: str | None = None,
    ) -> Order:
        if urgency not in URGENCIES:
            raise ValueError("Неизвестная срочность")
        now = utc_now()
        cursor = await self.connection.execute(
            """
            INSERT INTO orders (
                user_id, user_name, description, user_photo_id, urgency, status,
                budget, size, color, reference_link, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                user_name,
                description,
                user_photo_id,
                urgency,
                budget,
                size,
                color,
                reference_link,
                now,
                now,
            ),
        )
        await self.connection.commit()
        order_id = cursor.lastrowid
        if order_id is None:
            raise RuntimeError("SQLite не вернул id заявки")
        created = await self.get_order(int(order_id))
        if created is None:
            raise RuntimeError("Заявка не найдена сразу после создания")
        return created

    async def get_order(self, order_id: int) -> Order | None:
        cursor = await self.connection.execute(
            "SELECT * FROM orders WHERE id = ?",
            (order_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return Order.from_row(row)

    async def update_order(self, order_id: int, **fields: Any) -> Order | None:
        unknown = set(fields) - _UPDATABLE
        if unknown:
            raise ValueError(f"Нельзя обновить поля: {', '.join(sorted(unknown))}")
        if not fields:
            return await self.get_order(order_id)
        if "status" in fields and fields["status"] not in STATUSES:
            raise ValueError("Неизвестный статус")
        fields = dict(fields)
        fields["updated_at"] = utc_now()
        assignments = ", ".join(f"{column} = ?" for column in fields)
        values = [*fields.values(), order_id]
        cursor = await self.connection.execute(
            f"UPDATE orders SET {assignments} WHERE id = ?",
            values,
        )
        await self.connection.commit()
        if cursor.rowcount == 0:
            return None
        return await self.get_order(order_id)

    async def list_orders(
        self,
        *,
        user_id: int | None = None,
        statuses: Sequence[str] | None = None,
        limit: int = 10,
        offset: int = 0,
        order: str = "desc",
    ) -> list[Order]:
        where, params = _filters(user_id=user_id, statuses=statuses)
        direction = "ASC" if order == "asc" else "DESC"
        limit = max(1, min(int(limit), 50))
        offset = max(0, int(offset))
        cursor = await self.connection.execute(
            f"SELECT * FROM orders{where} ORDER BY id {direction} LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        rows = await cursor.fetchall()
        return [Order.from_row(row) for row in rows]

    async def count_orders(
        self,
        *,
        user_id: int | None = None,
        statuses: Sequence[str] | None = None,
    ) -> int:
        where, params = _filters(user_id=user_id, statuses=statuses)
        cursor = await self.connection.execute(
            f"SELECT COUNT(*) AS total FROM orders{where}",
            params,
        )
        row = await cursor.fetchone()
        if row is None:
            return 0
        return int(row["total"])


def _filters(
    *,
    user_id: int | None,
    statuses: Sequence[str] | None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if user_id is not None:
        clauses.append("user_id = ?")
        params.append(user_id)
    if statuses:
        marks = ", ".join("?" for _ in statuses)
        clauses.append(f"status IN ({marks})")
        params.extend(statuses)
    if not clauses:
        return "", params
    return " WHERE " + " AND ".join(clauses), params
