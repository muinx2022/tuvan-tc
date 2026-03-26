from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from decimal import Decimal
from typing import Any

import requests

from common.exceptions import BadRequestError

SSI_FC_ACCESS_TOKEN_API = "https://fc-data.ssi.com.vn/api/v2/Market/AccessToken"
SSI_FC_DAILY_PRICE_API = "https://fc-data.ssi.com.vn/api/v2/Market/DailyStockPrice"
VN_DATE = "%d/%m/%Y"


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _int_value(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(Decimal(str(value)))
    except Exception:
        return None


class SsiForeignClient:
    def __init__(self, consumer_id: str, consumer_secret: str) -> None:
        self.consumer_id = (consumer_id or "").strip()
        self.consumer_secret = (consumer_secret or "").strip()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
        self._access_token: str | None = None

    def _ensure_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        if not self.consumer_id or not self.consumer_secret:
            raise BadRequestError("SSI FC consumer ID/secret are required")
        response = self.session.post(
            SSI_FC_ACCESS_TOKEN_API,
            json={
                "consumerID": self.consumer_id,
                "consumerSecret": self.consumer_secret,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("data") or payload.get("accessToken") or payload.get("token")
        if isinstance(token, dict):
            token = token.get("accessToken") or token.get("token")
        token = str(token or "").strip()
        if not token:
            raise BadRequestError("SSI FC access token response is invalid")
        self._access_token = token
        return token

    def fetch_foreign_snapshot(self, ticker: str, trading_date: date) -> dict | None:
        token = self._ensure_access_token()
        response = self.session.get(
            SSI_FC_DAILY_PRICE_API,
            params={
                "Symbol": ticker,
                "FromDate": trading_date.strftime(VN_DATE),
                "ToDate": trading_date.strftime(VN_DATE),
                "PageIndex": 1,
                "PageSize": 1,
                "Ascending": False,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if response.status_code == 401:
            self._access_token = None
            token = self._ensure_access_token()
            response = self.session.get(
                SSI_FC_DAILY_PRICE_API,
                params={
                    "Symbol": ticker,
                    "FromDate": trading_date.strftime(VN_DATE),
                    "ToDate": trading_date.strftime(VN_DATE),
                    "PageIndex": 1,
                    "PageSize": 1,
                    "Ascending": False,
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data") or []
        if not isinstance(rows, list) or not rows:
            return None
        row = rows[0]
        buy_vol = _int_value(row.get("ForeignBuyVolTotal") or row.get("foreignBuyVolTotal"))
        sell_vol = _int_value(row.get("ForeignSellVolTotal") or row.get("foreignSellVolTotal"))
        buy_val = _decimal(row.get("ForeignBuyValTotal") or row.get("foreignBuyValTotal"))
        sell_val = _decimal(row.get("ForeignSellValTotal") or row.get("foreignSellValTotal"))
        net_vol = _int_value(row.get("NetForeignVol") or row.get("netForeignVol") or row.get("netBuySellVol"))
        net_val = _decimal(row.get("NetForeignVal") or row.get("netForeignVal") or row.get("netBuySellVal"))
        return {
            "foreignBuyVolTotal": buy_vol,
            "foreignSellVolTotal": sell_vol,
            "foreignBuyValTotal": buy_val,
            "foreignSellValTotal": sell_val,
            "netForeignVol": net_vol if net_vol is not None else ((buy_vol or 0) - (sell_vol or 0)),
            "netForeignVal": net_val if net_val is not None else ((buy_val or Decimal("0")) - (sell_val or Decimal("0"))),
            "foreignDataSource": "ssi_fc",
            "rawPayload": row,
        }


def fetch_foreign_snapshots_bulk(
    consumer_id: str,
    consumer_secret: str,
    tickers: list[str],
    trading_date: date,
    max_workers: int = 8,
) -> dict[str, dict]:
    normalized = [str(ticker or "").strip().upper() for ticker in tickers if str(ticker or "").strip()]
    if not normalized:
        return {}
    results: dict[str, dict] = {}

    def work(ticker: str) -> tuple[str, dict | None]:
        client = SsiForeignClient(consumer_id, consumer_secret)
        return ticker, client.fetch_foreign_snapshot(ticker, trading_date)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(work, ticker): ticker for ticker in normalized}
        for future in as_completed(futures):
            ticker, payload = future.result()
            if payload is not None:
                results[ticker] = payload
    return results
