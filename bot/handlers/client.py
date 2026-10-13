"""Сценарий клиента: заявка, список и решение по предложению."""

from __future__ import annotations

from html import escape
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
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
    cancel_keyboard,
    client_list_keyboard,
    client_main_keyboard,
    client_order_keyboard,
    confirm_keyboard,
    extra_input_keyboard,
    extras_keyboard,
    photo_keyboard,
    preview_keyboard,
    urgency_keyboard,
)
from bot.services.drafts import OrderDraft
from bot.services.formatting import (
    format_admin_card,
    format_client_order,
    format_client_preview,
    format_order_list,
)
from bot.services.notifications import notify_user
from bot.services.ui import as_message, refresh_card, show_screen, try_delete
from bot.states.client import ClientClarify, OrderCreate, is_order_create

router = Router(name="client")

DESCRIPTION_PROMPT = (
    "<b>Новая заявка</b>\n\n"
    "Опишите товар: что ищете, бренд, модель и важные детали."
)
PHOTO_PROMPT = "Пришлите одно фото товара или пропустите этот шаг."
URGENCY_PROMPT = "Насколько срочно нужен товар?"
EXTRAS_PROMPT = (
    "<b>Дополнительные параметры</b>\n\n"
    "Любой пункт можно пропустить. «-» в поле очищает уже введённое значение."
)
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


async def _show_preview(
    state: FSMContext,
    *,
    prefer: Message | None = None,
    anchor: Message | None = None,
) -> None:
    draft = OrderDraft.from_state(await state.get_data())
    await state.set_state(OrderCreate.preview)
    await state.update_data(return_to_preview=False)
    await show_screen(
        state,
        format_client_preview(draft),
        preview_keyboard(),
        prefer=prefer,
        anchor=anchor,
    )


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


@router.callback_query(ClientMenuCB.filter(F.action == "new"))
async def new_order(query: CallbackQuery, state: FSMContext) -> None:
    message = as_message(query.message)
    await state.clear()
    await state.set_state(OrderCreate.description)
    if message is not None:
        await show_screen(state, DESCRIPTION_PROMPT, cancel_keyboard(), prefer=message)
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
        await refresh_card(message, CLIENT_START, client_main_keyboard())
    await query.answer()


@router.callback_query(ClientMenuCB.filter(F.action == "help"))
async def help_callback(query: CallbackQuery) -> None:
    message = as_message(query.message)
    if message is not None:
        await refresh_card(message, CLIENT_HELP, client_main_keyboard())
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
        await refresh_card(message, "Создание заявки отменено.", client_main_keyboard())
    await query.answer()


@router.callback_query(CreateCB.filter(F.action == "skip_photo"))
async def skip_photo(query: CallbackQuery, state: FSMContext) -> None:
    draft = OrderDraft.from_state(await state.get_data())
    message = as_message(query.message)
    if draft.return_to_preview:
        await state.update_data(return_to_preview=False)
        await _show_preview(state, prefer=message)
        await query.answer()
        return
    await state.update_data(user_photo_id=None)
    await state.set_state(OrderCreate.urgency)
    await show_screen(state, URGENCY_PROMPT, urgency_keyboard(), prefer=message)
    await query.answer()


@router.callback_query(CreateCB.filter(F.action == "clear_photo"))
async def clear_photo(query: CallbackQuery, state: FSMContext) -> None:
    draft = OrderDraft.from_state(await state.get_data())
    editing = draft.return_to_preview
    draft = draft.with_photo(None)
    await _store_draft(state, draft, return_to_preview=False)
    message = as_message(query.message)
    if editing:
        await _show_preview(state, prefer=message)
    else:
        await state.set_state(OrderCreate.urgency)
        await show_screen(state, URGENCY_PROMPT, urgency_keyboard(), prefer=message)
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
    await state.update_data(**draft.to_state())
    await _show_preview(state, prefer=as_message(query.message))
    await query.answer()


@router.callback_query(CreateCB.filter(F.action == "extras"))
async def open_extras(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OrderCreate.preview)
    await show_screen(
        state,
        EXTRAS_PROMPT,
        extras_keyboard(),
        prefer=as_message(query.message),
    )
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
    await state.update_data(extra_field=field)
    await state.set_state(OrderCreate.extra)
    await show_screen(
        state,
        EXTRA_PROMPTS[field],
        extra_input_keyboard(),
        prefer=as_message(query.message),
    )
    await query.answer()


@router.callback_query(CreateCB.filter(F.action == "back"))
async def back_to_preview(query: CallbackQuery, state: FSMContext) -> None:
    await _show_preview(state, prefer=as_message(query.message))
    await query.answer()


