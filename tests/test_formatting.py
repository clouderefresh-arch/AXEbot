"""Карточки и callback data."""

from bot.database.db import Order
from bot.keyboards.admin import builder_keyboard
from bot.keyboards.callbacks import ReplyCB
from bot.services.drafts import ReplyDraft
from bot.services.formatting import format_builder, format_client_preview, format_price_values
from bot.services.drafts import OrderDraft


def test_price_line_has_three_currencies() -> None:
    assert format_price_values(115, 1472, 16.1) == "115.00 ¥ (1 472.00 ₽ / 16.10 $)"


def test_preview_escapes_html() -> None:
    text = format_client_preview(
        OrderDraft(description="<b>hack</b>", urgency="low", reference_link="https://example.com/a b")
    )
    assert "&lt;b&gt;hack&lt;/b&gt;" in text
    assert "<a href=" not in text
    assert "https://example.com/a b" in text


def test_builder_shows_markup_note() -> None:
    text = format_builder(
        ReplyDraft(
            order_id=4,
            raw_cny=100,
            price_cny=115,
            price_rub=1472,
            price_usd=16.1,
            delivery_time="10-14 дней",
        ),
        markup_percent=15,
    )
    assert "заявке #4" in text
    assert "115.00 ¥" in text
    assert "1 472.00 ₽" in text
    assert "16.10 $" in text
    assert "наценка 15%" in text


def test_safe_link_is_clickable() -> None:
    text = format_client_preview(
        OrderDraft(
            description="сумка",
            urgency="medium",
            reference_link="https://example.com/item",
        )
    )
    assert '<a href="https://example.com/item">' in text


def test_builder_callback_roundtrip() -> None:
    draft = ReplyDraft(order_id=12, price_cny=10, price_rub=100, price_usd=2)
    packed = builder_keyboard(draft).inline_keyboard[-1][0].callback_data
    assert packed is not None
    unpacked = ReplyCB.unpack(packed)
    assert unpacked.action == "cancel"
    assert unpacked.order_id == 12
    assert len(packed.encode()) <= 64


def test_order_card_uses_saved_prices() -> None:
    order = Order(
        id=3,
        user_id=1,
        user_name="Анна",
        description="сумка",
        user_photo_id=None,
        urgency="low",
        status="answered",
        budget=None,
        size=None,
        color=None,
        reference_link=None,
        price_cny=10,
        price_rub=100,
        price_usd=1.5,
        delivery_time=None,
        assistant_comment="есть",
        assistant_photo_id=None,
        created_at="2026-10-13T10:00:00+00:00",
        updated_at=None,
    )
    from zoneinfo import ZoneInfo

    from bot.services.formatting import format_offer

    text = format_offer(order, updated=False)
    assert "10.00 ¥" in text
    assert "100.00 ₽" in text
    assert "1.50 $" in text
