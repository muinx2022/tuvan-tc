from __future__ import annotations

from dataclasses import dataclass

from common.exceptions import BadRequestError


@dataclass
class ParsedVpsSymbol:
    ticker: str
    organ_code: str | None
    organ_name: str | None
    organ_short_name: str | None
    icb_code: str | None
    industry_name: str | None
    listing_date: str | None


def _text(node: dict, field: str) -> str:
    value = node.get(field)
    if value is None:
        return ""
    return str(value).strip()


def parse_company_basic_payload(root: dict) -> tuple[list[ParsedVpsSymbol], int]:
    data = root.get("data")
    if not isinstance(data, list):
        raise BadRequestError("VPS response is invalid")

    by_ticker: dict[str, ParsedVpsSymbol] = {}
    for item in data:
        ticker = _text(item, "Ticker").upper()
        if not ticker:
            continue
        industry_name = _text(item, "IcbName2") or None
        by_ticker[ticker] = ParsedVpsSymbol(
            ticker=ticker,
            organ_code=_text(item, "OrganCode") or None,
            organ_name=_text(item, "OrganName") or None,
            organ_short_name=_text(item, "OrganShortName") or None,
            icb_code=_text(item, "IcbCode") or None,
            industry_name=industry_name,
            listing_date=_text(item, "ListingDate") or None,
        )
    return list(by_ticker.values()), len(data)
