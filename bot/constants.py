"""Общие константы заявок и подписей."""

from __future__ import annotations

URGENCY_URGENT = "urgent"
URGENCY_MEDIUM = "medium"
URGENCY_LOW = "low"

URGENCIES: frozenset[str] = frozenset(
    {URGENCY_URGENT, URGENCY_MEDIUM, URGENCY_LOW}
)

URGENCY_LABELS: dict[str, str] = {
    URGENCY_URGENT: "Срочно",
    URGENCY_MEDIUM: "Средний приоритет",
    URGENCY_LOW: "Не срочно",
}

STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in_progress"
STATUS_ANSWERED = "answered"
STATUS_APPROVED = "approved"
STATUS_COMPLETED = "completed"
STATUS_CANCELED = "canceled"

STATUSES: frozenset[str] = frozenset(
    {
        STATUS_PENDING,
        STATUS_IN_PROGRESS,
        STATUS_ANSWERED,
        STATUS_APPROVED,
        STATUS_COMPLETED,
        STATUS_CANCELED,
    }
)

STATUS_ORDER: tuple[str, ...] = (
    STATUS_PENDING,
    STATUS_IN_PROGRESS,
    STATUS_ANSWERED,
    STATUS_APPROVED,
    STATUS_COMPLETED,
    STATUS_CANCELED,
)

STATUS_LABELS: dict[str, str] = {
    STATUS_PENDING: "Ожидает",
    STATUS_IN_PROGRESS: "В работе",
    STATUS_ANSWERED: "Есть предложение",
    STATUS_APPROVED: "Клиент принял",
    STATUS_COMPLETED: "Завершена",
    STATUS_CANCELED: "Отменена",
}

OPEN_STATUSES: tuple[str, ...] = (STATUS_PENDING, STATUS_IN_PROGRESS)

CLOSED_STATUSES: frozenset[str] = frozenset({STATUS_COMPLETED, STATUS_CANCELED})

MAX_DESCRIPTION = 1500
MAX_EXTRA = 300
MAX_COMMENT = 1000
MAX_DELIVERY = 200

CLEAR_TOKENS: frozenset[str] = frozenset({"-", "—", "нет", "очистить", "удалить"})

PAGE_SIZE = 5
