"""Explore which Ghanaian photo concepts actually pass the feature-image gates.

For each candidate query, report how many results survive every gate and the
titles that pass, so failing themes can be re-pointed at concepts Commons
genuinely has landscape, high-res, freely-licensed photographs of -- rather
than loosening the filters into irrelevant art.
"""
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_feature_images as F  # noqa: E402

QUERIES = [
    # infrastructure / energy
    "Akosombo Dam", "Bui Dam Ghana", "Tema Oil Refinery", "Ghana electricity",
    "Ghana power", "Ghana solar panel", "Ghana water supply", "Ghana borehole",
    "Ghana telecommunications", "Ghana internet cafe",
    # documents -> life / people substitutes
    "Ghana independence day", "Ghana national day", "Ghanaian family",
    "Ghana school children uniform", "Ghana graduation ceremony",
    "Ghana voting election", "Ghana traditional council",
    # commerce / enterprise
    "Ghana market trader", "Ghana shop owner", "Ghana tailor",
    "Ghana hairdresser", "Ghana street vendor", "Ghana bakery",
    "Ghana taxi driver", "Ghana agrobusiness",
    # health
    "Ghana doctor", "Ghana nurse", "Ghana clinic patient",
    "Ghana pharmacy", "Ghana medicine",
    # money / legal
    "Ghana bank", "Ghana ATM", "Ghana mobile phone money",
    "Ghana courthouse", "Ghana lawyer", "Ghana traditional council meeting",
    # land / property / housing
    "Ghana apartment", "Ghana bungalow", "Ghana unfinished building",
    "Ghana real estate", "Ghana land", "Ghana cement",
    # diaspora
    "Ghanaian UK", "Ghana church London", "African diaspora London",
    "Ghana community centre",
]


def passing_titles(query, match=(), ghana_only=True, limit=30):
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
        if w < F.MIN_WIDTH or h < F.MIN_HEIGHT or w < h * 1.15:
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


for q in QUERIES:
    try:
        t = passing_titles(q)
    except Exception as exc:
        print(f"[err] {q}: {exc}")
        continue
    flag = "OK " if t else "-- "
    print(f"{flag}{q:34} {len(t):2}  {t[0][:70] if t else ''}")