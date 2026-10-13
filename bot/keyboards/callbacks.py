"""CallbackData для инлайн-кнопок."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton


class ClientMenuCB(CallbackData, prefix="cm"):
    action: str


class CreateCB(CallbackData, prefix="cr"):
    action: str
    value: str = "-"


class PageCB(CallbackData, prefix="pg"):
    scope: str
    offset: int


class ClientOrderCB(CallbackData, prefix="co"):
    action: str
    order_id: int


class AdminMenuCB(CallbackData, prefix="am"):
    action: str


class AdminOrderCB(CallbackData, prefix="ao"):
    action: str
    order_id: int


class StatusCB(CallbackData, prefix="ss"):
    status: str
    order_id: int


class ReplyCB(CallbackData, prefix="rp"):
    action: str
    order_id: int


def inline_button(text: str, data: CallbackData) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data.pack())
