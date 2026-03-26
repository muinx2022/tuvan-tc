from __future__ import annotations

import requests

from common.exceptions import BadRequestError

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)


class VietstockClient:
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def load_session_page(self, ticker: str) -> requests.Response:
        page_url = f"https://finance.vietstock.vn/{ticker}/tai-chinh.htm?tab=CHART"
        response = self.session.get(
            page_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            timeout=60,
        )
        response.raise_for_status()
        return response

    def build_cookie_header(self, response: requests.Response) -> str:
        if not response.cookies:
            raise BadRequestError("Unable to establish Vietstock session")
        return "; ".join(f"{key}={value}" for key, value in response.cookies.items())

    def fetch_chart_payload(self, ticker: str, token: str, cookie_header: str) -> dict:
        body = "&".join(
            [
                "stockCode=" + requests.utils.quote(ticker, safe=""),
                "chartPageId=0",
                "__RequestVerificationToken=" + requests.utils.quote(token, safe=""),
                "isCatch=true",
                "languageId=1",
            ]
        )
        response = self.session.post(
            "https://finance.vietstock.vn/FinanceChartPage/GetListChart_Page_Mapping_ByStockCode_Full",
            data=body,
            headers={
                "User-Agent": USER_AGENT,
                "Referer": f"https://finance.vietstock.vn/{ticker}/tai-chinh.htm?tab=CHART",
                "Origin": "https://finance.vietstock.vn",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Accept": "*/*",
                "Cookie": cookie_header,
            },
            timeout=120,
        )
        response.raise_for_status()
        try:
            return response.json()
        except Exception as exc:
            raise BadRequestError(f"Unable to parse Vietstock chart response for ticker {ticker}") from exc
