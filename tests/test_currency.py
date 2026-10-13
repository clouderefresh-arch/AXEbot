"""Курсы и разбор суммы в юанях."""

from decimal import Decimal

import pytest

from bot.services.currency import CurrencyService, parse_cny
from tests.conftest import make_settings


def test_convert_without_markup() -> None:
    service = CurrencyService(
        make_settings(cny_to_rub=10, cny_to_usd=Decimal("0.2"), markup_percent=0)
    )
    price = service.convert(Decimal("100"))
    assert price.raw_cny == Decimal("100.00")
    assert price.price_cny == Decimal("100.00")
    assert price.price_rub == Decimal("1000.00")
    assert price.price_usd == Decimal("20.00")


def test_convert_applies_markup_before_rates() -> None:
    service = CurrencyService(
        make_settings(cny_to_rub="12.80", cny_to_usd="0.14", markup_percent=15)
    )
    price = service.convert(Decimal("100"))
    assert price.price_cny == Decimal("115.00")
    assert price.price_rub == Decimal("1472.00")
    assert price.price_usd == Decimal("16.10")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("199", Decimal("199")),
        ("199.5", Decimal("199.5")),
        ("199,5", Decimal("199.5")),
        ("  199 ¥  ", Decimal("199")),
        ("1 250,50", Decimal("1250.50")),
    ],
)
def test_parse_cny(raw: str, expected: Decimal) -> None:
    assert parse_cny(raw) == expected


@pytest.mark.parametrize("raw", ["", "0", "-5", "десять", "10-14"])
def test_parse_cny_rejects_bad_values(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_cny(raw)
