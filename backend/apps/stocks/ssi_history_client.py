from __future__ import annotations

from datetime import date

import requests

SSI_HISTORY_API = "https://iboard-api.ssi.com.vn/statistics/company/ssmi/stock-info"
VN_DATE = "%d/%m/%Y"


class SsiHistoryClient:
    def fetch_histories(self, ticker: str, from_date: date, page_size: int, page: int = 1) -> dict:
        url = (
            f"{SSI_HISTORY_API}?symbol={ticker}&page={page}&pageSize={page_size}"
            f"&fromDate={from_date.strftime(VN_DATE)}&toDate={date.today().strftime(VN_DATE)}"
        )
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        response.raise_for_status()
        return response.json()
