import httpx
from datetime import date
from typing import Any

from app.config import settings

OC_BASE = "https://api.opencorporates.com/v0.8"

AFRICAN_COUNTRIES = [
    "Ghana", "Nigeria", "Ethiopia", "Kenya", "Tanzania", "Uganda",
    "Senegal", "Ivory Coast", "Cote d'Ivoire", "Cameroon", "Angola",
    "Mozambique", "Zambia", "Somalia", "Liberia", "Sierra Leone",
    "Congo", "DRC", "Rwanda", "Burundi", "Eritrea", "Djibouti",
    "Benin", "Togo", "Mali", "Burkina Faso", "Niger", "Chad",
    "Sudan", "South Sudan", "Malawi", "Zimbabwe", "Botswana",
    "Namibia", "Lesotho", "Eswatini", "Gambia", "Guinea",
    "Guinea-Bissau", "Mauritania", "Cape Verde", "Comoros",
    "Mauritius", "Seychelles", "Sao Tome",
]

DIASPORA_SURNAMES_PREFIXES = [
    "Afri", "Ama", "Ban", "Boa", "Diop", "Eke", "Esi", "Fof",
    "Kam", "Kei", "Kofi", "Kwa", "Mba", "Mbi", "Mbo", "Ndi",
    "Nko", "Nwa", "Oka", "Oke", "Oko", "Ola", "Oli", "Olu",
    "Omo", "Ony", "Osu", "Oti", "Owu", "Uba", "Uche", "Udo",
    "Uka", "Ume", "Uwa",
]

JURISDICTIONS = ["US_MD", "US_TX"]

ORIGIN_MAP = {
    "ghana": "gh", "ghanaian": "gh",
    "nigeria": "ng", "nigerian": "ng",
    "ethiopia": "et", "ethiopian": "et",
    "kenya": "ke", "kenyan": "ke",
    "tanzania": "tz", "tanzanian": "tz",
    "uganda": "ug", "ugandan": "ug",
    "senegal": "sn", "senegalese": "sn",
    "cameroon": "cm", "cameroonian": "cm",
    "angola": "ao", "angolan": "ao",
    "mozambique": "mz", "mozambican": "mz",
    "zambia": "zm", "zambian": "zm",
    "liberia": "lr", "liberian": "lr",
    "sierra leone": "sl", "sierra leonean": "sl",
    "rwanda": "rw", "rwandan": "rw",
    "somalia": "so", "somali": "so",
    "congo": "cg",
    "benin": "bj", "beninese": "bj",
    "togo": "tg", "togolese": "tg",
    "mali": "ml", "malian": "ml",
    "burkina faso": "bf",
    "niger": "ne", "nigerien": "ne",
    "chad": "td", "chadian": "td",
    "sudan": "sd", "sudanese": "sd",
    "zimbabwe": "zw", "zimbabwean": "zw",
    "malawi": "mw", "malawian": "mw",
    "botswana": "bw", "botswanan": "bw",
    "namibia": "na", "namibian": "na",
    "gambia": "gm", "gambian": "gm",
    "mauritius": "mu",
    "seychelles": "sc",
    "cape verde": "cv",
    "djibouti": "dj",
    "eritrea": "er",
    "mauritania": "mr",
    "guinea": "gn", "guinean": "gn",
}


