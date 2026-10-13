"""Напоминания ассистенту об открытых заявках."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from bot.config import Settings
from bot.constants import OPEN_STATUSES
from bot.database.db import Database
from bot.keyboards.admin import reminder_keyboard
from bot.services.formatting import format_reminder
from bot.services.notifications import notify_user

logger = logging.getLogger(__name__)


def is_quiet_hours(moment: datetime, start: int, end: int) -> bool:
    """Тихие часы включительно с start и до end, не включая end.

    Интервал через полночь, если start > end (например 22 → 9).
    Одинаковые границы означают, что тихих часов нет.
    """

    if moment.tzinfo is None:
        raise ValueError("Нужна дата со временной зоной")
    if start == end:
        return False
    hour = moment.hour
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


class ReminderService:
    """Шлёт сводку открытых заявок и не дублирует её чаще чем раз в полчаса."""

    def __init__(self) -> None:
        self._last_sent_at: datetime | None = None

    async def send(
        self,
        bot: Bot,
        db: Database,
        settings: Settings,
        *,
        ignore_quiet: bool = False,
        now: datetime | None = None,
    ) -> bool:
        tz = ZoneInfo(settings.timezone)
        current = now.astimezone(tz) if now is not None else datetime.now(tz)
        if not ignore_quiet and is_quiet_hours(
            current,
            settings.quiet_hours_start,
            settings.quiet_hours_end,
        ):
            logger.debug("Напоминание пропущено: тихие часы")
            return False
        if self._last_sent_at is not None:
            gap = current - self._last_sent_at.astimezone(tz)
            guard = timedelta(minutes=min(30, settings.reminder_interval_minutes))
            if gap < guard:
                return False

        orders = await db.list_orders(statuses=OPEN_STATUSES, limit=20, order="asc")
        if not orders:
            return False
        total = await db.count_orders(statuses=OPEN_STATUSES)
        sent = await notify_user(
            bot,
            settings.admin_id,
            format_reminder(orders, total=total, moment=current),
            reply_markup=reminder_keyboard(),
        )
        if not sent:
            return False
        self._last_sent_at = current
        return True


def setup_scheduler(
    bot: Bot,
    db: Database,
    settings: Settings,
    reminders: ReminderService,
) -> AsyncIOScheduler:
    tz = ZoneInfo(settings.timezone)
    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(
        reminders.send,
        DateTrigger(run_date=datetime.now(tz) + timedelta(seconds=10)),
        kwargs={"bot": bot, "db": db, "settings": settings, "ignore_quiet": False},
        id="startup-reminder",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        reminders.send,
        IntervalTrigger(minutes=settings.reminder_interval_minutes, timezone=tz),
        kwargs={"bot": bot, "db": db, "settings": settings, "ignore_quiet": False},
        id="open-orders-reminder",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    if settings.quiet_hours_start != settings.quiet_hours_end:
        scheduler.add_job(
            reminders.send,
            CronTrigger(hour=settings.quiet_hours_end, minute=0, timezone=tz),
            kwargs={"bot": bot, "db": db, "settings": settings, "ignore_quiet": True},
            id="morning-digest",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
    return scheduler
