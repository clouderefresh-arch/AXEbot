"""Шаги конструктора ответа ассистента."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class ReplyBuilder(StatesGroup):
    """Черновик ответа хранится в data FSM, состояние — какое поле ждём."""

    menu = State()
    price = State()
    delivery = State()
    comment = State()
    photo = State()


def is_reply_builder(state_name: str | None) -> bool:
    return bool(state_name and state_name.startswith(f"{ReplyBuilder.__name__}:"))
