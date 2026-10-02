"""Find *additional distinct* Ghanaian photo concepts.

Two jobs:
  1. fill the 10 posts that still have no feature photo (land fraud/title/POA,
     flood zones, fintech licence, fibre)
  2. give posts that currently share a theme their own image, so the archive
     stops repeating photos.

Same gates as the real pipeline. Survivors are printed for title inspection.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_feature_images as F  # noqa: E402

CANDIDATES = [
    # --- land / property / fraud (7 missing posts) ---
    ("land", "Ghana farmland field", ("farmland", "field", "farm", "land", "agricultur")),
    ("land", "Ghana agricultural land crops", ("agricultur", "crop", "farm", "field", "land")),
    ("stool", "Ghana chief traditional stool", ("chief", "stool", "traditional", "chiefcy")),
    ("land", "Ghana property house for sale", ("property", "house", "sale", "land", "estate")),
    ("survey", "Ghana survey land measurement", ("survey", "measurement", "land", "measur")),
    # --- flood zones ---
    ("flood", "Accra flooding drainage water", ("flood", "drainage", "water", "accra")),
    ("flood", "Ghana flood river basin", ("flood", "river", "water", "basin")),
    ("flood", "Korle Lagoon Accra", ("korle", "lagoon", "accra", "water")),
    # --- fintech licence ---
    ("fintech", "Ghana bank building Accra", ("bank", "accra", "ghana")),
    ("fintech", "Ghana forex bureau money", ("forex", "bureau", "money", "exchange")),
    ("fintech", "Ghana ATM machine bank", ("atm", "machine", "bank", "cash")),
    # --- fibre / remote work ---
    ("remote", "Ghana office workers computer", ("office", "computer", "worker", "desk")),
    ("remote", "Ghana call centre office", ("call centre", "call center", "office", "desk")),
    ("remote", "Ghana university computer lab", ("computer", "lab", "university", "student")),
    # --- enterprise dupes (need 4 distinct) ---
    ("artisan", "Ghana carpenter wood workshop", ("carpenter", "wood", "workshop", "craft")),
    ("artisan", "Ghana weaver textile kente", ("weaver", "textile", "kente", "cloth", "weaving")),
    ("market", "Ghana market women goods stall", ("market", "women", "goods", "stall", "trader")),
    ("office", "Ghana office paperwork desk", ("office", "paperwork", "desk", "document", "form")),
    ("factory", "Ghana factory industrial workers", ("factory", "industrial", "worker", "manufactur")),
    # --- housing dupes (need 2 more distinct) ---
    ("housing", "Accra residential neighbourhood street", ("residential", "neighbourhood", "street", "houses")),
    ("housing", "Ghana compound house courtyard", ("compound", "courtyard", "house", "compound")),
    # --- register dupes (need 2 more distinct) ---
    ("office", "Ghana government office building", ("government", "office", "building", "ministry")),
    ("register", "Ghana shop front trader business", ("shop", "front", "trader", "business", "store")),
]


def passing(query, match, limit=30, ghana_only=True):
    data = F.api({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrnamespace": "6", "gsrlimit": str(limit),
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "1920",
    })
    pages = (data.get("query") or {}).get("pages") or {}
    out = []
    for p in pages.values():
        info = (p.get("imageinfo") or [{}])[0]
        if info.get("mime", "") not in ("image/jpeg", "image/png"):
            continue
        w, h = info.get("width") or 0, info.get("height") or 0
        if w < F.MIN_WIDTH or h < F.MIN_HEIGHT or not (1.15 <= w / h <= F.MAX_ASPECT):
            continue
        meta = info.get("extmetadata") or {}
        short = F.strip_html((meta.get("LicenseShortName") or {}).get("value"))
        code = F.strip_html((meta.get("License") or {}).get("value"))
        if not F.acceptable(short, code):
            continue
        title = p.get("title", "")
        desc = F.strip_html((meta.get("ImageDescription") or {}).get("value"))
        subject = F.strip_html((meta.get("ObjectName") or {}).get("value"))
        if F.is_negative(title, desc):
            continue
        blob = " ".join([title, desc, subject]).lower()
        if match and not any(m in blob for m in match):
            continue
        if ghana_only and not F.has_ghana_marker(title, desc, subject):
            continue
        out.append(title)
    return out


for key, q, match in CANDIDATES:
    try:
        t = passing(q, match)
    except Exception as exc:
        print(f"[err] {key}: {exc}")
        continue
    print(f"=== {key:9} ({len(t)}) q={q!r}")
    for title in t[:3]:
        print(f"        {title}")
