"""Инлайн-клавиатуры ассистента."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constants import PAGE_SIZE, STATUS_LABELS, STATUS_ORDER
from bot.database.db import Order
from bot.keyboards.callbacks import (
    AdminMenuCB,
    AdminOrderCB,
    PageCB,
    ReplyCB,
    StatusCB,
    inline_button,
)
from bot.services.drafts import ReplyDraft


def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [inline_button("Открытые заявки", AdminMenuCB(action="open"))],
            [inline_button("Все заявки", AdminMenuCB(action="all"))],
            [inline_button("Помощь", AdminMenuCB(action="help"))],
        ]
    )


def reminder_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [inline_button("Открытые заявки", AdminMenuCB(action="open"))],
        ]
    )


def admin_order_keyboard(order: Order) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if order.status == "pending":
        rows.append(
            [inline_button("Взять в работу", AdminOrderCB(action="take", order_id=order.id))]
        )
    if order.status not in {"canceled", "completed"}:
        rows.append(
            [inline_button("Ответить", AdminOrderCB(action="reply", order_id=order.id))]
        )
    rows.append(
        [inline_button("Сменить статус", AdminOrderCB(action="status", order_id=order.id))]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def status_keyboard(order: Order) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for status in STATUS_ORDER:
        if status == order.status:
            continue
        pair.append(
            inline_button(
                STATUS_LABELS[status],
                StatusCB(status=status, order_id=order.id),
            )
        )
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([inline_button("Назад", AdminOrderCB(action="back", order_id=order.id))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_list_keyboard(
    orders: list[Order],
    *,
    scope: str,
    offset: int,
    total: int,
) -> InlineKeyboardMarkup:
    rows = [
        [
            inline_button(
                f"#{order.id} · {_urgency_short(order.urgency)}",
                AdminOrderCB(action="open", order_id=order.id),
            )
        ]
        for order in orders
    ]
    nav: list[InlineKeyboardButton] = []
    if offset > 0:
        nav.append(
            inline_button(
                "Назад",
                PageCB(scope=scope, offset=max(0, offset - PAGE_SIZE)),
            )
        )
    if offset + PAGE_SIZE < total:
        nav.append(
            inline_button(
                "Дальше",
                PageCB(scope=scope, offset=offset + PAGE_SIZE),
            )
        )
    if nav:
        rows.append(nav)
    rows.append([inline_button("В меню", AdminMenuCB(action="menu"))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def builder_keyboard(draft: ReplyDraft) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            inline_button("Цена (в юанях)", ReplyCB(action="price", order_id=draft.order_id)),
            inline_button("Сроки доставки", ReplyCB(action="delivery", order_id=draft.order_id)),
        ],
        [
            inline_button("Комментарий", ReplyCB(action="comment", order_id=draft.order_id)),
            inline_button("Прикрепить фото", ReplyCB(action="photo", order_id=draft.order_id)),
        ],
    ]
    if draft.assistant_photo_id:
        rows.append(
            [
                inline_button(
                    "Убрать фото",
                    ReplyCB(action="clear_photo", order_id=draft.order_id),
                )
            ]
        )
    rows.append(
        [inline_button("Отправить клиенту", ReplyCB(action="send", order_id=draft.order_id))]
    )
    rows.append([inline_button("Отмена", ReplyCB(action="cancel", order_id=draft.order_id))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def builder_input_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [inline_button("Назад", ReplyCB(action="back", order_id=order_id))],
            [inline_button("Отмена", ReplyCB(action="cancel", order_id=order_id))],
        ]
    )


def _urgency_short(urgency: str) -> str:
    return {"urgent": "срочно", "medium": "обычно", "low": "несрочно"}.get(urgency, urgency)
