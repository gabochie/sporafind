"""Diagnose why unresolved feature-image themes find no candidate.

Re-runs the Commons search for each unresolved theme and reports how many
results die at each gate (mime, resolution, landscape, licence, negative,
on-topic match, Ghana provenance). Use it to decide per theme whether to
loosen a gate, change the query, or accept the gap.
"""
import json
import sys
import urllib.parse

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import fetch_feature_images as F  # noqa: E402

MANIFEST = json.loads(F.MANIFEST.read_text(encoding="utf-8"))
THEMES = {}
for spec in F.THEMES:
    THEMES[spec["key"]] = spec


def gates(spec, limit=25):
    data = F.api({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": spec["query"], "gsrnamespace": "6", "gsrlimit": str(limit),
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "1920",
    })
    pages = (data.get("query") or {}).get("pages") or {}
    counts = dict(total=len(pages), mime=0, size=0, land=0, lic=0,
                  neg=0, match=0, ghana=0, ok=0)
    for p in pages.values():
        info = (p.get("imageinfo") or [{}])[0]
        if info.get("mime", "") not in ("image/jpeg", "image/png"):
            counts["mime"] += 1
            continue
        w, h = info.get("width") or 0, info.get("height") or 0
        if w < F.MIN_WIDTH or h < F.MIN_HEIGHT:
            counts["size"] += 1
            continue
        if w < h * 1.15:
            counts["land"] += 1
            continue
        meta = info.get("extmetadata") or {}
        short = F.strip_html((meta.get("LicenseShortName") or {}).get("value"))
        code = F.strip_html((meta.get("License") or {}).get("value"))
        if not F.acceptable(short, code):
            counts["lic"] += 1
            continue
        title = p.get("title", "")
        desc = F.strip_html((meta.get("ImageDescription") or {}).get("value"))
        subject = F.strip_html((meta.get("ObjectName") or {}).get("value"))
        if F.is_negative(title, desc):
            counts["neg"] += 1
            continue
        blob = " ".join([title, desc, subject]).lower()
        if spec["match"] and not any(m in blob for m in spec["match"]):
            counts["match"] += 1
            continue
        if spec["ghana_only"] and not F.has_ghana_marker(title, desc, subject):
            counts["ghana"] += 1
            continue
        counts["ok"] += 1
    return counts


unresolved = MANIFEST.get("unresolved", [])
for key in unresolved:
    spec = THEMES.get(key)
    if not spec:
        print(f"{key:22} NO SPEC")
        continue
    try:
        c = gates(spec)
    except Exception as exc:
        print(f"{key:22} query-error: {exc}")
        continue
    died = {k: v for k, v in c.items() if k not in ("total", "ok") and v > 0}
    print(f"{key:22} ok={c['ok']:<2} of {c['total']:<3} lost={died}  q={spec['query']!r}")