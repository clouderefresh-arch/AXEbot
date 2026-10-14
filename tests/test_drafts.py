"""Черновики заявки и ответа."""

import pytest

from bot.services.currency import ConvertedPrice
from bot.services.drafts import OrderDraft, ReplyDraft
from decimal import Decimal


def test_order_draft_becomes_ready() -> None:
    draft = OrderDraft().with_description("Кроссовки").with_urgency("urgent")
    assert draft.ready()
    assert not OrderDraft(description="Кроссовки").ready()


def test_extra_clear_token() -> None:
    draft = OrderDraft(budget="5000").with_extra("budget", "-")
    assert draft.budget is None


def test_description_too_short() -> None:
    with pytest.raises(ValueError):
        OrderDraft().with_description("  ок ")


def test_reply_requires_price_or_comment() -> None:
    empty = ReplyDraft(order_id=1)
    assert not empty.can_send
    assert empty.with_comment("есть в наличии").can_send
    priced = empty.with_price(
        ConvertedPrice(
            raw_cny=Decimal("10"),
            price_cny=Decimal("10"),
            price_rub=Decimal("100"),
            price_usd=Decimal("2"),
            markup_percent=Decimal("0"),
        )
    )
    assert priced.can_send
    assert priced.without_price().can_send is False


def test_reply_roundtrip_state() -> None:
    draft = ReplyDraft(order_id=7, assistant_comment="ок", delivery_time="10 дней")
    restored = ReplyDraft.from_state(draft.to_state())
    assert restored.order_id == 7
    assert restored.assistant_comment == "ок"
    assert restored.delivery_time == "10 дней"
