"""Инлайн-клавиатуры клиента."""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot.constants import URGENCY_LABELS, URGENCY_LOW, URGENCY_MEDIUM, URGENCY_URGENT
from bot.database.db import Order
from bot.keyboards.callbacks import (
    ClientMenuCB,
    ClientOrderCB,
    CreateCB,
    PageCB,
    inline_button,
)

_CANCEL = inline_button("Отмена", CreateCB(action="cancel"))

BTN_NEW = "Новая заявка"
BTN_LIST = "Мои заявки"
BTN_HELP = "Помощь"
BTN_SKIP = "Пропустить"
BTN_CANCEL = "Отмена"
BTN_SEND = "Отправить заявку"
BTN_EXTRAS = "Дополнительные параметры"
BTN_EDIT_DESC = "Изменить описание"
BTN_EDIT_PHOTO = "Изменить фото"
BTN_EDIT_URGENCY = "Изменить срочность"
BTN_BACK = "Назад"
BTN_BUDGET = "Бюджет"
BTN_SIZE = "Размер"
BTN_COLOR = "Цвет"
BTN_LINK = "Ссылка"

EXTRA_REPLY_FIELDS = {
    BTN_BUDGET: "budget",
    BTN_SIZE: "size",
    BTN_COLOR: "color",
    BTN_LINK: "link",
}


def _reply(*rows: list[str]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=label) for label in row] for row in rows],
        resize_keyboard=True,
    )


def client_reply_menu() -> ReplyKeyboardMarkup:
    return _reply([BTN_NEW], [BTN_LIST, BTN_HELP])


def description_reply_kb() -> ReplyKeyboardMarkup:
    return _reply([BTN_CANCEL])


def photo_reply_kb() -> ReplyKeyboardMarkup:
    return _reply([BTN_SKIP], [BTN_CANCEL])


def urgency_reply_kb() -> ReplyKeyboardMarkup:
    return _reply(
        [URGENCY_LABELS[URGENCY_URGENT]],
        [URGENCY_LABELS[URGENCY_MEDIUM]],
        [URGENCY_LABELS[URGENCY_LOW]],
        [BTN_CANCEL],
    )


def preview_reply_kb() -> ReplyKeyboardMarkup:
    return _reply(
        [BTN_SEND],
        [BTN_EXTRAS],
        [BTN_EDIT_DESC, BTN_EDIT_PHOTO],
        [BTN_EDIT_URGENCY],
        [BTN_CANCEL],
    )


def extras_reply_kb() -> ReplyKeyboardMarkup:
    return _reply([BTN_BUDGET, BTN_SIZE], [BTN_COLOR, BTN_LINK], [BTN_BACK])


def extra_input_reply_kb() -> ReplyKeyboardMarkup:
    return _reply([BTN_BACK], [BTN_CANCEL])


def client_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [inline_button("Новая заявка", ClientMenuCB(action="new"))],
            [inline_button("Мои заявки", ClientMenuCB(action="list"))],
            [inline_button("Помощь", ClientMenuCB(action="help"))],
        ]
    )


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_CANCEL]])


def photo_keyboard(*, editing: bool, has_photo: bool) -> InlineKeyboardMarkup:
    rows = []
    if editing:
        rows.append([inline_button("Оставить как есть", CreateCB(action="skip_photo"))])
        if has_photo:
            rows.append([inline_button("Удалить фото", CreateCB(action="clear_photo"))])
    else:
        rows.append([inline_button("Пропустить", CreateCB(action="skip_photo"))])
    rows.append([_CANCEL])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def urgency_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                inline_button(
                    URGENCY_LABELS[URGENCY_URGENT],
                    CreateCB(action="urgency", value=URGENCY_URGENT),
                )
            ],
            [
                inline_button(
                    URGENCY_LABELS[URGENCY_MEDIUM],
                    CreateCB(action="urgency", value=URGENCY_MEDIUM),
                )
            ],
            [
                inline_button(
                    URGENCY_LABELS[URGENCY_LOW],
                    CreateCB(action="urgency", value=URGENCY_LOW),
                )
            ],
            [_CANCEL],
        ]
    )


def preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [inline_button("Дополнительные параметры", CreateCB(action="extras"))],
            [
                inline_button("Изменить описание", CreateCB(action="edit_desc")),
                inline_button("Изменить фото", CreateCB(action="edit_photo")),
            ],
            [inline_button("Изменить срочность", CreateCB(action="edit_urgency"))],
            [inline_button("Отправить заявку", CreateCB(action="send"))],
            [_CANCEL],
        ]
    )


def extras_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                inline_button("Бюджет", CreateCB(action="field", value="budget")),
                inline_button("Размер", CreateCB(action="field", value="size")),
            ],
            [
                inline_button("Цвет", CreateCB(action="field", value="color")),
                inline_button("Ссылка", CreateCB(action="field", value="link")),
            ],
            [inline_button("Назад", CreateCB(action="back"))],
        ]
    )


def extra_input_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [inline_button("Назад", CreateCB(action="back"))],
            [_CANCEL],
        ]
    )


def client_list_keyboard(
    orders: list[Order],
    *,
    offset: int,
    limit: int,
    total: int,
) -> InlineKeyboardMarkup:
    rows = [
        [
            inline_button(
                f"#{order.id} · {_urgency_short(order.urgency)}",
                ClientOrderCB(action="open", order_id=order.id),
            )
        ]
        for order in orders
    ]
    nav = _nav_row(scope="my", offset=offset, limit=limit, total=total)
    if nav:
        rows.append(nav)
    rows.append([inline_button("В меню", ClientMenuCB(action="menu"))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def client_order_keyboard(order: Order) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if order.status in {"pending", "in_progress"}:
        rows.append(
            [inline_button("Отменить заявку", ClientOrderCB(action="cancel", order_id=order.id))]
        )
    if order.status == "answered":
        rows.append(
            [
                inline_button("Принять", ClientOrderCB(action="accept", order_id=order.id)),
                inline_button("Отклонить", ClientOrderCB(action="reject", order_id=order.id)),
            ]
        )
        rows.append(
            [inline_button("Уточнить", ClientOrderCB(action="ask", order_id=order.id))]
        )
    rows.append([inline_button("К списку", ClientMenuCB(action="list"))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def offer_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                inline_button("Принять", ClientOrderCB(action="accept", order_id=order_id)),
                inline_button("Отклонить", ClientOrderCB(action="reject", order_id=order_id)),
            ],
            [inline_button("Уточнить", ClientOrderCB(action="ask", order_id=order_id))],
            [inline_button("Мои заявки", ClientMenuCB(action="list"))],
        ]
    )


def confirm_keyboard(order_id: int, *, yes_action: str, yes_text: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [inline_button(yes_text, ClientOrderCB(action=yes_action, order_id=order_id))],
            [inline_button("Назад", ClientOrderCB(action="open", order_id=order_id))],
        ]
    )


def _nav_row(
    *,
    scope: str,
    offset: int,
    limit: int,
    total: int,
) -> list[InlineKeyboardButton]:
    row: list[InlineKeyboardButton] = []
    if offset > 0:
        row.append(
            inline_button(
                "Назад",
                PageCB(scope=scope, offset=max(0, offset - limit)),
            )
        )
    if offset + limit < total:
        row.append(
            inline_button(
                "Дальше",
                PageCB(scope=scope, offset=offset + limit),
            )
        )
    return row


def _urgency_short(urgency: str) -> str:
    return {"urgent": "срочно", "medium": "обычно", "low": "несрочно"}.get(urgency, urgency)
