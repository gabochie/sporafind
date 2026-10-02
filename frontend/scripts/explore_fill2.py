"""Round 2: short queries work far better on Commons than long ones."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_feature_images as F  # noqa: E402

CANDIDATES = [
    ("flood", "Ghana flood", ("flood", "water", "river", "drain")),
    ("flood", "Accra drainage", ("drain", "water", "accra", "canal")),
    ("flood", "Ghana lagoon", ("lagoon", "water", "wetland", "ghana")),
    ("remote", "Ghana internet", ("internet", "computer", "online", "network", "cyber")),
    ("remote", "Ghana computer", ("computer", "laptop", "screen", "digital")),
    ("artisan", "Ghana weaver", ("weav", "kente", "cloth", "textile", "loom")),
    ("artisan", "Ghana carpenter", ("carpenter", "wood", "joinery", "timber")),
    ("artisan", "Ghana shoemaker", ("shoe", "cobbler", "leather", "repair")),
    ("factory", "Ghana factory", ("factory", "industrial", "manufactur", "plant", "industry")),
    ("factory", "Ghana port workers", ("port", "worker", "container", "cargo", "dock")),
    ("court", "Ghana court", ("court", "judge", "legal", "tribunal", "law")),
    ("court", "Ghana police", ("police", "officer", "law", "crime", "gendarme")),
    ("survey", "Ghana surveyor", ("survey", "surveyor", "gps", "land", "cadastre")),
    ("land", "Ghana land dispute", ("land", "dispute", "chief", "stool", "boundary")),
    ("stool", "Ghana chief", ("chief", "stool", "chiefcy", "traditional", "regent")),
    ("office", "Ghana office", ("office", "desk", "building", "ministry", "department")),
    ("register", "Ghana business licence", ("licence", "license", "business", "permit", "registration")),
    ("tax", "Ghana tax revenue", ("tax", "revenue", "gra", "customs", "levy")),
    ("money", "Ghana cash currency", ("cash", "currency", "cedi", "money", "notes")),
    ("market2", "Ghana women market", ("market", "women", "trader", "stall", "goods")),
    ("housing2", "Ghana neighbourhood houses", ("neighbourhood", "houses", "residential", "street", "compound")),
    ("housing3", "Ghana real estate agent", ("estate", "agent", "property", "realtor", "letting")),
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
    print(f"=== {key:10} ({len(t)}) q={q!r}")
    for title in t[:3]:
        print(f"           {title}")