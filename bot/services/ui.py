"""Редактирование одного сервисного сообщения вместо ленты шагов."""

from __future__ import annotations

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InaccessibleMessage, InlineKeyboardMarkup, Message


def as_message(message: Message | InaccessibleMessage | None) -> Message | None:
    if isinstance(message, Message):
        return message
    return None


async def try_delete(message: Message) -> None:
    try:
        await message.delete()
    except TelegramAPIError:
        return


async def show_screen(
    state: FSMContext,
    text: str,
    reply_markup: InlineKeyboardMarkup | None,
    *,
    prefer: Message | None = None,
    anchor: Message | None = None,
) -> None:
    """Обновляет экран мастера.

    prefer — сообщение, которое нужно править (обычно callback).
    anchor — сообщение пользователя: от него уйдёт новый экран, если править нечего.
    """

    if prefer is not None:
        updated = await edit_or_answer(prefer, text, reply_markup)
        await state.update_data(
            ui_chat_id=updated.chat.id,
            ui_message_id=updated.message_id,
        )
        return

    data = await state.get_data()
    chat_id = data.get("ui_chat_id")
    message_id = data.get("ui_message_id")
    bot = anchor.bot if anchor is not None else None
    if bot is not None and isinstance(chat_id, int) and isinstance(message_id, int):
        try:
            await bot.edit_message_text(
                text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=reply_markup,
            )
            return
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return

    if anchor is None:
        return
    sent = await anchor.answer(text, reply_markup=reply_markup)
    await state.update_data(ui_chat_id=sent.chat.id, ui_message_id=sent.message_id)


async def refresh_card(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None,
) -> Message:
    """Обновляет текстовую карточку или подпись к фото, чтобы убрать старые кнопки."""

    if message.photo:
        try:
            if len(text) <= 1024:
                return await message.edit_caption(caption=text, reply_markup=reply_markup)
            await message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return message
        return await message.answer(text, reply_markup=reply_markup)
    return await edit_or_answer(message, text, reply_markup)


async def edit_or_answer(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None,
) -> Message:
    try:
        return await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return message
        return await message.answer(text, reply_markup=reply_markup)
