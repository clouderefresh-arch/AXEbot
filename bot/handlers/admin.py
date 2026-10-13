"""Сценарий ассистента: список заявок, статусы и конструктор ответа."""

from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.constants import (
    CLEAR_TOKENS,
    CLOSED_STATUSES,
    OPEN_STATUSES,
    PAGE_SIZE,
    STATUS_ANSWERED,
    STATUS_IN_PROGRESS,
    STATUS_PENDING,
    STATUSES,
)
from bot.database.db import Database, Order
from bot.filters import IsAdmin
from bot.handlers.common import ADMIN_HELP, ADMIN_START
from bot.keyboards.admin import (
    admin_list_keyboard,
    admin_main_keyboard,
    admin_order_keyboard,
    builder_input_keyboard,
    builder_keyboard,
    status_keyboard,
)
from bot.keyboards.callbacks import AdminMenuCB, AdminOrderCB, PageCB, ReplyCB, StatusCB
from bot.keyboards.client import offer_keyboard
from bot.services.currency import CurrencyService, parse_cny
from bot.services.drafts import ReplyDraft
from bot.services.formatting import (
    client_status_text,
    format_admin_card,
    format_builder,
    format_offer,
    format_order_list,
)
from bot.services.notifications import notify_user
from bot.services.ui import as_message, edit_or_answer, show_screen, try_delete
from bot.states.admin import ReplyBuilder

logger = logging.getLogger(__name__)

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

PROMPTS = {
    "price": (
        "Введите цену в юанях, например 199 или 199.5.\n"
        "Символ «-» очищает цену."
    ),
    "delivery": "Введите срок доставки, например «10–14 дней». «-» очищает срок.",
    "comment": "Введите комментарий для клиента. «-» очищает комментарий.",
    "photo": "Пришлите фото товара, которое увидит клиент.",
}
FIELD_STATE = {
    "price": ReplyBuilder.price,
    "delivery": ReplyBuilder.delivery,
    "comment": ReplyBuilder.comment,
    "photo": ReplyBuilder.photo,
}


