from __future__ import annotations

import requests

from common.exceptions import BadRequestError

VPS_COMPANY_API = "https://histdatafeed.vps.com.vn/company/basic"


class VpsClient:
    def fetch_company_basic(self) -> dict:
        response = requests.get(VPS_COMPANY_API, timeout=120)
        response.raise_for_status()
        try:
            return response.json()
        except Exception as exc:
            raise BadRequestError("VPS response is invalid") from exc
