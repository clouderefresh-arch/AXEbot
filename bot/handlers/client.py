"""Сценарий клиента: заявка, список и решение по предложению."""

from __future__ import annotations

from html import escape
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User

from bot.config import Settings
from bot.constants import (
    MAX_COMMENT,
    PAGE_SIZE,
    STATUS_ANSWERED,
    STATUS_APPROVED,
    STATUS_CANCELED,
    STATUS_IN_PROGRESS,
    STATUS_PENDING,
)
from bot.database.db import Database, Order
from bot.handlers.common import CLIENT_HELP, CLIENT_START
from bot.keyboards.admin import admin_order_keyboard
from bot.keyboards.callbacks import ClientMenuCB, ClientOrderCB, CreateCB, PageCB
from bot.keyboards.client import (
    BTN_CANCEL,
    BTN_HELP,
    BTN_LIST,
    BTN_NEW,
    client_list_keyboard,
    client_order_keyboard,
    client_reply_menu,
    confirm_keyboard,
    field_prompt_keyboard,
    order_form_keyboard,
    urgency_menu_keyboard,
)
from bot.services.drafts import OrderDraft
from bot.services.formatting import (
    format_admin_card,
    format_client_order,
    format_client_preview,
    format_order_list,
)
from bot.services.notifications import notify_user
from bot.services.ui import as_message, refresh_card
from bot.states.client import ClientClarify, OrderCreate, is_order_create

router = Router(name="client")

DESCRIPTION_PROMPT = (
    "Напишите, что нужно найти: бренд, модель и важные детали.\n"
    "Можно прислать фото с подписью — бот заберёт и текст, и снимок."
)
PHOTO_PROMPT = "Пришлите одно фото товара. Сообщение останется в чате."
URGENCY_PROMPT = "Насколько срочно нужен товар? Выберите кнопку ниже."
EXTRA_PROMPTS = {
    "budget": "Укажите бюджет, например «до 5000 ₽».",
    "size": "Укажите размер.",
    "color": "Укажите цвет.",
    "reference_link": "Пришлите ссылку на похожий товар.",
}
FIELD_BY_ACTION = {
    "budget": "budget",
    "size": "size",
    "color": "color",
    "link": "reference_link",
}


def display_name(user: User) -> str:
    parts = [part for part in (user.first_name, user.last_name) if part]
    name = " ".join(parts).strip()
    if user.username:
        return f"{name} (@{user.username})" if name else f"@{user.username}"
    return name or str(user.id)


async def _store_draft(state: FSMContext, draft: OrderDraft, **extra: object) -> None:
    payload = draft.to_state()
    payload.update(extra)
    await state.update_data(**payload)


