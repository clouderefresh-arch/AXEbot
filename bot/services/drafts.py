"""Черновики заявки клиента и ответа ассистента."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from bot.constants import (
    CLEAR_TOKENS,
    MAX_COMMENT,
    MAX_DELIVERY,
    MAX_DESCRIPTION,
    MAX_EXTRA,
    URGENCIES,
)
from bot.database.db import Order
from bot.services.currency import ConvertedPrice

_EXTRA_FIELDS = frozenset({"budget", "size", "color", "reference_link"})


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _optional_text(raw: str, *, limit: int, label: str) -> str | None:
    text = raw.strip()
    if text.casefold() in CLEAR_TOKENS:
        return None
    if len(text) > limit:
        raise ValueError(f"{label} слишком длинный. Максимум {limit} символов.")
    return text


@dataclass(slots=True)
class OrderDraft:
    """Черновик заявки в FSM до записи в базу."""

    description: str = ""
    urgency: str | None = None
    user_photo_id: str | None = None
    budget: str | None = None
    size: str | None = None
    color: str | None = None
    reference_link: str | None = None
    return_to_preview: bool = False

    def ready(self) -> bool:
        return bool(self.description.strip()) and self.urgency in URGENCIES

    def to_state(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "urgency": self.urgency,
            "user_photo_id": self.user_photo_id,
            "budget": self.budget,
            "size": self.size,
            "color": self.color,
            "reference_link": self.reference_link,
            "return_to_preview": self.return_to_preview,
        }

    @classmethod
    def from_state(cls, data: Mapping[str, Any]) -> OrderDraft:
        urgency = data.get("urgency")
        return cls(
            description=str(data.get("description") or ""),
            urgency=urgency if isinstance(urgency, str) and urgency in URGENCIES else None,
            user_photo_id=_clean(data.get("user_photo_id")),
            budget=_clean(data.get("budget")),
            size=_clean(data.get("size")),
            color=_clean(data.get("color")),
            reference_link=_clean(data.get("reference_link")),
            return_to_preview=bool(data.get("return_to_preview")),
        )

    def with_description(self, text: str) -> OrderDraft:
        cleaned = text.strip()
        if len(cleaned) < 3:
            raise ValueError("Опишите товар чуть подробнее — хотя бы 3 символа.")
        if len(cleaned) > MAX_DESCRIPTION:
            raise ValueError(
                f"Описание слишком длинное. Максимум {MAX_DESCRIPTION} символов."
            )
        return replace(self, description=cleaned)

    def with_photo(self, file_id: str | None) -> OrderDraft:
        return replace(self, user_photo_id=_clean(file_id))

    def with_urgency(self, urgency: str) -> OrderDraft:
        if urgency not in URGENCIES:
            raise ValueError("Выберите срочность кнопкой.")
        return replace(self, urgency=urgency)

    def with_extra(self, field: str, text: str) -> OrderDraft:
        if field not in _EXTRA_FIELDS:
            raise ValueError("Неизвестное поле")
        labels = {
            "budget": "Бюджет",
            "size": "Размер",
            "color": "Цвет",
            "reference_link": "Ссылка",
        }
        value = _optional_text(text, limit=MAX_EXTRA, label=labels[field])
        return replace(self, **{field: value})


@dataclass(slots=True)
class ReplyDraft:
    """Черновик структурированного ответа ассистента."""

    order_id: int
    price_cny: float | None = None
    price_rub: float | None = None
    price_usd: float | None = None
    raw_cny: float | None = None
    delivery_time: str | None = None
    assistant_comment: str | None = None
    assistant_photo_id: str | None = None

    @property
    def can_send(self) -> bool:
        return self.price_cny is not None or bool(self.assistant_comment)

    def to_state(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "price_cny": self.price_cny,
            "price_rub": self.price_rub,
            "price_usd": self.price_usd,
            "raw_cny": self.raw_cny,
            "delivery_time": self.delivery_time,
            "assistant_comment": self.assistant_comment,
            "assistant_photo_id": self.assistant_photo_id,
        }

    @classmethod
    def from_state(cls, data: Mapping[str, Any]) -> ReplyDraft:
        order_id = _as_int(data.get("order_id"))
        if order_id is None:
            raise ValueError("Черновик ответа не найден. Откройте конструктор заново.")
        return cls(
            order_id=order_id,
            price_cny=_as_float(data.get("price_cny")),
            price_rub=_as_float(data.get("price_rub")),
            price_usd=_as_float(data.get("price_usd")),
            raw_cny=_as_float(data.get("raw_cny")),
            delivery_time=_clean(data.get("delivery_time")),
            assistant_comment=_clean(data.get("assistant_comment")),
            assistant_photo_id=_clean(data.get("assistant_photo_id")),
        )

    @classmethod
    def from_order(cls, order: Order) -> ReplyDraft:
        return cls(
            order_id=order.id,
            price_cny=order.price_cny,
            price_rub=order.price_rub,
            price_usd=order.price_usd,
            delivery_time=order.delivery_time,
            assistant_comment=order.assistant_comment,
            assistant_photo_id=order.assistant_photo_id,
        )

    def with_price(self, price: ConvertedPrice) -> ReplyDraft:
        return replace(
            self,
            raw_cny=float(price.raw_cny),
            price_cny=float(price.price_cny),
            price_rub=float(price.price_rub),
            price_usd=float(price.price_usd),
        )

    def without_price(self) -> ReplyDraft:
        return replace(
            self,
            raw_cny=None,
            price_cny=None,
            price_rub=None,
            price_usd=None,
        )

    def with_delivery(self, text: str) -> ReplyDraft:
        return replace(
            self,
            delivery_time=_optional_text(text, limit=MAX_DELIVERY, label="Срок"),
        )

    def with_comment(self, text: str) -> ReplyDraft:
        return replace(
            self,
            assistant_comment=_optional_text(
                text, limit=MAX_COMMENT, label="Комментарий"
            ),
        )

    def with_photo(self, file_id: str | None) -> ReplyDraft:
        return replace(self, assistant_photo_id=_clean(file_id))
