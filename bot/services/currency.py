"""Конвертация юаней по курсу ЦБ РФ."""

from __future__ import annotations

import logging
import socket
import ssl
import xml.etree.ElementTree as ET
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import aiohttp
import certifi

from bot.config import Settings

logger = logging.getLogger(__name__)

_TWOPLACES = Decimal("0.01")
_RATE_PLACES = Decimal("0.000001")
_MAX_CNY = Decimal("100000000")
_CNY_WORDS = ("юаней", "юаня", "юань", "cny", "rmb", "¥", "￥")
_CBR_URL = "https://www.cbr.ru/scripts/XML_daily.asp"
_RATE_TTL = timedelta(hours=1)

RateFetcher = Callable[[], Awaitable["ExchangeRates"]]


@dataclass(frozen=True)
class ExchangeRates:
    """Сколько рублей и долларов стоит 1 юань до наценки."""

    cny_to_rub: Decimal
    cny_to_usd: Decimal
    as_of: str
    source: str

    def note(self) -> str:
        rub = _rate(self.cny_to_rub)
        usd = _rate(self.cny_to_usd)
        if self.source == "cbr":
            when = f" на {self.as_of}" if self.as_of else ""
            return f"Курс ЦБ РФ{when}: 1 ¥ = {rub} ₽ / {usd} $"
        return (
            f"Запасной курс из настроек: 1 ¥ = {rub} ₽ / {usd} $. "
            "ЦБ РФ сейчас недоступен."
        )


@dataclass(frozen=True)
class ConvertedPrice:
    """Цена закупки и цена для клиента после наценки."""

    raw_cny: Decimal
    price_cny: Decimal
    price_rub: Decimal
    price_usd: Decimal
    markup_percent: Decimal


class CurrencyService:
    """Берёт курс юаня с сайта ЦБ и считает цену для клиента.

    Наценка применяется к юаням, затем умножается на курс.
    Если ЦБ не ответил, используется последний успешный курс, а если его ещё нет —
    числа CNY_TO_RUB и CNY_TO_USD из настроек.
    """

    def __init__(
        self,
        settings: Settings,
        fetcher: RateFetcher | None = None,
    ) -> None:
        self._settings = settings
        self._fetcher = fetcher or fetch_cbr_rates
        self._rates: ExchangeRates | None = None
        self._fetched_at: datetime | None = None

    async def get_rates(self) -> ExchangeRates:
        if self._is_fresh() and self._rates is not None:
            return self._rates
        try:
            rates = await self._fetcher()
        except Exception:
            logger.warning("Не удалось получить курс ЦБ РФ", exc_info=True)
            rates = self._rates or self.fallback_rates()
        else:
            logger.info("%s", rates.note())
        self._rates = rates
        self._fetched_at = datetime.now(timezone.utc)
        return rates

    def _is_fresh(self) -> bool:
        if self._rates is None or self._fetched_at is None:
            return False
        return datetime.now(timezone.utc) - self._fetched_at < _RATE_TTL

    def fallback_rates(self) -> ExchangeRates:
        return ExchangeRates(
            cny_to_rub=Decimal(str(self._settings.cny_to_rub)),
            cny_to_usd=Decimal(str(self._settings.cny_to_usd)),
            as_of="",
            source="config",
        )

    async def convert(self, amount_cny: Decimal) -> ConvertedPrice:
        rates = await self.get_rates()
        return convert_amount(
            amount_cny,
            rates,
            markup_percent=Decimal(str(self._settings.markup_percent)),
        )


def convert_amount(
    amount_cny: Decimal,
    rates: ExchangeRates,
    *,
    markup_percent: Decimal,
) -> ConvertedPrice:
    if amount_cny <= 0:
        raise ValueError("Цена должна быть больше нуля")
    if amount_cny > _MAX_CNY:
        raise ValueError("Слишком большая цена")
    factor = Decimal(1) + (markup_percent / Decimal(100))
    marked = _money(amount_cny * factor)
    return ConvertedPrice(
        raw_cny=_money(amount_cny),
        price_cny=marked,
        price_rub=_money(marked * rates.cny_to_rub),
        price_usd=_money(marked * rates.cny_to_usd),
        markup_percent=markup_percent,
    )


def parse_cbr_xml(payload: str) -> ExchangeRates:
    """Разбирает ежедневный XML ЦБ: https://www.cbr.ru/scripts/XML_daily.asp."""

    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("ЦБ вернул не XML") from exc
    per_unit: dict[str, Decimal] = {}
    for node in root.findall("Valute"):
        code = (node.findtext("CharCode") or "").strip().upper()
        if code not in {"USD", "CNY"}:
            continue
        nominal = _decimal(node.findtext("Nominal") or "1", label=code)
        value = _decimal(node.findtext("Value") or "", label=code)
        if nominal <= 0 or value <= 0:
            raise ValueError(f"Некорректный курс {code} в ответе ЦБ")
        per_unit[code] = (value / nominal).quantize(_RATE_PLACES, rounding=ROUND_HALF_UP)
    if "CNY" not in per_unit or "USD" not in per_unit:
        raise ValueError("В ответе ЦБ нет курса юаня или доллара")
    cny_rub = per_unit["CNY"]
    usd_rub = per_unit["USD"]
    return ExchangeRates(
        cny_to_rub=cny_rub,
        cny_to_usd=(cny_rub / usd_rub).quantize(_RATE_PLACES, rounding=ROUND_HALF_UP),
        as_of=(root.attrib.get("Date") or "").strip(),
        source="cbr",
    )


async def fetch_cbr_rates() -> ExchangeRates:
    timeout = aiohttp.ClientTimeout(total=15)
    context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=context, family=socket.AF_INET)
    headers = {"User-Agent": "AXEbot/1.0"}
    async with aiohttp.ClientSession(timeout=timeout, connector=connector, headers=headers) as session:
        async with session.get(_CBR_URL) as response:
            response.raise_for_status()
            raw = await response.read()
    return parse_cbr_xml(raw.decode("windows-1251"))


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


def _rate(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return f"{quantized:.4f}"


def _decimal(raw: str, *, label: str) -> Decimal:
    try:
        return Decimal(raw.strip().replace(" ", "").replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(f"Некорректное число {label} в ответе ЦБ") from exc