def _clamp(offset: int, total: int, limit: int) -> int:
    if total <= 0:
        return 0
    max_offset = ((total - 1) // limit) * limit
    return min(max(0, offset), max_offset)


async def show_my_orders(
    message: Message,
    db: Database,
    *,
    user_id: int,
    offset: int,
    edit: bool,
) -> None:
    total = await db.count_orders(user_id=user_id)
    offset = _clamp(offset, total, PAGE_SIZE)
    orders = await db.list_orders(
        user_id=user_id,
        limit=PAGE_SIZE,
        offset=offset,
        order="desc",
    )
    text = format_order_list("Мои заявки", orders, total=total, offset=offset)
    keyboard = client_list_keyboard(orders, offset=offset, limit=PAGE_SIZE, total=total)
    if edit:
        await refresh_card(message, text, keyboard)
        return
    await message.answer(text, reply_markup=keyboard)


async def _forget_menu_buttons(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    chat_id = data.get("menu_chat_id")
    message_id = data.get("menu_message_id")
    if not isinstance(chat_id, int) or not isinstance(message_id, int):
        return
    try:
        await message.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=None,
        )
    except TelegramBadRequest:
        return


async def _remember_menu(state: FSMContext, sent: Message) -> None:
    await state.update_data(menu_chat_id=sent.chat.id, menu_message_id=sent.message_id)


async def _show_order_menu(message: Message | None, state: FSMContext) -> None:
    if message is None:
        return
    await _forget_menu_buttons(message, state)
    draft = OrderDraft.from_state(await state.get_data())
    await state.set_state(OrderCreate.preview)
    sent = await message.answer(
        format_client_preview(draft),
        reply_markup=order_form_keyboard(draft),
    )
    await _remember_menu(state, sent)


async def _ask_description(message: Message | None, state: FSMContext) -> None:
    if message is None:
        await state.set_state(OrderCreate.description)
        return
    await _forget_menu_buttons(message, state)
    await state.set_state(OrderCreate.description)
    sent = await message.answer(DESCRIPTION_PROMPT, reply_markup=field_prompt_keyboard())
    await _remember_menu(state, sent)


async def _ask_photo(message: Message | None, state: FSMContext) -> None:
    if message is None:
        await state.set_state(OrderCreate.photo)
        return
    await _forget_menu_buttons(message, state)
    await state.set_state(OrderCreate.photo)
    sent = await message.answer(PHOTO_PROMPT, reply_markup=field_prompt_keyboard())
    await _remember_menu(state, sent)


async def _ask_urgency(message: Message | None, state: FSMContext) -> None:
    if message is None:
        await state.set_state(OrderCreate.urgency)
        return
    await _forget_menu_buttons(message, state)
    await state.set_state(OrderCreate.urgency)
    sent = await message.answer(URGENCY_PROMPT, reply_markup=urgency_menu_keyboard())
    await _remember_menu(state, sent)


async def _ask_extra(message: Message | None, state: FSMContext, field: str) -> None:
    await state.update_data(extra_field=field)
    await state.set_state(OrderCreate.extra)
    if message is None:
        return
    await _forget_menu_buttons(message, state)
    sent = await message.answer(
        f"{EXTRA_PROMPTS[field]}\n«-» очищает поле.",
        reply_markup=field_prompt_keyboard(),
    )
    await _remember_menu(state, sent)


def _image_file_id(message: Message) -> str | None:
    if message.photo:
        return message.photo[-1].file_id
    document = message.document
    if document is None:
        return None
    mime = document.mime_type or ""
    name = (document.file_name or "").lower()
    if mime.startswith("image/") or name.endswith((".jpg", ".jpeg", ".png", ".webp", ".heic")):
        return document.file_id
    return None


async def _own_order(query: CallbackQuery, db: Database, order_id: int) -> Order | None:
    order = await db.get_order(order_id)
    if query.from_user is None or order is None or order.user_id != query.from_user.id:
        await query.answer("Заявка не найдена", show_alert=True)
        return None
    return order


@router.message(Command("orders"))
async def orders_command(message: Message, db: Database) -> None:
    if message.from_user is None:
        return
    await show_my_orders(message, db, user_id=message.from_user.id, offset=0, edit=False)


@router.message(F.text == BTN_CANCEL)
async def cancel_button(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=client_reply_menu())


@router.message(F.text == BTN_NEW)
async def new_button(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _show_order_menu(message, state)


@router.message(F.text == BTN_LIST)
async def list_button(message: Message, db: Database) -> None:
    if message.from_user is None:
        return
    await show_my_orders(message, db, user_id=message.from_user.id, offset=0, edit=False)


@router.message(F.text == BTN_HELP)
async def help_button(message: Message) -> None:
    await message.answer(CLIENT_HELP, reply_markup=client_reply_menu())


@router.callback_query(ClientMenuCB.filter(F.action == "new"))
async def new_order(query: CallbackQuery, state: FSMContext) -> None:
    message = as_message(query.message)
    await state.clear()
    if message is not None:
        await _show_order_menu(message, state)
    await query.answer()


@router.callback_query(ClientMenuCB.filter(F.action == "list"))
async def list_orders(query: CallbackQuery, db: Database) -> None:
    message = as_message(query.message)
    if message is None or query.from_user is None:
        await query.answer()
        return
    await show_my_orders(message, db, user_id=query.from_user.id, offset=0, edit=True)
    await query.answer()


@router.callback_query(ClientMenuCB.filter(F.action == "menu"))
async def back_to_menu(query: CallbackQuery) -> None:
    message = as_message(query.message)
    if message is not None:
        await message.answer(CLIENT_START, reply_markup=client_reply_menu())
    await query.answer()


@router.callback_query(ClientMenuCB.filter(F.action == "help"))
async def help_callback(query: CallbackQuery) -> None:
    message = as_message(query.message)
    if message is not None:
        await message.answer(CLIENT_HELP, reply_markup=client_reply_menu())
    await query.answer()


@router.callback_query(PageCB.filter(F.scope == "my"))
async def page_orders(query: CallbackQuery, callback_data: PageCB, db: Database) -> None:
    message = as_message(query.message)
    if message is None or query.from_user is None:
        await query.answer()
        return
    await show_my_orders(
        message,
        db,
        user_id=query.from_user.id,
        offset=callback_data.offset,
        edit=True,
    )
    await query.answer()


@router.callback_query(CreateCB.filter(F.action == "cancel"))
async def cancel_create(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    message = as_message(query.message)
    if message is not None:
        await message.answer("Создание заявки отменено.", reply_markup=client_reply_menu())
    await query.answer()


@router.callback_query(CreateCB.filter(F.action == "skip_photo"))
async def skip_photo(query: CallbackQuery, state: FSMContext) -> None:
    await _show_order_menu(as_message(query.message), state)
    await query.answer()


@router.callback_query(CreateCB.filter(F.action == "clear_photo"))
async def clear_photo(query: CallbackQuery, state: FSMContext) -> None:
    draft = OrderDraft.from_state(await state.get_data()).with_photo(None)
    await _store_draft(state, draft)
    await _show_order_menu(as_message(query.message), state)
    await query.answer("Фото убрано")


@router.callback_query(CreateCB.filter(F.action == "urgency"))
async def choose_urgency(
    query: CallbackQuery,
    callback_data: CreateCB,
    state: FSMContext,
) -> None:
    try:
        draft = OrderDraft.from_state(await state.get_data()).with_urgency(callback_data.value)
    except ValueError as exc:
        await query.answer(str(exc), show_alert=True)
        return
    await _store_draft(state, draft)
    await _show_order_menu(as_message(query.message), state)
    await query.answer()


@router.callback_query(CreateCB.filter(F.action == "extras"))
async def open_extras(query: CallbackQuery, state: FSMContext) -> None:
    await _show_order_menu(as_message(query.message), state)
    await query.answer()


@router.callback_query(CreateCB.filter(F.action == "field"))
async def ask_extra(
    query: CallbackQuery,
    callback_data: CreateCB,
    state: FSMContext,
) -> None:
    field = FIELD_BY_ACTION.get(callback_data.value)
    if field is None:
        await query.answer("Неизвестное поле", show_alert=True)
        return
    await _ask_extra(as_message(query.message), state, field)
    await query.answer()


@router.callback_query(CreateCB.filter(F.action == "back"))
async def back_to_preview(query: CallbackQuery, state: FSMContext) -> None:
    await _show_order_menu(as_message(query.message), state)
    await query.answer()


@router.callback_query(CreateCB.filter(F.action == "edit_desc"))
async def edit_description(query: CallbackQuery, state: FSMContext) -> None:
    await _ask_description(as_message(query.message), state)
    await query.answer()


@router.callback_query(CreateCB.filter(F.action == "edit_photo"))
async def edit_photo(query: CallbackQuery, state: FSMContext) -> None:
    await _ask_photo(as_message(query.message), state)
    await query.answer()


@router.callback_query(CreateCB.filter(F.action == "edit_urgency"))
async def edit_urgency(query: CallbackQuery, state: FSMContext) -> None:
    await _ask_urgency(as_message(query.message), state)
    await query.answer()


@router.callback_query(CreateCB.filter(F.action == "send"))
async def send_order(
    query: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
    bot: Bot,
) -> None:
    if query.from_user is None:
        await query.answer()
        return
    order = await _submit_order(
        as_message(query.message),
        state,
        db,
        settings,
        bot,
        query.from_user,
    )
    if order is None:
        await query.answer("Заполните описание и срочность", show_alert=True)
        return
    await query.answer("Заявка отправлена")


async def _submit_order(
    message: Message | None,
    state: FSMContext,
    db: Database,
    settings: Settings,
    bot: Bot,
    user: User,
) -> Order | None:
    draft = OrderDraft.from_state(await state.get_data())
    if not draft.ready() or draft.urgency is None:
        return None
    order = await db.create_order(
        user_id=user.id,
        user_name=display_name(user),
        description=draft.description,
        urgency=draft.urgency,
        user_photo_id=draft.user_photo_id,
        budget=draft.budget,
        size=draft.size,
        color=draft.color,
        reference_link=draft.reference_link,
    )
    await state.clear()
    card = format_admin_card(order, tz=ZoneInfo(settings.timezone))
    if order.user_photo_id:
        await notify_user(
            bot,
            settings.admin_id,
            f"Фото клиента по заявке #{order.id}",
            photo_id=order.user_photo_id,
        )
    await notify_user(
        bot,
        settings.admin_id,
        card,
        reply_markup=admin_order_keyboard(order),
    )
    if message is not None:
        await message.answer(
            f"Заявка <b>#{order.id}</b> отправлена ассистенту. "
            "Статус можно смотреть в «Мои заявки».",
            reply_markup=client_reply_menu(),
        )
    return order


def _with_caption(draft: OrderDraft, caption: str) -> OrderDraft:
    text = caption.strip()
    if len(text) < 3 or draft.description.strip():
        return draft
    try:
        return draft.with_description(text)
    except ValueError:
        return draft


@router.message(OrderCreate.description, F.photo)
@router.message(OrderCreate.description, F.document)
async def save_description_media(message: Message, state: FSMContext) -> None:
    file_id = _image_file_id(message)
    if file_id is None:
        await message.answer(DESCRIPTION_PROMPT, reply_markup=field_prompt_keyboard())
        return
    draft = _with_caption(
        OrderDraft.from_state(await state.get_data()).with_photo(file_id),
        message.caption or "",
    )
    if not draft.description.strip():
        await state.update_data(user_photo_id=file_id)
        await message.answer(
            "Фото сохранил. Теперь напишите текстом, что нужно найти.",
            reply_markup=field_prompt_keyboard(),
        )
        return
    await _store_draft(state, draft)
    await _show_order_menu(message, state)


@router.message(OrderCreate.description, F.text)
async def save_description(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return
    try:
        draft = OrderDraft.from_state(await state.get_data()).with_description(message.text)
    except ValueError as exc:
        await message.answer(str(exc), reply_markup=field_prompt_keyboard())
        return
    await _store_draft(state, draft)
    await _show_order_menu(message, state)


@router.message(OrderCreate.description)
async def description_expected(message: Message, state: FSMContext) -> None:
    await _ask_description(message, state)


@router.message(OrderCreate.photo, F.photo)
@router.message(OrderCreate.photo, F.document)
async def save_photo(message: Message, state: FSMContext) -> None:
    file_id = _image_file_id(message)
    if file_id is None:
        await message.answer(PHOTO_PROMPT, reply_markup=field_prompt_keyboard())
        return
    draft = _with_caption(
        OrderDraft.from_state(await state.get_data()).with_photo(file_id),
        message.caption or "",
    )
    await _store_draft(state, draft)
    await _show_order_menu(message, state)


@router.message(OrderCreate.photo)
async def photo_expected(message: Message, state: FSMContext) -> None:
    await _ask_photo(message, state)


@router.message(OrderCreate.urgency)
async def urgency_expected(message: Message, state: FSMContext) -> None:
    await _ask_urgency(message, state)


@router.message(OrderCreate.extra, F.text)
async def save_extra(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return
    field = (await state.get_data()).get("extra_field")
    if not isinstance(field, str):
        await _show_order_menu(message, state)
        return
    try:
        draft = OrderDraft.from_state(await state.get_data()).with_extra(field, message.text)
    except ValueError as exc:
        await message.answer(str(exc), reply_markup=field_prompt_keyboard())
        return
    await state.update_data(**draft.to_state(), extra_field=None)
    await _show_order_menu(message, state)


@router.message(OrderCreate.extra)
async def extra_expected(message: Message, state: FSMContext) -> None:
    field = (await state.get_data()).get("extra_field")
    if isinstance(field, str) and field in EXTRA_PROMPTS:
        await _ask_extra(message, state, field)
        return
    await _show_order_menu(message, state)


@router.message(OrderCreate.preview, F.photo)
@router.message(OrderCreate.preview, F.document)
async def preview_photo(message: Message, state: FSMContext) -> None:
    file_id = _image_file_id(message)
    if file_id is None:
        await _show_order_menu(message, state)
        return
    draft = _with_caption(
        OrderDraft.from_state(await state.get_data()).with_photo(file_id),
        message.caption or "",
    )
    await _store_draft(state, draft)
    await _show_order_menu(message, state)


@router.message(OrderCreate.preview)
async def preview_hint(message: Message, state: FSMContext) -> None:
    await _show_order_menu(message, state)


@router.callback_query(ClientOrderCB.filter(F.action == "open"))
async def open_order(
    query: CallbackQuery,
    callback_data: ClientOrderCB,
    db: Database,
    settings: Settings,
) -> None:
    order = await _own_order(query, db, callback_data.order_id)
    message = as_message(query.message)
    if order is None or message is None:
        if order is None:
            return
        await query.answer()
        return
    await refresh_card(
        message,
        format_client_order(order, tz=ZoneInfo(settings.timezone)),
        client_order_keyboard(order),
    )
    await query.answer()


@router.callback_query(ClientOrderCB.filter(F.action == "cancel"))
async def ask_cancel(
    query: CallbackQuery,
    callback_data: ClientOrderCB,
    db: Database,
) -> None:
    order = await _own_order(query, db, callback_data.order_id)
    message = as_message(query.message)
    if order is None or message is None:
        if order is None:
            return
        await query.answer()
        return
    if order.status not in {STATUS_PENDING, STATUS_IN_PROGRESS}:
        await query.answer("Эту заявку уже нельзя отменить", show_alert=True)
        return
    await refresh_card(
        message,
        f"Отменить заявку <b>#{order.id}</b>?",
        confirm_keyboard(order.id, yes_action="cancel_yes", yes_text="Да, отменить"),
    )
    await query.answer()


@router.callback_query(ClientOrderCB.filter(F.action == "cancel_yes"))
async def confirm_cancel(
    query: CallbackQuery,
    callback_data: ClientOrderCB,
    db: Database,
    settings: Settings,
    bot: Bot,
) -> None:
    await _close_by_client(
        query,
        db,
        settings,
        bot,
        order_id=callback_data.order_id,
        allowed={STATUS_PENDING, STATUS_IN_PROGRESS},
        admin_text="Клиент отменил заявку #{id}.",
        alert="Заявка отменена",
    )


@router.callback_query(ClientOrderCB.filter(F.action == "accept"))
async def accept_offer(
    query: CallbackQuery,
    callback_data: ClientOrderCB,
    db: Database,
    settings: Settings,
    bot: Bot,
) -> None:
    order = await _own_order(query, db, callback_data.order_id)
    if order is None:
        return
    if order.status != STATUS_ANSWERED:
        await query.answer("Это предложение уже нельзя принять", show_alert=True)
        return
    updated = await db.update_order(order.id, status=STATUS_APPROVED)
    if updated is None:
        await query.answer("Заявка не найдена", show_alert=True)
        return
    await notify_user(
        bot,
        settings.admin_id,
        f"Клиент принял предложение по заявке #{updated.id}.",
        reply_markup=admin_order_keyboard(updated),
    )
    message = as_message(query.message)
    if message is not None:
        await refresh_card(
            message,
            format_client_order(updated, tz=ZoneInfo(settings.timezone)),
            client_order_keyboard(updated),
        )
    await query.answer("Вы приняли предложение")


@router.callback_query(ClientOrderCB.filter(F.action == "reject"))
async def ask_reject(
    query: CallbackQuery,
    callback_data: ClientOrderCB,
    db: Database,
) -> None:
    order = await _own_order(query, db, callback_data.order_id)
    message = as_message(query.message)
    if order is None or message is None:
        if order is None:
            return
        await query.answer()
        return
    if order.status != STATUS_ANSWERED:
        await query.answer("Это предложение уже нельзя отклонить", show_alert=True)
        return
    await refresh_card(
        message,
        f"Отклонить предложение по заявке <b>#{order.id}</b>?",
        confirm_keyboard(order.id, yes_action="reject_yes", yes_text="Да, отклонить"),
    )
    await query.answer()


@router.callback_query(ClientOrderCB.filter(F.action == "reject_yes"))
async def confirm_reject(
    query: CallbackQuery,
    callback_data: ClientOrderCB,
    db: Database,
    settings: Settings,
    bot: Bot,
) -> None:
    await _close_by_client(
        query,
        db,
        settings,
        bot,
        order_id=callback_data.order_id,
        allowed={STATUS_ANSWERED},
        admin_text="Клиент отклонил предложение по заявке #{id}.",
        alert="Предложение отклонено",
    )


@router.callback_query(ClientOrderCB.filter(F.action == "ask"))
async def ask_clarification(
    query: CallbackQuery,
    callback_data: ClientOrderCB,
    state: FSMContext,
    db: Database,
) -> None:
    if is_order_create(await state.get_state()):
        await query.answer(
            "Сначала завершите или отмените создание заявки",
            show_alert=True,
        )
        return
    order = await _own_order(query, db, callback_data.order_id)
    if order is None:
        return
    if order.status != STATUS_ANSWERED:
        await query.answer("Уточнение доступно, когда есть предложение", show_alert=True)
        return
    await state.set_state(ClientClarify.text)
    await state.update_data(clarify_order_id=order.id)
    message = as_message(query.message)
    if message is not None:
        await message.answer(
            f"Напишите вопрос по заявке #{order.id}. /cancel — отмена."
        )
    await query.answer()


@router.message(ClientClarify.text, F.text)
async def save_clarification(
    message: Message,
    state: FSMContext,
    db: Database,
    settings: Settings,
    bot: Bot,
) -> None:
    if message.text is None or message.from_user is None:
        return
    order_id = (await state.get_data()).get("clarify_order_id")
    if not isinstance(order_id, int):
        await state.clear()
        await message.answer("Вопрос сброшен.", reply_markup=client_reply_menu())
        return
    order = await db.get_order(order_id)
    if order is None or order.user_id != message.from_user.id:
        await state.clear()
        await message.answer("Заявка не найдена.", reply_markup=client_reply_menu())
        return
    text = message.text.strip()
    if len(text) < 2:
        await message.answer("Напишите вопрос чуть подробнее.")
        return
    if len(text) > MAX_COMMENT:
        await message.answer(f"Слишком длинное сообщение. Максимум {MAX_COMMENT} символов.")
        return
    await state.clear()
    note = (
        f"<b>Уточнение по заявке #{order.id}</b>\n"
        f"{escape(display_name(message.from_user))}\n\n"
        f"{escape(text)}"
    )
    await notify_user(
        bot,
        settings.admin_id,
        note,
        reply_markup=admin_order_keyboard(order),
    )
    await message.answer("Вопрос отправлен ассистенту.", reply_markup=client_reply_menu())


@router.message(ClientClarify.text)
async def clarification_expected(message: Message) -> None:
    await message.answer("Пришлите вопрос текстом. /cancel — отмена.")


@router.message()
async def client_fallback(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    current = await state.get_state()
    if is_order_create(current):
        await message.answer(
            "Нажмите кнопку в сообщении с заявкой или пришлите то, что бот запросил."
        )
        return
    if current:
        await message.answer("Пришлите сообщение текстом или нажмите /cancel.")
        return
    await message.answer("Выберите действие в меню.", reply_markup=client_reply_menu())


async def _close_by_client(
    query: CallbackQuery,
    db: Database,
    settings: Settings,
    bot: Bot,
    *,
    order_id: int,
    allowed: set[str],
    admin_text: str,
    alert: str,
) -> None:
    order = await _own_order(query, db, order_id)
    if order is None:
        return
    if order.status not in allowed:
        await query.answer("Статус заявки уже изменился", show_alert=True)
        return
    updated = await db.update_order(order.id, status=STATUS_CANCELED)
    if updated is None:
        await query.answer("Заявка не найдена", show_alert=True)
        return
    await notify_user(
        bot,
        settings.admin_id,
        admin_text.format(id=updated.id),
        reply_markup=admin_order_keyboard(updated),
    )
    message = as_message(query.message)
    if message is not None:
        await refresh_card(
            message,
            format_client_order(updated, tz=ZoneInfo(settings.timezone)),
            client_order_keyboard(updated),
        )
    await query.answer(alert)
