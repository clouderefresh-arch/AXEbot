"""Шаги заявки клиента: кнопки внизу и фото с подписью."""

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
from aiogram.methods import SendMessage, TelegramMethod
from aiogram.methods.base import TelegramType
from aiogram.types import Chat, Document, Message, PhotoSize, Update, User

from bot.handlers.client import router as client_router
from bot.states.client import OrderCreate


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

    def state(self, user_id: int) -> FSMContext:
        return FSMContext(
            storage=self.dispatcher.storage,
            key=StorageKey(bot_id=self.bot.id, chat_id=user_id, user_id=user_id),
        )

    def texts(self) -> list[SendMessage]:
        return [call for call in self.session.calls if isinstance(call, SendMessage)]


def _buttons(method: SendMessage) -> list[str]:
    markup = method.reply_markup
    assert markup is not None and hasattr(markup, "keyboard")
    return [button.text for row in markup.keyboard for button in row]


def _photo(file_id: str) -> PhotoSize:
    return PhotoSize(file_id=file_id, file_unique_id=file_id, width=8, height=8)


def test_client_wizard_accepts_photo_and_keeps_buttons() -> None:
    asyncio.run(_client_wizard())


async def _client_wizard() -> None:
    wizard = Wizard()
    try:
        await _bottom_buttons(wizard)
        await _caption_opens_urgency(wizard)
        await _photo_then_text(wizard)
        await _text_then_photo(wizard)
        await _image_file(wizard)
    finally:
        await wizard.bot.session.close()


async def _bottom_buttons(wizard: Wizard) -> None:
    await wizard.send(11, text="Новая заявка")
    sent = wizard.texts()[-1]
    assert "фото с подписью" in (sent.text or "")
    assert "Отмена" in _buttons(sent)
    assert await wizard.state(11).get_state() == OrderCreate.description.state


async def _caption_opens_urgency(wizard: Wizard) -> None:
    wizard.session.calls.clear()
    await wizard.send(12, text="Новая заявка")
    await wizard.send(12, photo=[_photo("photo-1")], caption="Кроссовки Nike 42")
    sent = wizard.texts()[-1]
    assert sent.text == "Насколько срочно нужен товар?"
    assert "Срочно" in _buttons(sent)
    data = await wizard.state(12).get_data()
    assert data["description"] == "Кроссовки Nike 42"
    assert data["user_photo_id"] == "photo-1"
    assert await wizard.state(12).get_state() == OrderCreate.urgency.state
    assert not any(type(call).__name__ == "DeleteMessage" for call in wizard.session.calls)


async def _photo_then_text(wizard: Wizard) -> None:
    wizard.session.calls.clear()
    await wizard.send(13, text="Новая заявка")
    await wizard.send(13, photo=[_photo("photo-2")])
    saved = wizard.texts()[-1]
    assert saved.text and saved.text.startswith("Фото сохранил")
    assert "Отмена" in _buttons(saved)
    await wizard.send(13, text="Чёрная куртка размер M")
    data = await wizard.state(13).get_data()
    assert data["user_photo_id"] == "photo-2"
    assert data["description"] == "Чёрная куртка размер M"
    assert await wizard.state(13).get_state() == OrderCreate.urgency.state
    assert "Срочно" in _buttons(wizard.texts()[-1])
    assert not any(type(call).__name__ == "DeleteMessage" for call in wizard.session.calls)


async def _text_then_photo(wizard: Wizard) -> None:
    wizard.session.calls.clear()
    await wizard.send(14, text="Новая заявка")
    await wizard.send(14, text="Сумка через плечо")
    photo_prompt = wizard.texts()[-1]
    assert "Пришлите одно фото" in (photo_prompt.text or "")
    assert "Пропустить" in _buttons(photo_prompt)
    await wizard.send(14, photo=[_photo("photo-3")])
    data = await wizard.state(14).get_data()
    assert data["description"] == "Сумка через плечо"
    assert data["user_photo_id"] == "photo-3"
    assert await wizard.state(14).get_state() == OrderCreate.urgency.state
    assert "Срочно" in _buttons(wizard.texts()[-1])
    assert not any(type(call).__name__ == "DeleteMessage" for call in wizard.session.calls)


async def _image_file(wizard: Wizard) -> None:
    document = Document(
        file_id="doc-1",
        file_unique_id="d1",
        file_name="shoe.jpg",
        mime_type="image/jpeg",
    )
    await wizard.send(15, text="Новая заявка")
    await wizard.send(15, document=document, caption="Кеды белые 41")
    data = await wizard.state(15).get_data()
    assert data["user_photo_id"] == "doc-1"
    assert data["description"] == "Кеды белые 41"
    assert await wizard.state(15).get_state() == OrderCreate.urgency.state
