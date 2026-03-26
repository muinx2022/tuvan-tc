from __future__ import annotations

import json
from dataclasses import dataclass

from bs4 import BeautifulSoup

from common.exceptions import BadRequestError


@dataclass
class VietstockSessionInfo:
    token: str
    cookie_header: str


def extract_verification_token(html: str, ticker: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    token_input = soup.find("input", attrs={"name": "__RequestVerificationToken"})
    if token_input is None:
        raise BadRequestError(f"Unable to extract Vietstock verification token for ticker {ticker}")
    token = token_input.get("value")
    if token is None or not str(token).strip():
        raise BadRequestError(f"Unable to extract Vietstock verification token value for ticker {ticker}")
    return str(token).strip()


def parse_chart_payload(payload: dict, ticker: str) -> tuple[dict[int, dict], dict[int, list[dict]]]:
    data = payload.get("data") or {}
    chart_nodes = data.get("InfoChart") or []
    detail_nodes = data.get("InfoChartDetail") or []
    if not isinstance(chart_nodes, list) or not isinstance(detail_nodes, list):
        raise BadRequestError(f"Vietstock chart payload is invalid for ticker {ticker}")

    chart_by_id: dict[int, dict] = {}
    for node in chart_nodes:
        chart_by_id[long_value(node, "ChartMenuID")] = node

    detail_by_id: dict[int, list[dict]] = {}
    for node in detail_nodes:
        cid = long_value(node, "ChartMenuID")
        detail_by_id.setdefault(cid, []).append(node)
    return chart_by_id, detail_by_id


def text(node: dict, field: str) -> str | None:
    value = node.get(field)
    if value is None:
        return None
    return str(value).strip() or None


def long_value(node: dict, field: str) -> int:
    value = node.get(field)
    if value is None:
        raise BadRequestError(f"Missing field: {field}")
    return int(value)


def nullable_int(node: dict, field: str) -> int | None:
    value = node.get(field)
    return None if value is None else int(value)


def report_type(report_term_type_id: int | None) -> str:
    return "YEAR" if report_term_type_id == 1 else "QUARTER"


def term_rank(term: str | None) -> int:
    if not term or not str(term).strip():
        return -999999
    raw = str(term).strip()
    try:
        if raw.startswith("Q"):
            parts = raw.split("/")
            return int(parts[1]) * 10 + int(parts[0][1:])
        if raw.startswith("N/"):
            return int(raw[2:]) * 10 + 9
    except Exception:
        return -999999
    return -999999


def latest_report_period(chart_details: list[dict]) -> str | None:
    best = None
    best_rank = -999999
    for node in chart_details:
        value = text(node, "NormTerm")
        if not value:
            continue
        rank = term_rank(value)
        if rank > best_rank:
            best_rank = rank
            best = value
    return best


def write_chart_json(chart_node: dict, chart_details: list[dict]) -> str:
    return json.dumps({"chart": chart_node, "details": chart_details})
