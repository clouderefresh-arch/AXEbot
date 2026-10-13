"""Курсы ЦБ и разбор суммы в юанях."""

import asyncio
from decimal import Decimal

import pytest

from bot.services.currency import (
    ExchangeRates,
    convert_amount,
    parse_cbr_xml,
    parse_cny,
    CurrencyService,
)
from tests.conftest import make_settings

_CBR_XML = """<?xml version="1.0" encoding="windows-1251"?>
<ValCurs Date="14.10.2026" name="Foreign Currency Market">
  <Valute ID="R01235">
    <CharCode>USD</CharCode>
    <Nominal>1</Nominal>
    <Value>92,5000</Value>
  </Valute>
  <Valute ID="R01375">
    <CharCode>CNY</CharCode>
    <Nominal>10</Nominal>
    <Value>128,0000</Value>
  </Valute>
</ValCurs>
"""


def test_parse_cbr_xml_uses_nominal() -> None:
    rates = parse_cbr_xml(_CBR_XML)
    assert rates.source == "cbr"
    assert rates.as_of == "14.10.2026"
    assert rates.cny_to_rub == Decimal("12.800000")
    assert rates.cny_to_usd == Decimal("0.138378")
    assert "ЦБ РФ" in rates.note()
    assert "14.10.2026" in rates.note()


def test_parse_cbr_xml_requires_both_currencies() -> None:
    with pytest.raises(ValueError):
        parse_cbr_xml("<ValCurs Date='01.01.2026'><Valute><CharCode>USD</CharCode><Nominal>1</Nominal><Value>90</Value></Valute></ValCurs>")


def test_convert_without_markup() -> None:
    rates = ExchangeRates(Decimal("10"), Decimal("0.2"), "14.10.2026", "cbr")
    price = convert_amount(Decimal("100"), rates, markup_percent=Decimal("0"))
    assert price.raw_cny == Decimal("100.00")
    assert price.price_cny == Decimal("100.00")
    assert price.price_rub == Decimal("1000.00")
    assert price.price_usd == Decimal("20.00")


def test_convert_applies_markup_before_rates() -> None:
    rates = ExchangeRates(Decimal("12.80"), Decimal("0.14"), "14.10.2026", "cbr")
    price = convert_amount(Decimal("100"), rates, markup_percent=Decimal("15"))
    assert price.price_cny == Decimal("115.00")
    assert price.price_rub == Decimal("1472.00")
    assert price.price_usd == Decimal("16.10")


def test_service_prefers_cbr_over_config() -> None:
    asyncio.run(_service_prefers_cbr())


async def _service_prefers_cbr() -> None:
    calls = 0

    async def fetcher() -> ExchangeRates:
        nonlocal calls
        calls += 1
        return ExchangeRates(Decimal("10"), Decimal("2"), "14.10.2026", "cbr")

    service = CurrencyService(
        make_settings(cny_to_rub=1, cny_to_usd=1, markup_percent=0),
        fetcher=fetcher,
    )
    first = await service.convert(Decimal("100"))
    second = await service.convert(Decimal("100"))
    assert first.price_rub == Decimal("1000.00")
    assert second.price_usd == Decimal("200.00")
    assert calls == 1


def test_service_falls_back_to_config() -> None:
    asyncio.run(_service_falls_back())


async def _service_falls_back() -> None:
    async def fetcher() -> ExchangeRates:
        raise RuntimeError("cbr down")

    service = CurrencyService(
        make_settings(cny_to_rub=10, cny_to_usd="0.2", markup_percent=0),
        fetcher=fetcher,
    )
    rates = await service.get_rates()
    price = await service.convert(Decimal("100"))
    assert rates.source == "config"
    assert "недоступен" in rates.note()
    assert price.price_rub == Decimal("1000.00")
    assert price.price_usd == Decimal("20.00")


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