def _clamp(offset: int, total: int, limit: int) -> int:
    if total <= 0:
        return 0
    max_offset = ((total - 1) // limit) * limit
    return min(max(0, offset), max_offset)


async def show_admin_list(
    message: Message,
    db: Database,
    *,
    scope: str,
    offset: int,
    edit: bool,
) -> None:
    statuses = OPEN_STATUSES if scope == "open" else None
    title = "Открытые заявки" if scope == "open" else "Все заявки"
    total = await db.count_orders(statuses=statuses)
    offset = _clamp(offset, total, PAGE_SIZE)
    orders = await db.list_orders(
        statuses=statuses,
        limit=PAGE_SIZE,
        offset=offset,
        order="asc" if scope == "open" else "desc",
    )
    text = format_order_list(title, orders, total=total, offset=offset)
    keyboard = admin_list_keyboard(orders, scope=scope, offset=offset, total=total)
    if edit:
        await edit_or_answer(message, text, keyboard)
        return
    await message.answer(text, reply_markup=keyboard)


async def _load_draft(state: FSMContext, order_id: int, db: Database) -> ReplyDraft:
    data = await state.get_data()
    if data.get("order_id") == order_id:
        try:
            return ReplyDraft.from_state(data)
        except ValueError:
            pass
    order = await db.get_order(order_id)
    if order is None:
        raise ValueError("Заявка не найдена")
    return ReplyDraft.from_order(order)


async def _render_builder(
    state: FSMContext,
    draft: ReplyDraft,
    settings: Settings,
    *,
    prefer: Message | None = None,
    anchor: Message | None = None,
) -> None:
    await state.set_state(ReplyBuilder.menu)
    await state.update_data(**draft.to_state())
    await show_screen(
        state,
        format_builder(draft, markup_percent=settings.markup_percent),
        builder_keyboard(draft),
        prefer=prefer,
        anchor=anchor,
    )


async def _order_or_alert(query: CallbackQuery, db: Database, order_id: int) -> Order | None:
    order = await db.get_order(order_id)
    if order is None:
        await query.answer("Заявка не найдена", show_alert=True)
        return None
    return order


@router.message(Command("orders"))
async def orders_command(message: Message, db: Database) -> None:
    await show_admin_list(message, db, scope="open", offset=0, edit=False)


@router.callback_query(AdminMenuCB.filter(F.action.in_({"open", "all"})))
async def menu_list(
    query: CallbackQuery,
    callback_data: AdminMenuCB,
    db: Database,
) -> None:
    message = as_message(query.message)
    if message is None:
        await query.answer()
        return
    await show_admin_list(message, db, scope=callback_data.action, offset=0, edit=True)
    await query.answer()


@router.callback_query(AdminMenuCB.filter(F.action == "menu"))
async def back_to_menu(query: CallbackQuery) -> None:
    message = as_message(query.message)
    if message is not None:
        await edit_or_answer(message, ADMIN_START, admin_main_keyboard())
    await query.answer()


@router.callback_query(AdminMenuCB.filter(F.action == "help"))
async def help_callback(query: CallbackQuery) -> None:
    message = as_message(query.message)
    if message is not None:
        await edit_or_answer(message, ADMIN_HELP, admin_main_keyboard())
    await query.answer()


@router.callback_query(PageCB.filter(F.scope.in_({"open", "all"})))
async def page_orders(
    query: CallbackQuery,
    callback_data: PageCB,
    db: Database,
) -> None:
    message = as_message(query.message)
    if message is None:
        await query.answer()
        return
    await show_admin_list(
        message,
        db,
        scope=callback_data.scope,
        offset=callback_data.offset,
        edit=True,
    )
    await query.answer()


@router.callback_query(AdminOrderCB.filter(F.action == "open"))
async def open_card(
    query: CallbackQuery,
    callback_data: AdminOrderCB,
    db: Database,
    settings: Settings,
    bot: Bot,
) -> None:
    order = await _order_or_alert(query, db, callback_data.order_id)
    message = as_message(query.message)
    if order is None or message is None:
        if order is None:
            return
        await query.answer()
        return
    if order.user_photo_id:
        try:
            await bot.send_photo(
                message.chat.id,
                order.user_photo_id,
                caption=f"Фото клиента по заявке #{order.id}",
            )
        except TelegramAPIError:
            logger.warning("Не удалось показать фото заявки %s", order.id, exc_info=True)
    await message.answer(
        format_admin_card(order, tz=_tz(settings)),
        reply_markup=admin_order_keyboard(order),
    )
    await query.answer()


@router.callback_query(AdminOrderCB.filter(F.action == "take"))
async def take_order(
    query: CallbackQuery,
    callback_data: AdminOrderCB,
    db: Database,
    settings: Settings,
    bot: Bot,
) -> None:
    order = await _order_or_alert(query, db, callback_data.order_id)
    if order is None:
        return
    if order.status != STATUS_PENDING:
        await query.answer("Заявка уже не в очереди", show_alert=True)
        return
    updated = await db.update_order(order.id, status=STATUS_IN_PROGRESS)
    if updated is None:
        await query.answer("Заявка не найдена", show_alert=True)
        return
    await notify_user(bot, updated.user_id, client_status_text(updated))
    message = as_message(query.message)
    if message is not None:
        await edit_or_answer(
            message,
            format_admin_card(updated, tz=_tz(settings)),
            admin_order_keyboard(updated),
        )
    await query.answer("Заявка в работе")


@router.callback_query(AdminOrderCB.filter(F.action == "status"))
async def open_status(
    query: CallbackQuery,
    callback_data: AdminOrderCB,
    db: Database,
    settings: Settings,
) -> None:
    order = await _order_or_alert(query, db, callback_data.order_id)
    message = as_message(query.message)
    if order is None or message is None:
        if order is None:
            return
        await query.answer()
        return
    await edit_or_answer(
        message,
        format_admin_card(order, tz=_tz(settings)),
        status_keyboard(order),
    )
    await query.answer()


@router.callback_query(AdminOrderCB.filter(F.action == "back"))
async def back_to_card(
    query: CallbackQuery,
    callback_data: AdminOrderCB,
    db: Database,
    settings: Settings,
) -> None:
    order = await _order_or_alert(query, db, callback_data.order_id)
    message = as_message(query.message)
    if order is None or message is None:
        if order is None:
            return
        await query.answer()
        return
    await edit_or_answer(
        message,
        format_admin_card(order, tz=_tz(settings)),
        admin_order_keyboard(order),
    )
    await query.answer()


@router.callback_query(StatusCB.filter())
async def set_status(
    query: CallbackQuery,
    callback_data: StatusCB,
    db: Database,
    settings: Settings,
    bot: Bot,
) -> None:
    if callback_data.status not in STATUSES:
        await query.answer("Неизвестный статус", show_alert=True)
        return
    order = await _order_or_alert(query, db, callback_data.order_id)
    if order is None:
        return
    if order.status == callback_data.status:
        await query.answer("Этот статус уже установлен", show_alert=True)
        return
    updated = await db.update_order(order.id, status=callback_data.status)
    if updated is None:
        await query.answer("Заявка не найдена", show_alert=True)
        return
    await notify_user(bot, updated.user_id, client_status_text(updated))
    message = as_message(query.message)
    if message is not None:
        await edit_or_answer(
            message,
            format_admin_card(updated, tz=_tz(settings)),
            admin_order_keyboard(updated),
        )
    await query.answer("Статус обновлён")


@router.callback_query(AdminOrderCB.filter(F.action == "reply"))
async def open_builder(
    query: CallbackQuery,
    callback_data: AdminOrderCB,
    state: FSMContext,
    db: Database,
    settings: Settings,
    bot: Bot,
) -> None:
    order = await _order_or_alert(query, db, callback_data.order_id)
    message = as_message(query.message)
    if order is None or message is None:
        if order is None:
            return
        await query.answer()
        return
    if order.status in CLOSED_STATUSES:
        await query.answer(
            "Сначала верните заявку в работу через смену статуса",
            show_alert=True,
        )
        return
    draft = ReplyDraft.from_order(order)
    data = await state.get_data()
    sent = await message.answer(
        format_builder(draft, markup_percent=settings.markup_percent),
        reply_markup=builder_keyboard(draft),
    )
    old_chat = data.get("ui_chat_id")
    old_message = data.get("ui_message_id")
    await state.set_state(ReplyBuilder.menu)
    await state.update_data(
        **draft.to_state(),
        ui_chat_id=sent.chat.id,
        ui_message_id=sent.message_id,
    )
    if (
        isinstance(old_chat, int)
        and isinstance(old_message, int)
        and old_message != sent.message_id
    ):
        try:
            await bot.edit_message_text(
                "Этот черновик закрыт. Ниже открыт новый конструктор.",
                chat_id=old_chat,
                message_id=old_message,
            )
        except TelegramAPIError:
            logger.debug("Старый конструктор уже нельзя изменить", exc_info=True)
    await query.answer()


@router.callback_query(ReplyCB.filter(F.action.in_({"price", "delivery", "comment", "photo"})))
async def ask_reply_field(
    query: CallbackQuery,
    callback_data: ReplyCB,
    state: FSMContext,
    db: Database,
) -> None:
    try:
        draft = await _load_draft(state, callback_data.order_id, db)
    except ValueError as exc:
        await query.answer(str(exc), show_alert=True)
        return
    await state.set_state(FIELD_STATE[callback_data.action])
    await state.update_data(**draft.to_state())
    await show_screen(
        state,
        PROMPTS[callback_data.action],
        builder_input_keyboard(draft.order_id),
        prefer=as_message(query.message),
    )
    await query.answer()


@router.callback_query(ReplyCB.filter(F.action == "clear_photo"))
async def clear_reply_photo(
    query: CallbackQuery,
    callback_data: ReplyCB,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    try:
        draft = (await _load_draft(state, callback_data.order_id, db)).with_photo(None)
    except ValueError as exc:
        await query.answer(str(exc), show_alert=True)
        return
    await _render_builder(state, draft, settings, prefer=as_message(query.message))
    await query.answer("Фото убрано")


@router.callback_query(ReplyCB.filter(F.action == "back"))
async def back_to_builder(
    query: CallbackQuery,
    callback_data: ReplyCB,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    try:
        draft = await _load_draft(state, callback_data.order_id, db)
    except ValueError as exc:
        await query.answer(str(exc), show_alert=True)
        return
    await _render_builder(state, draft, settings, prefer=as_message(query.message))
    await query.answer()


@router.callback_query(ReplyCB.filter(F.action == "cancel"))
async def cancel_builder(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    message = as_message(query.message)
    if message is not None:
        await edit_or_answer(message, "Конструктор закрыт.", admin_main_keyboard())
    await query.answer()


@router.callback_query(ReplyCB.filter(F.action == "send"))
async def send_reply(
    query: CallbackQuery,
    callback_data: ReplyCB,
    state: FSMContext,
    db: Database,
    settings: Settings,
    bot: Bot,
) -> None:
    try:
        draft = await _load_draft(state, callback_data.order_id, db)
    except ValueError as exc:
        await query.answer(str(exc), show_alert=True)
        return
    if not draft.can_send:
        await query.answer("Укажите цену или комментарий", show_alert=True)
        return
    order = await db.get_order(draft.order_id)
    if order is None:
        await query.answer("Заявка не найдена", show_alert=True)
        return
    if order.status in CLOSED_STATUSES:
        await query.answer(
            "По завершённой или отменённой заявке ответ не отправляется",
            show_alert=True,
        )
        return
    already_answered = order.status == STATUS_ANSWERED or _has_saved_answer(order)
    updated = await db.update_order(
        draft.order_id,
        status=STATUS_ANSWERED,
        price_cny=draft.price_cny,
        price_rub=draft.price_rub,
        price_usd=draft.price_usd,
        delivery_time=draft.delivery_time,
        assistant_comment=draft.assistant_comment,
        assistant_photo_id=draft.assistant_photo_id,
    )
    if updated is None:
        await query.answer("Заявка не найдена", show_alert=True)
        return
    delivered = await notify_user(
        bot,
        updated.user_id,
        format_offer(updated, updated=already_answered),
        reply_markup=offer_keyboard(updated.id),
        photo_id=updated.assistant_photo_id,
    )
    await state.clear()
    message = as_message(query.message)
    if delivered:
        text = f"Ответ по заявке <b>#{updated.id}</b> отправлен клиенту."
    else:
        text = (
            f"Ответ по заявке <b>#{updated.id}</b> сохранён, "
            "но сообщение клиенту не доставлено."
        )
    if message is not None:
        await edit_or_answer(message, text, admin_order_keyboard(updated))
    await query.answer("Отправлено" if delivered else "Сохранено, клиент не получил")


@router.message(ReplyBuilder.price, F.text)
async def save_price(
    message: Message,
    state: FSMContext,
    settings: Settings,
    currency: CurrencyService,
) -> None:
    if message.text is None:
        return
    try:
        draft = ReplyDraft.from_state(await state.get_data())
    except ValueError as exc:
        await message.answer(str(exc))
        return
    raw = message.text.strip()
    try:
        if raw.casefold() in CLEAR_TOKENS:
            draft = draft.without_price()
        else:
            draft = draft.with_price(currency.convert(parse_cny(raw)))
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await try_delete(message)
    await _render_builder(state, draft, settings, anchor=message)


@router.message(ReplyBuilder.price)
async def price_expected(message: Message) -> None:
    await message.answer("Введите цену числом, например 199 или 199.5.")


@router.message(ReplyBuilder.delivery, F.text)
async def save_delivery(message: Message, state: FSMContext, settings: Settings) -> None:
    await _save_text_field(message, state, settings, kind="delivery")


@router.message(ReplyBuilder.delivery)
async def delivery_expected(message: Message) -> None:
    await message.answer("Пришлите срок текстом, например «10–14 дней».")


@router.message(ReplyBuilder.comment, F.text)
async def save_comment(message: Message, state: FSMContext, settings: Settings) -> None:
    await _save_text_field(message, state, settings, kind="comment")


@router.message(ReplyBuilder.comment)
async def comment_expected(message: Message) -> None:
    await message.answer("Пришлите комментарий текстом.")


@router.message(ReplyBuilder.photo, F.photo)
async def save_reply_photo(message: Message, state: FSMContext, settings: Settings) -> None:
    if not message.photo:
        return
    try:
        draft = ReplyDraft.from_state(await state.get_data()).with_photo(
            message.photo[-1].file_id
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await try_delete(message)
    await _render_builder(state, draft, settings, anchor=message)


@router.message(ReplyBuilder.photo)
async def photo_expected(message: Message) -> None:
    await message.answer("Пришлите фотографию товара.")


@router.message(ReplyBuilder.menu)
async def builder_hint(message: Message) -> None:
    await message.answer("Меняйте ответ кнопками под карточкой конструктора.")


@router.message()
async def admin_fallback(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        await message.answer(
            "Жду данные для конструктора или нажмите кнопку под ним. /cancel — сброс."
        )
        return
    await message.answer("Панель ассистента.", reply_markup=admin_main_keyboard())


@router.callback_query()
async def admin_callback_fallback(query: CallbackQuery) -> None:
    await query.answer()


async def _save_text_field(
    message: Message,
    state: FSMContext,
    settings: Settings,
    *,
    kind: str,
) -> None:
    if message.text is None:
        return
    try:
        draft = ReplyDraft.from_state(await state.get_data())
        if kind == "delivery":
            draft = draft.with_delivery(message.text)
        else:
            draft = draft.with_comment(message.text)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await try_delete(message)
    await _render_builder(state, draft, settings, anchor=message)


def _tz(settings: Settings) -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def _has_saved_answer(order: Order) -> bool:
    return order.price_cny is not None or bool(order.assistant_comment)
