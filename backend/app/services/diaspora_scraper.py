import re
from typing import Any
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup

from app.services.opencorporates import AFRICAN_COUNTRIES

# Known African diaspora directories/organizations by state
DIRECTORY_SOURCES: list[dict[str, Any]] = [
    {
        "id": "usafrican-chamber-members",
        "name": "US African Chamber of Commerce — Member Directory",
        "url": "https://www.usafricanchamber.org/members",
        "type": "chamber",
        "parser": "usafrican_chamber",
    },
    {
        "id": "md-african-community",
        "name": "Maryland African Community Organizations",
        "url": "https://www.africancommunities.org/maryland",
        "type": "community",
        "parser": "generic_org_list",
    },
    {
        "id": "tx-african-community",
        "name": "Texas African Community Organizations",
        "url": "https://www.africancommunities.org/texas",
        "type": "community",
        "parser": "generic_org_list",
    },
    {
        "id": "african-diaspora-directory",
        "name": "African Diaspora Business Directory",
        "url": "https://www.africandiasporadirectory.com/businesses",
        "type": "business",
        "parser": "generic_org_list",
    },
]

ORGS_TARGETED = [
    {
        "name": "African Diaspora Association of Maryland",
        "locality": "Baltimore",
        "region": "MD",
        "country": "United States",
        "org_type": "association",
        "tags": ["diaspora", "community"],
        "origin": None,
    },
    {
        "name": "Texas African Diaspora Association",
        "locality": "Houston",
        "region": "TX",
        "country": "United States",
        "org_type": "association",
        "tags": ["diaspora", "community"],
        "origin": None,
    },
    {
        "name": "African Chamber of Commerce of Houston",
        "locality": "Houston",
        "region": "TX",
        "country": "United States",
        "org_type": "chamber",
        "tags": ["chamber", "business"],
        "origin": None,
    },
    {
        "name": "African Chamber of Commerce of Maryland",
        "locality": "Baltimore",
        "region": "MD",
        "country": "United States",
        "org_type": "chamber",
        "tags": ["chamber", "business"],
        "origin": None,
    },
    {
        "name": "Dallas African Diaspora Business Council",
        "locality": "Dallas",
        "region": "TX",
        "country": "United States",
        "org_type": "council",
        "tags": ["diaspora", "business"],
        "origin": None,
    },
    {
        "name": "African Diaspora Business Alliance — Washington DC Metro",
        "locality": "Silver Spring",
        "region": "MD",
        "country": "United States",
        "org_type": "alliance",
        "tags": ["diaspora", "business"],
        "origin": None,
    },
]


async def fetch_and_parse(url: str, parser: str) -> list[dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Sporafind/1.0"})
            if resp.status_code != 200:
                return []
            if parser == "usafrican_chamber":
                return _parse_usafrican_chamber(resp.text)
            return _parse_generic_org_list(resp.text, url)
    except Exception:
        return []


def _parse_usafrican_chamber(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    orgs: list[dict[str, Any]] = []
    for item in soup.select(".member-item, .directory-entry, tr, .card"):
        text = item.get_text(" ", strip=True)
        if not text or len(text) < 5:
            continue
        name_el = item.select_one("h3, h4, .name, .title, strong")
        name = name_el.get_text(strip=True) if name_el else text.split(",")[0].strip()
        if len(name) < 3:
            continue
        location = item.get("data-location", "") or item.get("data-region", "") or ""
        orgs.append({
            "name": name[:255],
            "locality": _extract_city(location, text),
            "region": _extract_region(location, text),
            "country": "United States",
            "org_type": "chamber",
            "tags": ["diaspora", "chamber"],
            "origin": None,
        })
    return orgs


def _parse_generic_org_list(html: str, url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    orgs: list[dict[str, Any]] = []
    for item in soup.select("li, tr, .entry, .item, .card, .listing"):
        text = item.get_text(" ", strip=True)
        if not text or len(text) < 10:
            continue
        name_el = item.select_one("h2, h3, h4, .title, .name, a")
        name = name_el.get_text(strip=True) if name_el else text.split("\n")[0].strip()
        if len(name) < 3:
            continue
        orgs.append({
            "name": name[:255],
            "locality": _extract_city("", text),
            "region": "",
            "country": "United States",
            "org_type": "organization",
            "tags": ["diaspora"],
            "origin": None,
        })
    return orgs


def _extract_city(location: str, text: str) -> str:
    if location:
        parts = location.split(",")
        return parts[0].strip()[:100]
    match = re.search(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*),\s*(MD|TX|Maryland|Texas)", text)
    if match:
        return match.group(1)[:100]
    return ""


def _extract_region(location: str, text: str) -> str:
    if location:
        parts = location.split(",")
        if len(parts) > 1:
            return parts[-1].strip()[:100]
    match = re.search(r",\s*(MD|TX|Maryland|Texas)", text)
    if match:
        raw = match.group(1)
        if raw == "Maryland":
            return "MD"
        if raw == "Texas":
            return "TX"
        return raw
    return ""
