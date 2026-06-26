import httpx
from datetime import date
from typing import Any

from app.config import settings

CH_BASE = "https://api.company-information.service.gov.uk"


class CompaniesHouseClient:
    def __init__(self):
        self.api_key = settings.companies_house_api_key
        self._auth = httpx.BasicAuth(username=self.api_key, password="")

    async def search_officers(self, nationality: str = "Ghanaian", items_per_page: int = 100) -> list[dict[str, Any]]:
        results = []
        start_index = 0

        async with httpx.AsyncClient(auth=self._auth, timeout=30) as client:
            while True:
                resp = await client.get(
                    f"{CH_BASE}/search/officers",
                    params={
                        "q": nationality,
                        "items_per_page": min(items_per_page, 100),
                        "start_index": start_index,
                    },
                )
                if resp.status_code != 200:
                    break

                data = resp.json()
                items = data.get("items", [])
                results.extend(items)
                total = data.get("total_results", 0)

                start_index += items_per_page
                if start_index >= total or not items:
                    break

        return results

    async def get_officer_detail(self, officer_id: str) -> dict[str, Any] | None:
        async with httpx.AsyncClient(auth=self._auth, timeout=30) as client:
            resp = await client.get(f"{CH_BASE}/officers/{officer_id}")
            if resp.status_code == 200:
                return resp.json()
        return None

    async def get_company_profile(self, company_number: str) -> dict[str, Any] | None:
        async with httpx.AsyncClient(auth=self._auth, timeout=30) as client:
            resp = await client.get(f"{CH_BASE}/company/{company_number}")
            if resp.status_code == 200:
                return resp.json()
        return None

    @staticmethod
    def parse_officer(raw: dict[str, Any]) -> dict[str, Any]:
        address = raw.get("address", {}) or {}
        date_of_birth = raw.get("date_of_birth")
        dob = None
        if date_of_birth:
            try:
                dob = date(date_of_birth["year"], date_of_birth["month"], 1)
            except (KeyError, ValueError):
                dob = None

        return {
            "source": "companies_house",
            "source_id": str(raw.get("links", {}).get("officer", {}).get("id", raw.get("officer_id", ""))),
            "name": raw.get("name", ""),
            "role": raw.get("officer_role", "").replace("_", " ").title() if raw.get("officer_role") else None,
            "company_name": raw.get("appointed_to", {}).get("company_name") if isinstance(raw.get("appointed_to"), dict) else None,
            "company_number": raw.get("appointed_to", {}).get("company_number") if isinstance(raw.get("appointed_to"), dict) else None,
            "nationality": raw.get("nationality"),
            "date_of_birth": dob,
            "country_of_residence": raw.get("country_of_residence"),
            "address_line_1": address.get("address_line_1"),
            "address_line_2": address.get("address_line_2"),
            "locality": address.get("locality"),
            "region": address.get("region"),
            "postal_code": address.get("postal_code"),
            "country": address.get("country"),
            "occupation": raw.get("occupation"),
            "appointed_on": self._parse_date(raw.get("appointed_on")),
            "resigned_on": self._parse_date(raw.get("resigned_on")),
            "is_active": raw.get("resigned_on") is None,
            "origin": "gh",
        }

    @staticmethod
    def _parse_date(d: str | None) -> date | None:
        if not d:
            return None
        try:
            return date.fromisoformat(d)
        except (ValueError, TypeError):
            return None
