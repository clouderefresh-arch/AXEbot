"""Общие команды: старт, помощь, сброс FSM."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import Settings
from bot.keyboards.admin import admin_main_keyboard
from bot.keyboards.client import client_reply_menu

router = Router(name="common")

CLIENT_START = (
    "<b>AXEbot</b> — персональный подбор товаров.\n\n"
    "Кнопки внизу: «Новая заявка», «Мои заявки», «Помощь».\n"
    "В заявке меню приходит сообщением в чат: нажмите поле и введите значение."
)

ADMIN_START = (
    "<b>Панель ассистента</b>\n\n"
    "Новые заявки приходят сюда. Кнопка «Ответить» открывает конструктор: "
    "цена в юанях пересчитывается в рубли и доллары по курсу ЦБ РФ, затем карточка уходит клиенту."
)

CLIENT_HELP = (
    "<b>Как подать заявку</b>\n"
    "1. «Новая заявка» — в чат приходит меню\n"
    "2. Нажмите «Добавить описание», «Добавить фото», «Добавить срочность» "
    "или другое поле\n"
    "3. Введите значение следующим сообщением. «-» очищает бюджет, размер, цвет и ссылку\n"
    "4. «Отправить заявку» на том же меню. Нужны описание и срочность\n\n"
    "Фото бот не удаляет. Когда ассистент ответит, можно принять предложение, "
    "отклонить его или задать вопрос.\n"
    "/cancel — выйти из заявки.\n"
    "/orders — список ваших заявок."
)

ADMIN_HELP = (
    "<b>Как ответить на заявку</b>\n"
    "1. «Взять в работу», когда начинаете поиск\n"
    "2. «Ответить» — конструктор цены, срока, фото и комментария\n"
    "3. Цена вводится в юанях и сразу пересчитывается по курсу ЦБ РФ\n"
    "4. «Отправить клиенту» — нужна цена или комментарий\n\n"
    "Открытые заявки напоминают о себе каждые 90 минут, "
    "кроме тихих часов 22:00–09:00. В 09:00 приходит утренняя сводка.\n"
    "/orders — открытые заявки.\n"
    "/cancel — закрыть конструктор."
)


def _is_admin(message: Message, settings: Settings) -> bool:
    return bool(message.from_user and message.from_user.id == settings.admin_id)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, settings: Settings) -> None:
    await state.clear()
    if _is_admin(message, settings):
        await message.answer(ADMIN_START, reply_markup=admin_main_keyboard())
        return
    await message.answer(CLIENT_START, reply_markup=client_reply_menu())


@router.message(Command("help"))
async def help_command(message: Message, settings: Settings) -> None:
    if _is_admin(message, settings):
        await message.answer(ADMIN_HELP, reply_markup=admin_main_keyboard())
        return
    await message.answer(CLIENT_HELP, reply_markup=client_reply_menu())


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext, settings: Settings) -> None:
    current = await state.get_state()
    await state.clear()
    menu = admin_main_keyboard() if _is_admin(message, settings) else client_reply_menu()
    if current is None:
        await message.answer("Сейчас нечего отменять.", reply_markup=menu)
        return
    await message.answer("Текущий шаг сброшен.", reply_markup=menu)


@router.message(Command("menu"))
async def menu_command(message: Message, settings: Settings) -> None:
    if _is_admin(message, settings):
        await message.answer("Панель ассистента.", reply_markup=admin_main_keyboard())
        return
    await message.answer("Меню.", reply_markup=client_reply_menu())
