"""Конвертация юаней в цены для клиента."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from bot.config import Settings

_TWOPLACES = Decimal("0.01")
_MAX_CNY = Decimal("100000000")
_CNY_WORDS = ("юаней", "юаня", "юань", "cny", "rmb", "¥", "￥")


@dataclass(frozen=True, slots=True)
class ConvertedPrice:
    """Цена закупки и цена для клиента после наценки."""

    raw_cny: Decimal
    price_cny: Decimal
    price_rub: Decimal
    price_usd: Decimal
    markup_percent: Decimal


class CurrencyService:
    """Считает ¥, ₽ и $ от суммы в юанях.

    Наценка применяется к юаням, затем умножается на курс.
    Клиент видит уже наценённую цену во всех трёх валютах.
    """

    def __init__(self, settings: Settings) -> None:
        self._rub = Decimal(str(settings.cny_to_rub))
        self._usd = Decimal(str(settings.cny_to_usd))
        self._markup = Decimal(str(settings.markup_percent))

    def convert(self, amount_cny: Decimal) -> ConvertedPrice:
        if amount_cny <= 0:
            raise ValueError("Цена должна быть больше нуля")
        if amount_cny > _MAX_CNY:
            raise ValueError("Слишком большая цена")
        factor = Decimal(1) + (self._markup / Decimal(100))
        marked = _money(amount_cny * factor)
        return ConvertedPrice(
            raw_cny=_money(amount_cny),
            price_cny=marked,
            price_rub=_money(marked * self._rub),
            price_usd=_money(marked * self._usd),
            markup_percent=self._markup,
        )


def parse_cny(raw: str) -> Decimal:
    """Принимает «199», «199,5» или «199 ¥»."""

    text = raw.strip().lower().replace(" ", "").replace(",", ".")
    for word in _CNY_WORDS:
        text = text.replace(word, "")
    if not text or text.count(".") > 1:
        raise ValueError("Введите цену числом, например 199 или 199.5")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("Введите цену числом, например 199 или 199.5") from exc
    if value <= 0:
        raise ValueError("Цена должна быть больше нуля")
    if value > _MAX_CNY:
        raise ValueError("Слишком большая цена")
    return value


def _money(value: Decimal) -> Decimal:
    return value.quantize(_TWOPLACES, rounding=ROUND_HALF_UP)
