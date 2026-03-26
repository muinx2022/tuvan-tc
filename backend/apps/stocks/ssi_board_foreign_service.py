from __future__ import annotations

from decimal import Decimal
from typing import Any

import requests

BOARD_ENDPOINTS = {
    "hose": "https://iboard-query.ssi.com.vn/stock/exchange/hose?boardId=MAIN",
    "hnx": "https://iboard-query.ssi.com.vn/stock/exchange/hnx?boardId=MAIN",
    "upcom": "https://iboard-query.ssi.com.vn/stock/exchange/upcom?boardId=MAIN",
}
DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://iboard.ssi.com.vn",
    "Referer": "https://iboard.ssi.com.vn/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
}


def _valid_ticker(value: str | None) -> bool:
    ticker = (value or "").strip().upper()
    return len(ticker) == 3 and ticker.isalpha()


def _to_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _to_decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def fetch_foreign_board_snapshots(timeout_seconds: int = 30) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    for exchange, url in BOARD_ENDPOINTS.items():
        response = session.get(url, timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data") or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("stockSymbol") or "").strip().upper()
            if not _valid_ticker(ticker):
                continue
            buy_vol = _to_int(row.get("buyForeignQtty"))
            sell_vol = _to_int(row.get("sellForeignQtty"))
            buy_val = _to_decimal(row.get("buyForeignValue"))
            sell_val = _to_decimal(row.get("sellForeignValue"))
            merged[ticker] = {
                "ticker": ticker,
                "sourceExchange": exchange.upper(),
                "foreignBuyVolTotal": buy_vol,
                "foreignSellVolTotal": sell_vol,
                "foreignBuyValTotal": buy_val,
                "foreignSellValTotal": sell_val,
                "netForeignVol": buy_vol - sell_vol,
                "netForeignVal": buy_val - sell_val,
                "rawPayload": row,
            }
    return merged
