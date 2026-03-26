from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from django.utils import timezone

from apps.stocks.models import StockHistory
from common.exceptions import BadRequestError

VN_DATE = "%d/%m/%Y"


def _text(node: dict, field: str) -> str:
    value = node.get(field)
    if value is None:
        return ""
    return str(value).strip()


def _decimal(node: dict, field: str) -> Decimal | None:
    raw = _text(node, field)
    if not raw:
        return None
    try:
        return Decimal(raw)
    except Exception:
        return None


def _long_val(node: dict, field: str) -> int | None:
    raw = _text(node, field)
    if not raw:
        return None
    try:
        return int(raw.split(".")[0])
    except Exception:
        return None


def parse_trading_date(raw: str | None) -> date | None:
    if not raw or not str(raw).strip():
        return None
    value = str(raw).strip()
    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        if "/" in value:
            return datetime.strptime(value, VN_DATE).date()
        return date.fromisoformat(value)
    except Exception:
        return None


@dataclass
class ParsedHistoryBatch:
    histories: list[StockHistory]


def parse_history_payload(root: dict, ticker: str, max_records: int | None) -> ParsedHistoryBatch:
    data = root.get("data")
    if not isinstance(data, list):
        raise BadRequestError(f"SSI history response is invalid for ticker {ticker}")

    by_date: dict[date, StockHistory] = {}
    created_at = timezone.now()
    for item in data:
        trading_date = parse_trading_date(_text(item, "tradingDate"))
        if trading_date is None:
            continue
        by_date[trading_date] = StockHistory(
            ticker=ticker,
            trading_date=trading_date,
            open_price=_decimal(item, "open"),
            high_price=_decimal(item, "high"),
            low_price=_decimal(item, "low"),
            close_price=_decimal(item, "close"),
            volume=_long_val(item, "volume"),
            avg_price=_decimal(item, "avgPrice"),
            price_changed=_decimal(item, "priceChanged"),
            per_price_change=_decimal(item, "perPriceChange"),
            total_match_vol=_long_val(item, "totalMatchVol"),
            total_match_val=_decimal(item, "totalMatchVal"),
            foreign_buy_vol_total=_long_val(item, "foreignBuyVolTotal"),
            foreign_sell_vol_total=_long_val(item, "foreignSellVolTotal"),
            raw_payload=json.dumps(item),
            created_at=created_at,
        )
    histories = sorted(by_date.values(), key=lambda item: item.trading_date, reverse=True)
    if max_records is not None and len(histories) > max_records:
        histories = histories[:max_records]
    return ParsedHistoryBatch(histories=sorted(histories, key=lambda item: item.trading_date))
