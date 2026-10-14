"""Меню заявки в чате: кнопка поля, затем ручной ввод."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import AnswerCallbackQuery, EditMessageReplyMarkup, SendMessage, TelegramMethod
from aiogram.methods.base import TelegramType
from aiogram.types import CallbackQuery, Chat, Document, Message, PhotoSize, Update, User

from bot.handlers.client import router as client_router
from bot.keyboards.callbacks import CreateCB
from bot.states.client import OrderCreate

_USER_ID = 12


class RecordingSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[TelegramMethod[Any]] = []

    async def close(self) -> None:
        return None

    async def stream_content(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        timeout: int = 30,
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes, None]:
        yield b""

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,
    ) -> TelegramType:
        self.calls.append(method)
        if isinstance(method, SendMessage):
            return Message(
                message_id=len(self.calls) + 50,
                date=datetime.now(timezone.utc),
                chat=Chat(id=method.chat_id, type="private"),
                text=method.text,
            )
        if isinstance(method, (AnswerCallbackQuery, EditMessageReplyMarkup)):
            return True
        raise AssertionError(type(method).__name__)


class Wizard:
    def __init__(self) -> None:
        self.session = RecordingSession()
        self.bot = Bot(token="123456:TESTTOKEN", session=self.session)
        self.dispatcher = Dispatcher(storage=MemoryStorage())
        self.dispatcher.include_router(client_router)
        self._update_id = 0

    async def send(self, user_id: int, **payload: object) -> None:
        self._update_id += 1
        message = Message(
            message_id=self._update_id,
            date=datetime.now(timezone.utc),
            chat=Chat(id=user_id, type="private"),
            from_user=User(id=user_id, is_bot=False, first_name="Клиент"),
            **payload,
        )
        await self.dispatcher.feed_update(
            self.bot,
            Update(update_id=self._update_id, message=message),
        )

    async def tap(self, user_id: int, data: str) -> None:
        self._update_id += 1
        query = CallbackQuery(
            id=f"cb{self._update_id}",
            from_user=User(id=user_id, is_bot=False, first_name="Клиент"),
            chat_instance="test",
            data=data,
            message=Message(
                message_id=self._update_id,
                date=datetime.now(timezone.utc),
                chat=Chat(id=user_id, type="private"),
                text="меню",
            ),
        )
        await self.dispatcher.feed_update(
            self.bot,
            Update(update_id=self._update_id, callback_query=query),
        )

    def state(self, user_id: int) -> FSMContext:
        return FSMContext(
            storage=self.dispatcher.storage,
            key=StorageKey(bot_id=self.bot.id, chat_id=user_id, user_id=user_id),
        )

    def texts(self) -> list[SendMessage]:
        return [call for call in self.session.calls if isinstance(call, SendMessage)]


def _labels(method: SendMessage) -> list[str]:
    markup = method.reply_markup
    assert markup is not None and hasattr(markup, "inline_keyboard")
    return [button.text for row in markup.inline_keyboard for button in row]


def _photo(file_id: str) -> PhotoSize:
    return PhotoSize(file_id=file_id, file_unique_id=file_id, width=8, height=8)


def test_order_menu_collects_fields_from_chat_buttons() -> None:
    asyncio.run(_order_menu())


async def _order_menu() -> None:
    wizard = Wizard()
    try:
        await _fields(wizard)
        await _caption(wizard)
    finally:
        await wizard.bot.session.close()


async def _fields(wizard: Wizard) -> None:
    await wizard.send(_USER_ID, text="Новая заявка")
    menu = wizard.texts()[-1]
    labels = _labels(menu)
    assert "Добавить описание" in labels
    assert "Добавить фото" in labels
    assert "Добавить срочность" in labels
    assert "Добавить бюджет" in labels
    assert "Отправить заявку" in labels
    assert await wizard.state(_USER_ID).get_state() == OrderCreate.preview.state

    await wizard.tap(_USER_ID, CreateCB(action="edit_desc").pack())
    assert "Напишите, что нужно найти" in (wizard.texts()[-1].text or "")
    assert "Назад к заявке" in _labels(wizard.texts()[-1])
    await wizard.send(_USER_ID, text="Кроссовки Nike 42")
    data = await wizard.state(_USER_ID).get_data()
    assert data["description"] == "Кроссовки Nike 42"
    assert await wizard.state(_USER_ID).get_state() == OrderCreate.preview.state
    assert "Изменить описание" in _labels(wizard.texts()[-1])

    await wizard.tap(_USER_ID, CreateCB(action="edit_photo").pack())
    await wizard.send(_USER_ID, photo=[_photo("photo-1")])
    data = await wizard.state(_USER_ID).get_data()
    assert data["user_photo_id"] == "photo-1"
    assert "Удалить фото" in _labels(wizard.texts()[-1])
    assert not any(type(call).__name__ == "DeleteMessage" for call in wizard.session.calls)

    await wizard.tap(_USER_ID, CreateCB(action="edit_urgency").pack())
    assert "Срочно" in _labels(wizard.texts()[-1])
    await wizard.tap(_USER_ID, CreateCB(action="urgency", value="urgent").pack())
    data = await wizard.state(_USER_ID).get_data()
    assert data["urgency"] == "urgent"
    assert "Изменить срочность" in _labels(wizard.texts()[-1])

    await wizard.tap(_USER_ID, CreateCB(action="field", value="budget").pack())
    await wizard.send(_USER_ID, text="до 5000 ₽")
    assert (await wizard.state(_USER_ID).get_data())["budget"] == "до 5000 ₽"


async def _caption(wizard: Wizard) -> None:
    await wizard.send(13, text="Новая заявка")
    await wizard.tap(13, CreateCB(action="edit_photo").pack())
    document = Document(
        file_id="doc-1",
        file_unique_id="d1",
        file_name="shoe.jpg",
        mime_type="image/jpeg",
    )
    await wizard.send(13, document=document, caption="Кеды белые 41")
    data = await wizard.state(13).get_data()
    assert data["user_photo_id"] == "doc-1"
    assert data["description"] == "Кеды белые 41"
    assert await wizard.state(13).get_state() == OrderCreate.preview.state
    assert not any(type(call).__name__ == "DeleteMessage" for call in wizard.session.calls)
