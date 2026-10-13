"""Тексты карточек заявки, предпросмотра и конструктора."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from zoneinfo import ZoneInfo

from bot.constants import STATUS_LABELS, URGENCY_LABELS
from bot.database.db import Order
from bot.services.drafts import OrderDraft, ReplyDraft

_TWOPLACES = Decimal("0.01")


def format_amount(value: float | Decimal | None) -> str:
    if value is None:
        return "—"
    quantized = Decimal(str(value)).quantize(_TWOPLACES, rounding=ROUND_HALF_UP)
    return f"{quantized:,.2f}".replace(",", " ")


def format_percent(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def format_timestamp(value: str, tz: ZoneInfo) -> str:
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return value
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(tz).strftime("%d.%m.%Y %H:%M")


def format_link(url: str | None) -> str:
    if not url:
        return "не указана"
    cleaned = url.strip()
    safe = cleaned.startswith(("http://", "https://")) and not any(
        char in cleaned for char in (' ', '"', "'", "<", ">", "\n", "\r")
    )
    if safe and len(cleaned) <= 500:
        visible = cleaned if len(cleaned) <= 80 else cleaned[:77] + "..."
        return f'<a href="{escape(cleaned, quote=True)}">{escape(visible)}</a>'
    return escape(cleaned)


def format_price_values(
    cny: float | None,
    rub: float | None,
    usd: float | None,
) -> str:
    if cny is None and rub is None and usd is None:
        return "—"
    if cny is not None and rub is not None and usd is not None:
        return (
            f"{format_amount(cny)} ¥ "
            f"({format_amount(rub)} ₽ / {format_amount(usd)} $)"
        )
    parts: list[str] = []
    if cny is not None:
        parts.append(f"{format_amount(cny)} ¥")
    if rub is not None:
        parts.append(f"{format_amount(rub)} ₽")
    if usd is not None:
        parts.append(f"{format_amount(usd)} $")
    return " · ".join(parts)


def format_client_preview(draft: OrderDraft) -> str:
    urgency = URGENCY_LABELS.get(draft.urgency or "", "не выбрана")
    return "\n".join(
        (
            "<b>Предпросмотр заявки</b>",
            "",
            f"<b>Описание:</b> {escape(draft.description) if draft.description else '—'}",
            f"<b>Фото:</b> {'прикреплено' if draft.user_photo_id else 'нет'}",
            f"<b>Срочность:</b> {escape(urgency)}",
            f"<b>Бюджет:</b> {escape(draft.budget) if draft.budget else 'не указан'}",
            f"<b>Размер:</b> {escape(draft.size) if draft.size else 'не указан'}",
            f"<b>Цвет:</b> {escape(draft.color) if draft.color else 'не указан'}",
            f"<b>Ссылка:</b> {format_link(draft.reference_link)}",
        )
    )


def format_builder(draft: ReplyDraft, *, markup_percent: float) -> str:
    price = format_price_values(draft.price_cny, draft.price_rub, draft.price_usd)
    if (
        draft.raw_cny is not None
        and draft.price_cny is not None
        and markup_percent > 0
    ):
        price += (
            f"\n  введено {format_amount(draft.raw_cny)} ¥, "
            f"наценка {format_percent(markup_percent)}%"
        )
    delivery = escape(draft.delivery_time) if draft.delivery_time else "—"
    photo = "прикреплено" if draft.assistant_photo_id else "нет"
    comment = escape(draft.assistant_comment) if draft.assistant_comment else "—"
    return "\n".join(
        (
            f"<b>Формирование ответа по заявке #{draft.order_id}</b>",
            f"• Цена: {price}",
            f"• Сроки доставки: {delivery}",
            f"• Фото: {photo}",
            f"• Комментарий: {comment}",
        )
    )


def format_admin_card(order: Order, *, tz: ZoneInfo) -> str:
    lines = [
        f"<b>Заявка #{order.id}</b>",
        f"<b>Статус:</b> {escape(STATUS_LABELS.get(order.status, order.status))}",
        (
            f"<b>Клиент:</b> {escape(order.user_name or '—')} "
            f"(<code>{order.user_id}</code>)"
        ),
        f"<b>Создана:</b> {escape(format_timestamp(order.created_at, tz))}",
        "",
        f"<b>Описание:</b> {escape(order.description)}",
        f"<b>Фото клиента:</b> {'есть' if order.user_photo_id else 'нет'}",
        f"<b>Срочность:</b> {escape(URGENCY_LABELS.get(order.urgency, order.urgency))}",
        f"<b>Бюджет:</b> {escape(order.budget) if order.budget else 'не указан'}",
        f"<b>Размер:</b> {escape(order.size) if order.size else 'не указан'}",
        f"<b>Цвет:</b> {escape(order.color) if order.color else 'не указан'}",
        f"<b>Ссылка:</b> {format_link(order.reference_link)}",
    ]
    if _has_answer(order):
        lines.extend(
            (
                "",
                "<b>Текущий ответ</b>",
                (
                    "<b>Цена:</b> "
                    f"{format_price_values(order.price_cny, order.price_rub, order.price_usd)}"
                ),
                f"<b>Сроки:</b> {escape(order.delivery_time) if order.delivery_time else '—'}",
                f"<b>Фото:</b> {'прикреплено' if order.assistant_photo_id else 'нет'}",
                (
                    "<b>Комментарий:</b> "
                    f"{escape(order.assistant_comment) if order.assistant_comment else '—'}"
                ),
            )
        )
    return "\n".join(lines)


def format_client_order(order: Order, *, tz: ZoneInfo) -> str:
    lines = [
        f"<b>Заявка #{order.id}</b>",
        f"<b>Статус:</b> {escape(STATUS_LABELS.get(order.status, order.status))}",
        f"<b>Создана:</b> {escape(format_timestamp(order.created_at, tz))}",
        "",
        f"<b>Описание:</b> {escape(order.description)}",
        f"<b>Фото:</b> {'прикреплено' if order.user_photo_id else 'нет'}",
        f"<b>Срочность:</b> {escape(URGENCY_LABELS.get(order.urgency, order.urgency))}",
        f"<b>Бюджет:</b> {escape(order.budget) if order.budget else 'не указан'}",
        f"<b>Размер:</b> {escape(order.size) if order.size else 'не указан'}",
        f"<b>Цвет:</b> {escape(order.color) if order.color else 'не указан'}",
        f"<b>Ссылка:</b> {format_link(order.reference_link)}",
    ]
    if _has_answer(order):
        lines.extend(("", format_offer_body(order)))
    return "\n".join(lines)


def format_offer(order: Order, *, updated: bool) -> str:
    title = "Обновлённое предложение" if updated else "Предложение по заявке"
    return "\n".join(
        (
            f"<b>{title} #{order.id}</b>",
            f"<b>Товар:</b> {escape(order.description)}",
            "",
            format_offer_body(order),
        )
    )


def format_offer_body(order: Order) -> str:
    return "\n".join(
        (
            (
                "<b>Цена:</b> "
                f"{format_price_values(order.price_cny, order.price_rub, order.price_usd)}"
            ),
            f"<b>Сроки доставки:</b> {escape(order.delivery_time) if order.delivery_time else '—'}",
            f"<b>Комментарий:</b> {escape(order.assistant_comment) if order.assistant_comment else '—'}",
        )
    )


def format_order_list(title: str, orders: list[Order], *, total: int, offset: int) -> str:
    if not orders:
        return f"<b>{escape(title)}</b>\n\nПока пусто."
    lines = [f"<b>{escape(title)}</b>", f"Показаны {offset + 1}–{offset + len(orders)} из {total}", ""]
    for order in orders:
        urgency = URGENCY_LABELS.get(order.urgency, order.urgency)
        status = STATUS_LABELS.get(order.status, order.status)
        lines.append(
            f"<b>#{order.id}</b> · {escape(urgency)} · {escape(status)}\n"
            f"{escape(_short(order.description, 90))}"
        )
    return "\n".join(lines)


def format_reminder(orders: list[Order], *, total: int, moment: datetime) -> str:
    lines = [
        "<b>Напоминание по открытым заявкам</b>",
        escape(moment.strftime("%d.%m.%Y %H:%M")),
        f"Без ответа: {total}",
        "",
    ]
    for order in orders:
        urgency = URGENCY_LABELS.get(order.urgency, order.urgency)
        status = STATUS_LABELS.get(order.status, order.status)
        lines.append(
            f"#{order.id} · {escape(urgency)} · {escape(status)} · "
            f"{escape(_short(order.description, 60))}"
        )
    if total > len(orders):
        lines.append(f"\nИ ещё {total - len(orders)}. Откройте список кнопкой ниже.")
    return "\n".join(lines)


def client_status_text(order: Order) -> str:
    messages = {
        "pending": f"Заявка #{order.id} снова ожидает ассистента.",
        "in_progress": f"Ассистент взял заявку #{order.id} в работу.",
        "answered": (
            f"По заявке #{order.id} есть предложение. "
            "Откройте «Мои заявки», если карточка не пришла отдельным сообщением."
        ),
        "approved": f"Заявка #{order.id} отмечена как принятая.",
        "completed": f"Заявка #{order.id} завершена. Спасибо!",
        "canceled": f"Заявка #{order.id} отменена.",
    }
    return messages.get(order.status, f"Статус заявки #{order.id} обновлён.")


def _has_answer(order: Order) -> bool:
    return any(
        (
            order.price_cny is not None,
            order.delivery_time,
            order.assistant_comment,
            order.assistant_photo_id,
        )
    )


def _short(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"
