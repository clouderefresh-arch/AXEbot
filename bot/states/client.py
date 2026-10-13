"""Шаги создания заявки и уточнения по предложению."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class OrderCreate(StatesGroup):
    """Мастер заявки: описание, фото, срочность, предпросмотр, доп. поля."""

    description = State()
    photo = State()
    urgency = State()
    preview = State()
    extra = State()


class ClientClarify(StatesGroup):
    """Клиент пишет вопрос по уже полученному предложению."""

    text = State()


def is_order_create(state_name: str | None) -> bool:
    return bool(state_name and state_name.startswith(f"{OrderCreate.__name__}:"))