class OpenCorporatesClient:
    def __init__(self):
        self.api_token = settings.opencorporates_api_key

    @property
    def available(self) -> bool:
        return bool(self.api_token)

    async def search_companies(
        self,
        jurisdiction: str,
        query: str = "",
        per_page: int = 30,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        if not self.available:
            return []
        params: dict[str, Any] = {
            "api_token": self.api_token,
            "per_page": min(per_page, 100),
            "page": page,
        }
        if query:
            params["q"] = query

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{OC_BASE}/companies/search",
                params={**params, "jurisdiction_code": jurisdiction},
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            return data.get("results", {}).get("companies", [])

    async def search_all_pages(
        self,
        jurisdiction: str,
        query: str = "",
        max_pages: int = 5,
    ) -> list[dict[str, Any]]:
        all_companies: list[dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            batch = await self.search_companies(
                jurisdiction=jurisdiction, query=query, page=page
            )
            if not batch:
                break
            all_companies.extend(batch)
        return all_companies

    async def get_officers(
        self, jurisdiction: str, company_number: str
    ) -> list[dict[str, Any]]:
        if not self.available:
            return []
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{OC_BASE}/companies/{jurisdiction}/{company_number}/officers",
                params={"api_token": self.api_token},
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            return data.get("results", {}).get("officers", [])

    async def search_diaspora_companies(
        self, jurisdiction: str, max_pages: int = 5
    ) -> list[dict[str, Any]]:
        seen: set[str] = set()
        all_companies: list[dict[str, Any]] = []

        for country in AFRICAN_COUNTRIES:
            batch = await self.search_all_pages(
                jurisdiction=jurisdiction, query=country, max_pages=2
            )
            for item in batch:
                c = item.get("company", {})
                cid = c.get("company_number", "")
                if cid and cid not in seen:
                    seen.add(cid)
                    all_companies.append(item)

        return all_companies

    @staticmethod
    def parse_company(raw: dict[str, Any]) -> dict[str, Any] | None:
        c = raw.get("company", {})
        if not c:
            return None
        company_number = c.get("company_number", "")
        if not company_number:
            return None

        address = c.get("registered_address", {}) or {}
        jurisdiction = c.get("jurisdiction_code", "")
        name = c.get("name", "")

        tags = []
        for country in AFRICAN_COUNTRIES:
            if country.lower() in name.lower():
                tags.append(country.lower())
                break

        return {
            "source": "opencorporates",
            "source_id": f"{jurisdiction}/{company_number}",
            "name": name,
            "company_number": company_number,
            "status": c.get("company_status"),
            "company_type": c.get("company_type"),
            "sic_codes": c.get("industry_codes", []),
            "registered_address": ", ".join(filter(None, [
                address.get("address_line_1"),
                address.get("address_line_2"),
                address.get("city"),
                address.get("state"),
                address.get("postal_code"),
                address.get("country"),
            ])),
            "locality": address.get("city"),
            "region": address.get("state"),
            "country": address.get("country"),
            "postal_code": address.get("postal_code"),
            "incorporation_date": c.get("incorporation_date"),
            "jurisdiction": jurisdiction,
            "tags": tags,
            "origin": None,
        }

    @staticmethod
    def parse_officer(raw: dict[str, Any], jurisdiction: str, company_name: str) -> dict[str, Any] | None:
        o = raw.get("officer", {})
        if not o:
            return None

        name = o.get("name", "")
        if not name:
            return None

        occupation = o.get("occupation") or o.get("position")
        nationality = o.get("nationality")

        date_of_birth = None
        if o.get("date_of_birth"):
            try:
                dob = o["date_of_birth"]
                if "/" in str(dob):
                    parts = str(dob).split("/")
                    date_of_birth = date(int(parts[2]), int(parts[0]), 1)
                else:
                    date_of_birth = date.fromisoformat(str(dob))
            except (ValueError, KeyError, IndexError):
                date_of_birth = None

        origin = None
        if nationality:
            nl = nationality.lower()
            for key, code in ORIGIN_MAP.items():
                if key in nl:
                    origin = code
                    break

        tags = []
        for country in AFRICAN_COUNTRIES:
            if country.lower() in name.lower():
                tags.append(country.lower())
                break

        return {
            "source": "opencorporates",
            "source_id": f"{jurisdiction}/{o.get('uid', '')}",
            "name": name,
            "role": occupation,
            "company_name": company_name,
            "company_number": None,
            "nationality": nationality,
            "date_of_birth": date_of_birth,
            "country_of_residence": o.get("country_of_residence"),
            "address_line_1": None,
            "address_line_2": None,
            "locality": None,
            "region": None,
            "postal_code": None,
            "country": None,
            "occupation": occupation,
            "is_active": True,
            "tags": tags,
            "origin": origin,
        }