@router.callback_query(CreateCB.filter(F.action == "edit_desc"))
async def edit_description(query: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(return_to_preview=True)
    await state.set_state(OrderCreate.description)
    await show_screen(
        state,
        DESCRIPTION_PROMPT,
        cancel_keyboard(),
        prefer=as_message(query.message),
    )
    await query.answer()


@router.callback_query(CreateCB.filter(F.action == "edit_photo"))
async def edit_photo(query: CallbackQuery, state: FSMContext) -> None:
    draft = OrderDraft.from_state(await state.get_data())
    await state.update_data(return_to_preview=True)
    await state.set_state(OrderCreate.photo)
    await show_screen(
        state,
        PHOTO_PROMPT,
        photo_keyboard(editing=True, has_photo=bool(draft.user_photo_id)),
        prefer=as_message(query.message),
    )
    await query.answer()


@router.callback_query(CreateCB.filter(F.action == "edit_urgency"))
async def edit_urgency(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OrderCreate.urgency)
    await show_screen(
        state,
        URGENCY_PROMPT,
        urgency_keyboard(),
        prefer=as_message(query.message),
    )
    await query.answer()


@router.callback_query(CreateCB.filter(F.action == "send"))
async def send_order(
    query: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
    bot: Bot,
) -> None:
    draft = OrderDraft.from_state(await state.get_data())
    if not draft.ready() or query.from_user is None or draft.urgency is None:
        await query.answer("Заполните описание и срочность", show_alert=True)
        return
    order = await db.create_order(
        user_id=query.from_user.id,
        user_name=display_name(query.from_user),
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
    message = as_message(query.message)
    text = (
        f"Заявка <b>#{order.id}</b> отправлена ассистенту. "
        "Статус можно смотреть в «Мои заявки»."
    )
    if message is not None:
        await refresh_card(message, text, client_main_keyboard())
    await query.answer("Заявка отправлена")


@router.message(OrderCreate.description, F.text)
async def save_description(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return
    try:
        draft = OrderDraft.from_state(await state.get_data()).with_description(message.text)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    editing = draft.return_to_preview
    await state.update_data(**draft.to_state())
    await try_delete(message)
    if editing:
        await _show_preview(state, anchor=message)
        return
    await state.set_state(OrderCreate.photo)
    await show_screen(
        state,
        PHOTO_PROMPT,
        photo_keyboard(editing=False, has_photo=False),
        anchor=message,
    )


@router.message(OrderCreate.description)
async def description_expected(message: Message) -> None:
    await message.answer("Нужно текстовое описание товара.")


@router.message(OrderCreate.photo, F.photo)
async def save_photo(message: Message, state: FSMContext) -> None:
    if not message.photo:
        return
    draft = OrderDraft.from_state(await state.get_data()).with_photo(message.photo[-1].file_id)
    editing = draft.return_to_preview
    await _store_draft(state, draft, return_to_preview=False)
    await try_delete(message)
    if editing:
        await _show_preview(state, anchor=message)
        return
    await state.set_state(OrderCreate.urgency)
    await show_screen(state, URGENCY_PROMPT, urgency_keyboard(), anchor=message)


@router.message(OrderCreate.photo)
async def photo_expected(message: Message) -> None:
    await message.answer("Пришлите фотографию или нажмите «Пропустить».")


@router.message(OrderCreate.urgency)
async def urgency_expected(message: Message, state: FSMContext) -> None:
    await try_delete(message)
    await show_screen(state, URGENCY_PROMPT, urgency_keyboard(), anchor=message)


@router.message(OrderCreate.extra, F.text)
async def save_extra(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return
    field = (await state.get_data()).get("extra_field")
    if not isinstance(field, str):
        await _show_preview(state, anchor=message)
        return
    try:
        draft = OrderDraft.from_state(await state.get_data()).with_extra(field, message.text)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await state.update_data(**draft.to_state(), extra_field=None)
    await try_delete(message)
    await _show_preview(state, anchor=message)


@router.message(OrderCreate.extra)
async def extra_expected(message: Message) -> None:
    await message.answer("Пришлите значение текстом или нажмите «Назад».")


@router.message(OrderCreate.preview)
async def preview_hint(message: Message) -> None:
    await message.answer("Проверьте заявку и нажмите кнопку под карточкой. /cancel — отмена.")


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
        await message.answer("Вопрос сброшен.", reply_markup=client_main_keyboard())
        return
    order = await db.get_order(order_id)
    if order is None or order.user_id != message.from_user.id:
        await state.clear()
        await message.answer("Заявка не найдена.", reply_markup=client_main_keyboard())
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
    await message.answer("Вопрос отправлен ассистенту.", reply_markup=client_main_keyboard())


@router.message(ClientClarify.text)
async def clarification_expected(message: Message) -> None:
    await message.answer("Пришлите вопрос текстом.")


@router.message()
async def client_fallback(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    if await state.get_state():
        await message.answer(
            "Используйте кнопки или пришлите то, что бот запросил. /cancel — сброс."
        )
        return
    await message.answer("Выберите действие в меню.", reply_markup=client_main_keyboard())


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
