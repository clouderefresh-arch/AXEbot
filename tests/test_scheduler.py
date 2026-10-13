"""Тихие часы и напоминания."""

import asyncio
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from bot.database import Database
from bot.services.scheduler import ReminderService, is_quiet_hours, setup_scheduler
from tests.conftest import make_settings

TZ = ZoneInfo("Europe/Moscow")


@pytest.mark.parametrize(
    ("hour", "expected"),
    [
        (21, False),
        (22, True),
        (23, True),
        (0, True),
        (8, True),
        (9, False),
        (12, False),
    ],
)
def test_quiet_hours_wrap_midnight(hour: int, expected: bool) -> None:
    moment = datetime(2026, 10, 13, hour, 30, tzinfo=TZ)
    assert is_quiet_hours(moment, 22, 9) is expected


def test_quiet_hours_disabled_when_bounds_match() -> None:
    moment = datetime(2026, 10, 13, 23, tzinfo=TZ)
    assert is_quiet_hours(moment, 9, 9) is False


def test_quiet_hours_require_timezone() -> None:
    with pytest.raises(ValueError):
        is_quiet_hours(datetime(2026, 10, 13, 23), 22, 9)


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, reply_markup: object = None) -> None:
        self.sent.append((chat_id, text))

    async def send_photo(self, chat_id: int, photo: str, caption: str = "", reply_markup: object = None) -> None:
        self.sent.append((chat_id, caption))


def test_reminder_respects_quiet_hours_and_dedup(tmp_path: Path) -> None:
    asyncio.run(_reminder(tmp_path))


async def _reminder(tmp_path: Path) -> None:
    db = Database(str(tmp_path / "bot.db"))
    await db.init()
    settings = make_settings()
    bot = FakeBot()
    service = ReminderService()
    day = datetime(2026, 10, 13, 10, 0, tzinfo=TZ)
    night = datetime(2026, 10, 13, 23, 0, tzinfo=TZ)
    try:
        assert await service.send(bot, db, settings, now=day) is False
        await db.create_order(
            user_id=1,
            user_name="Клиент",
            description="Кроссовки",
            urgency="urgent",
        )
        assert await service.send(bot, db, settings, now=night) is False
        assert await service.send(bot, db, settings, now=day) is True
        assert "Кроссовки" in bot.sent[-1][1]
        later = datetime(2026, 10, 13, 10, 20, tzinfo=TZ)
        assert await service.send(bot, db, settings, now=later) is False
        morning = datetime(2026, 10, 14, 9, 0, tzinfo=TZ)
        assert await service.send(bot, db, settings, now=morning, ignore_quiet=True) is True
    finally:
        await db.close()


def test_scheduler_registers_morning_digest() -> None:
    scheduler = setup_scheduler(FakeBot(), object(), make_settings(), ReminderService())
    assert {job.id for job in scheduler.get_jobs()} == {
        "startup-reminder",
        "open-orders-reminder",
        "morning-digest",
    }


def test_scheduler_skips_digest_without_quiet_hours() -> None:
    scheduler = setup_scheduler(
        FakeBot(),
        object(),
        make_settings(quiet_hours_start=0, quiet_hours_end=0),
        ReminderService(),
    )
    assert {job.id for job in scheduler.get_jobs()} == {
        "startup-reminder",
        "open-orders-reminder",
    }
