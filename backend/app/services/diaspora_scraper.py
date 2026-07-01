import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.services.opencorporates import AFRICAN_COUNTRIES

logger = logging.getLogger(__name__)

DIRECTORY_SOURCES: list[dict[str, Any]] = [
    {
        "id": "acct-members",
        "name": "African Chamber of Commerce of Texas — Member Directory",
        "url": "https://acctx.us/members",
        "type": "chamber",
        "parser": "acct_members",
    },
    {
        "id": "md-bcc-directory",
        "name": "Maryland Black Chamber of Commerce — Member Directory",
        "url": "https://marylandbcc.org/member-directory/",
        "type": "chamber",
        "parser": "md_bcc_directory",
    },
]

ORGS_TARGETED = [
    {
        "name": "Maryland African Chamber of Commerce (MACC)",
        "locality": "Bowie",
        "region": "MD",
        "country": "United States",
        "org_type": "chamber",
        "tags": ["chamber", "business", "diaspora"],
        "origin": None,
    },
    {
        "name": "African Chamber of Commerce of Texas (ACCT)",
        "locality": "Austin",
        "region": "TX",
        "country": "United States",
        "org_type": "chamber",
        "tags": ["chamber", "business", "diaspora"],
        "origin": None,
    },
    {
        "name": "Texas Africa Chamber of Commerce (TXACC)",
        "locality": "Houston",
        "region": "TX",
        "country": "United States",
        "org_type": "chamber",
        "tags": ["chamber", "business", "diaspora"],
        "origin": None,
    },
    {
        "name": "Nigerian American Chamber of Commerce Texas (NACC)",
        "locality": "Houston",
        "region": "TX",
        "country": "United States",
        "org_type": "chamber",
        "tags": ["chamber", "business", "nigeria"],
        "origin": "ng",
    },
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
    {
        "name": "African Diaspora Association of the Greater Houston Area",
        "locality": "Houston",
        "region": "TX",
        "country": "United States",
        "org_type": "association",
        "tags": ["diaspora", "community"],
        "origin": None,
    },
    {
        "name": "Maryland African Diaspora Business Council",
        "locality": "Baltimore",
        "region": "MD",
        "country": "United States",
        "org_type": "council",
        "tags": ["diaspora", "business"],
        "origin": None,
    },
    {
        "name": "African Diaspora Chamber of Commerce Maryland",
        "locality": "Silver Spring",
        "region": "MD",
        "country": "United States",
        "org_type": "chamber",
        "tags": ["diaspora", "chamber"],
        "origin": None,
    },
    {
        "name": "African Diaspora Chamber of Commerce Texas",
        "locality": "Austin",
        "region": "TX",
        "country": "United States",
        "org_type": "chamber",
        "tags": ["diaspora", "chamber"],
        "origin": None,
    },
    {
        "name": "Ghanaian Diaspora Association of Maryland",
        "locality": "Silver Spring",
        "region": "MD",
        "country": "United States",
        "org_type": "association",
        "tags": ["diaspora", "community", "ghana"],
        "origin": "gh",
    },
    {
        "name": "Nigerian Diaspora Association of Texas",
        "locality": "Houston",
        "region": "TX",
        "country": "United States",
        "org_type": "association",
        "tags": ["diaspora", "community", "nigeria"],
        "origin": "ng",
    },
    {
        "name": "Ethiopian Diaspora Association of Texas",
        "locality": "Dallas",
        "region": "TX",
        "country": "United States",
        "org_type": "association",
        "tags": ["diaspora", "community", "ethiopia"],
        "origin": "et",
    },
]


async def fetch_and_parse(url: str, parser: str) -> list[dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Sporafind/1.0"})
            if resp.status_code != 200:
                logger.warning("Scraper got HTTP %d from %s", resp.status_code, url)
                return []
            if parser == "acct_members":
                return _parse_acct_members(resp.text)
            if parser == "md_bcc_directory":
                return _parse_md_bcc_directory(resp.text)
            logger.warning("Unknown parser '%s' for %s", parser, url)
            return []
    except httpx.RequestError as e:
        logger.error("Request failed for %s: %s", url, e)
        return []
    except Exception as e:
        logger.error("Parse error for %s: %s", url, e, exc_info=True)
        return []


def _parse_acct_members(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    orgs: list[dict[str, Any]] = []
    page_text = soup.get_text(" ", strip=True)

    business_section = page_text.split("Business Listing:")[-1].split("Gallery")[0] if "Business Listing:" in page_text else page_text
    for line in business_section.split("\n"):
        line = line.strip()
        if not line or len(line) < 3:
            continue
        if any(skip in line.lower() for skip in ["chase bank", "ironstone", "state farm", "hampton inn", "marriott",
                                                   "compass bank", "postnet", "hogg foundation", "national american",
                                                   "twin towers", "austin cdc", "hd tv", "royal muffler",
                                                   "4 ni technologies", "trace auto", "rapid repair"]):
            continue
        orgs.append({
            "name": line[:255],
            "locality": "",
            "region": "TX",
            "country": "United States",
            "org_type": "chamber_member",
            "tags": ["diaspora", "business"],
            "origin": None,
        })
    return orgs


def _parse_md_bcc_directory(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    orgs: list[dict[str, Any]] = []

    for card in soup.select(".member-item, .member-card, .listing-item, li, .w-dyn-item"):
        name_el = card.select_one("h3, h4, .title, .name, a, strong")
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        if len(name) < 3:
            continue

        text = card.get_text(" ", strip=True)
        industry = ""
        for el in card.select(".industry, .category, .tag, .badge"):
            industry = el.get_text(strip=True)
            break

        orgs.append({
            "name": name[:255],
            "locality": _extract_city("", text),
            "region": "MD",
            "country": "United States",
            "org_type": industry[:50] if industry else "chamber_member",
            "tags": ["diaspora", "business"],
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
