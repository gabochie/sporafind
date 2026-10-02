"""Curate + download licensed feature photos for blog posts from Wikimedia Commons.

Why Commons and not Unsplash/Pexels: those APIs need keys or block this host
(401/403). Commons exposes machine-readable licence + author metadata, which is
exactly what a legally-defensible free-image pipeline needs.

Design notes
------------
* We fetch a small set of *themed* photographs (a Ghana city skyline, a tro-tro,
  a land deed...) and map them onto posts semantically. Hand-picking 60 unrelated
  search results per slug produces irrelevant art; a curated theme set keeps the
  archive visually coherent.
* Licence allowlist is recorded per file in data/feature-images.json together
  with author, licence name, licence URL and the Commons file page, so every
  card and article can render an attribution line.
* Output is committed. Re-running is a no-op unless --force is passed, so the
  build stays offline and deterministic once the assets exist.

Usage:
    python scripts/fetch_feature_images.py           # fetch missing only
    python scripts/fetch_feature_images.py --force   # re-fetch everything
    python scripts/fetch_feature_images.py --report  # print the manifest
"""

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "img" / "blog"
MANIFEST = ROOT / "data" / "feature-images.json"

UA = "sporafind-feature-image-fetch/1.0 (editorial@sporafind.com)"
API = "https://commons.wikimedia.org/w/api.php"
# This host runs behind a TLS-intercepting proxy whose CA store is not
# installed; verify=1 fails on the proxy cert. Images are re-encoded and
# re-validated locally before use, and Commons is not a security boundary.
SSL_CTX = ssl._create_unverified_context()

# Licences we accept. "noindex" style restrictions are rejected outright.
LICENCE_ALLOW = {
    "cc0", "cc-zero", "public domain", "pd", "pd-self", "no restrictions",
    "cc by", "cc by 2.0", "cc by 2.5", "cc by 3.0", "cc by 4.0",
    "cc by-sa", "cc by-sa 2.0", "cc by-sa 2.5", "cc by-sa 3.0", "cc by-sa 4.0",
}
LICENCE_BLOCK = {"nc", "nd", "fair use", "non-free", "copyright"}

MIN_WIDTH = 1400
MIN_HEIGHT = 800
# Cap the aspect ratio too. The gate above reads the *original* dimensions but
# downloads a 1920px-wide thumbnail, so an original of e.g. 4027x1364 passes the
# height test and then downloads as a 1920x650 strip that crops badly in a card.
MAX_ASPECT = 2.2

# Ghana markers. A theme flagged ghana_only=True is rejected unless the file's
# own title or description names Ghana/Accra (or a major Ghanaian city). Without
# this gate a search for "Accra tro-tro" happily returns a Luxembourg aircraft.
GHANA_MARKERS = (
    "ghana", "ghanaian", "accra", "kumasi", "tema", "tarkwa", "cape coast",
    "takoradi", "ho", "sunyani", "koforidua", "bolgatanga", "wa", "tamale",
    "korle bu", "kotoka", "kaneshie", "osu", "labadi", "east legon",
    "westuff", "wollerton", "spintex", " Tema", "harmattan",
)
# Words that mean "this is not reportage of the thing I asked for".
NEGATIVE = (
    "logo", "coat of arms", "stamp", "poster", "banner", "screenshot",
    "diagram", "chart", "graph", "icon", "seal", "carta ", "map of",
    "locator", "flag of", "plaque", "sign", "book cover", "painting",
    "illustration", "drawing", "engraving", "lithograph", "cartoon",
    "micrograph", "x-ray", "radiograph", "specimen", "fossil",
    "kitty", "kitties", "aeroplane", "aircraft", "airliner", "jet ",
    "steam", "1900", "1910", "1920", "1930", "1940",
)


def has_ghana_marker(*texts):
    blob = " ".join(t for t in texts if t).lower()
    return any(m in blob for m in GHANA_MARKERS)


def is_negative(*texts):
    blob = " ".join(t for t in texts if t).lower()
    return any(n in blob for n in NEGATIVE)


# theme key -> spec dict:
#   query      Commons search string
#   alt        alt text we will publish (must describe what the photo shows)
#   match      all-of tokens; the file must mention these to be on-topic
#   ghana_only require a Ghana/Accra marker in title or description
#   posts      slugs that can use this theme
def T(key, query, alt, match=(), ghana_only=True, posts=(), pick=None):
    return {"key": key, "query": query, "alt": alt,
            "match": tuple(match), "ghana_only": ghana_only, "posts": tuple(posts),
            "pick": pick}


THEMES = [
    # ---------- city / cost of living ----------
    T("accra_skyline", "Accra skyline", "Accra's skyline and high-rise towers.",
      match=("skyline",), posts=("diaspora-gentrification-accra-honest-data",
                                 "ghana-cost-of-living-truth-diaspora-2026")),
    T("accra_street", "Accra street traffic", "Street and traffic in central Accra.",
      match=("street", "road", "junction", "traffic"),
      posts=("accra-budget-tiers-compared-2026", "ghanaian-diaspora-uk-2025")),
    T("accra_market", "Accra market traders", "Traders and goods at a busy Accra market.",
      match=("market",),
      posts=("import-vs-local-shopping-accra-xpats",
             "market-pricing-power-ghana-farmers-beat-middlemen")),
    T("trotro", "Accra minibus tro tro", "A minibus (tro-tro) in Accra street traffic.",
      match=("minibus", "tro-tro", "trotro", "bus"),
      posts=("accra-transport-costs-trotro-bolt-owning-car",)),
    T("ghana_cedi", "Ghana bank branch", "A bank branch in Ghana.",
      match=("bank", "currency", "cedi", "money", "atm"),
      posts=("ghana-cost-of-living-truth-diaspora-2026",
             "obroni-pricing-ghana-how-to-negotiate")),
    # ---------- housing / land ----------
    T("ghana_housing", "Accra residential houses", "Residential housing in Accra.",
      match=("house", "housing", "residential", "apartment", "home"),
      posts=("accra-rent-trap-diaspora-guide",
             "accra-agent-fees-renoviction-renters-defense")),
    T("ghana_construction", "Accra building construction site",
      "A building under construction in Accra.", match=("construction", "building"),
      posts=("monitoring-ghana-construction-from-abroad",
             "building-material-inflation-ghana-timing")),
    # No honest photo exists: Commons has no reportage of Ghanaian land
    # registry/title documents (searches return logos, maps and scans that die
    # the mime/size/landscape gates). These posts keep the designed cover.
    T("ghana_title_search", "Ghana lands commission title",
      "Land registry and title documents.", match=("title", "deed", "land", "certificate", "document"),
      posts=("lands-commission-title-search-ghana-walkthrough",
             "multiple-sale-land-fraud-ghana", "forged-land-documents-ghana-red-flags")),
    T("ghana_wetland", "Ghana wetland Ramsar", "A protected wetland landscape in Ghana.",
      match=("wetland", "ramsar", "reserve"),
      posts=("ramsar-wetland-land-ghana-demolition-risk",)),
    T("ghana_village", "Ghana village community", "A village settlement in Ghana.",
      match=("village", "community"),
      posts=("pan-african-village-asebu-lessons-diaspora",)),
    T("ghana_estate", "Ghana apartment", "A residential apartment building in Ghana.",
      match=("apartment", "estate", "bungalow", "housing", "residential"),
      # Not the top-ranked hit: that file's own title reads "a unit apartment for
      # an alleged former witch", which is unfit for a commercial property guide.
      pick="File:Apartment Modern.jpg",
      posts=("gated-communities-ghana-sanbra-guide",
             "off-plan-property-ghana-due-diligence-checklist",
             "ghana-rent-act-tenant-rights-2026")),
    # ---------- infrastructure / utilities ----------
    T("ghana_meter", "Ghana electricity meter ECG", "An electricity meter in Ghana.",
      match=("meter", "electricity", "ecg"),
      posts=("ecg-prepaid-meter-draining-fast-rights-fixes",
             "solar-inverter-setup-ghana-homes-costs")),
    T("ghana_solar", "Ghana solar panel", "A solar panel installation in Ghana.",
      match=("solar", "panel", "inverter"),
      posts=("solar-inverter-setup-ghana-homes-costs",)),
    T("ghana_water", "Ghana water supply", "A water supply point in Ghana.",
      match=("water", "borehole", "tank", "pump", "reservoir", "supply"),
      posts=("water-security-ghana-home-tanks-boreholes-costs",
             "dumsor-water-internet-ghana-infrastructure-playbook")),
    # Only fibre photos on Commons are Australian NBN crews (Wagga, NSW). They
    # pass every gate but are not Ghanaian, so this theme stays unresolved by
    # design rather than shipping a misleading image.
    T("ghana_fibre", "Ghana fibre optic network", "Fibre optic network cabling in Ghana.",
      match=("fibre", "fiber", "optic", "cable", "telecom", "internet"),
      posts=("internet-remote-workers-ghana-fibre-dual-sim-stack",
             "dumsor-water-internet-ghana-infrastructure-playbook")),
    T("ghana_port", "Tema port containers Ghana", "Container stacks at Tema port, Ghana.",
      match=("port", "container", "terminal", "harbour", "harbor"),
      posts=("shipping-to-ghana-container-costs-port-clearance",)),
    # ---------- health ----------
    T("ghana_hospital", "Accra hospital building", "A hospital in Accra.",
      match=("hospital", "clinic", "medical", "health"),
      posts=("best-private-hospitals-accra-2026-compared",
             "emergency-care-plan-ghana-ambulances-hospitals",
             "ghana-healthcare-schools-diaspora-families-guide")),
    T("ghana_malaria", "Ghana malaria mosquito net", "A treated mosquito net in Ghana.",
      match=("malaria", "mosquito", "net", "bed"),
      posts=("malaria-vaccinations-ghana-returnee-health-brief",)),
    T("ghana_medication", "Ghana pharmacy", "A pharmacy in Ghana.",
      match=("pharmacy", "medicine", "drug", "medication", "chemist", "pharmaceutical"),
      posts=("chronic-medication-ghana-availability-planning",)),
    T("ghana_school", "Ghana school classroom pupils", "Pupils in a Ghanaian classroom.",
      match=("school", "classroom", "pupil", "student", "teacher"),
      posts=("international-schools-accra-fees-admissions-2026",
             "ghana-healthcare-schools-diaspora-families-guide")),
    T("ghana_nhis", "Ghana doctor nurse hospital",
      "Ghanaian health workers treating a patient.",
      match=("doctor", "nurse", "hospital", "clinic", "medical", "health"),
      # The only photograph actually taken inside a Ghanaian hospital is a
      # 4027x1364 strip (rejected by MAX_ASPECT). These are a joint
      # US-Ghana medical training exercise, but they do show Ghanaian health
      # workers treating a patient, which is what the alt text claims.
      pick="File:American, Ghanaian medical professionals partner to treat patients, hone skills 170209-A-IO170-062.jpg",
      posts=("nhis-enrolment-diaspora-guide-eligibility-process",)),
    # ---------- documents / money / business ----------
    # Passport/visa documents themselves are not documented on Commons; the
    # airport arrival shot is honest reportage for a visa guide.
    T("ghana_passport", "Kotoka International Airport terminal",
      "Arrivals at Kotoka International Airport, Accra.",
      match=("airport", "kotoka", "terminal", "accra"),
      # "Accra Ghana 2.jpg" ranks first but is a generic city shot; pin the file
      # that actually shows the arrivals entrance the alt text describes.
      pick="File:Accra Intl Airport arrivals entrance.jpg",
      posts=("ghana-visa-guide-diaspora-types-fees-fast-track",)),
    T("ghana_bank", "Bank of Ghana building Accra", "A bank building in Accra.",
      match=("bank",),
      posts=("diaspora-mortgages-ghana-compared-2026",
             "build-vs-buy-ghana-diaspora-framework")),
    # Commons has no Ghanaian mobile-money/fintech reportage: agent and phone
    # searches return zero usable frames, and cash/money searches surface a euro
    # area map. Kept unresolved rather than mislabeling an unrelated photo.
    T("ghana_mobile_money", "Ghana mobile money payment", "A mobile money payment in Ghana.",
      match=("mobile money", "momo", "payment", "fintech", "cash"),
      posts=("fintech-licence-ghana-bank-of-ghana-requirements",)),
    T("ghana_register", "Ghana market trader", "A trader at a market in Ghana.",
      match=("trader", "market", "shop", "business"),
      posts=("how-to-register-business-ghana-orc-gipa-gra-walkthrough",
             "doing-business-ghana-diaspora-bureaucracy-guide")),
    T("ghana_farm", "Ghana farmer crops", "A farmer selling produce in Ghana.",
      match=("farmer", "farm", "crop", "agriculture", "harvest", "produce"),
      posts=("diaspora-farm-investment-9-rules-before-sending-money",)),
    T("ghana_materials", "Ghana cement",
      "Cement and building materials in Ghana.",
      match=("cement", "concrete", "brick", "timber", "scaffold", "aggregate"),
      posts=("building-material-inflation-ghana-timing",)),
    # ---------- community ----------
    T("ghana_church", "Ghana church congregation", "A congregation gathered in a Ghanaian church.",
      match=("church", "congregation", "cathedral", "mosque"),
      posts=("finding-community-ghana-returnees-churches-associations",)),
    T("ghana_greeting", "Ghana traditional dance festival",
      "A traditional dance celebration in Ghana.",
      match=("dance", "festival", "traditional", "cultural"),
      posts=("twi-ga-greetings-etiquette-returnees-starter",)),
    T("ghana_community", "Ghana community gathering", "People gathered at a community event in Ghana.",
      match=("community", "gathering", "event", "association", "meeting"),
      posts=("obroni-to-belonging-diaspora-integration-ghana",
             "fihankra-ghana-cautionary-tale-returnees")),
    T("ghana_airport", "Kotoka International Airport Accra terminal",
      "An arrivals hall at Ghana's airport.",
      match=("airport", "terminal", "kotoka", "aviation"),
      posts=("fihankra-ghana-cautionary-tale-returnees",)),
    # ---------- misc ----------
    T("ghana_diaspora_uk", "Ghanaian community London", "A Ghanaian community gathering in the UK.",
      match=("ghanaian", "london", "diaspora", "african"),
      ghana_only=False, posts=("ghanaian-diaspora-uk-2025",)),
    T("ghana_remittance", "money transfer remittance", "Sending money abroad.",
      match=("transfer", "remittance", "money", "bank", "cash"),
      ghana_only=False, posts=("family-fixer-fraud-ghana-protecting-diaspora-money",)),
    T("ghana_data", "data analytics dashboard", "A data dashboard on a screen.",
      match=("dashboard", "data", "analytics", "chart", "screen"),
      ghana_only=False, posts=("ai-powered-diaspora-segmentation",)),
    T("ghana_power_plant", "Akosombo Dam", "The Akosombo hydroelectric dam in Ghana.",
      match=("dam", "hydro", "reservoir", "power"),
      posts=("ecg-prepaid-meter-draining-fast-rights-fixes",)),
    # Commons has no photograph of a Ghanaian notary or power-of-attorney
    # document (only logos and scans). The Law Courts Complex is honest
    # reportage for the legal/POA/fraud guides.
    T("ghana_court", "Ghana court", "The Law Courts Complex in Accra.",
      match=("court", "judge", "judicial", "tribunal"),
      pick="File:Law Court Complex in Ghana.jpg",
      posts=("fake-power-of-attorney-ghana-land-scams",
             "consularized-power-of-attorney-ghana-diaspora",
             "ghana-land-fraud-survival-guide",
             "escrow-ghana-property-transactions-guide")),
    # Citizenship documents themselves are not on Commons; Independence Day is
    # honest reportage for the citizenship/right-of-abode guides.
    T("ghana_citizenship", "Ghana independence day",
      "Ghana's Independence Day celebration.",
      match=("independence", "celebration", "parade", "ceremony"),
      posts=("ghana-citizenship-right-of-abode-guide-2026",)),
    # "Ghana bakery" is contaminated: unrelated Hong Kong bakery photos pass
    # every gate because their captions merely mention Ghana. A real Ghanaian
    # small-business shop is the honest alternative.
    T("ghana_enterprise", "Elmina salon Ghana",
      "A hairdressing salon in Elmina, Ghana.",
      match=("salon", "hair", "barber", "shop"),
      posts=("facilitation-fees-ghana-business-unofficial-tax",)),
    # ---------- additional distinct concepts ----------
    # Added so posts sharing a theme stop sharing a photo, and so the
    # land/flood/fintech/fibre guides get imagery instead of a bare cover.
    T("ghana_police", "Ghana police", "A police station in Accra.",
      match=("police", "gendarme", "officer"),
      posts=("stool-land-concurrence-ghana-explained",
             "fake-power-of-attorney-ghana-land-scams")),
    T("ghana_chief", "Ghana chief", "A chief in traditional attire in Ghana.",
      match=("chief", "stool", "chiefcy", "traditional"),
      posts=("multiple-sale-land-fraud-ghana",
             "stool-land-concurrence-ghana-explained",
             "land-guards-ghana-law-protection-guide")),
    T("ghana_land_farm", "Ghana farmland field", "Farmland in Ghana.",
      match=("farmland", "farm", "field", "agricultur", "crop"),
      posts=("lands-commission-title-search-ghana-walkthrough",
             "can-foreigners-own-land-ghana-50-year-rule",
             "multiple-sale-land-fraud-ghana")),
    T("ghana_government_office", "Ghana government office building",
      "A government office in Accra.",
      match=("office", "ministry", "department", "authority", "gra"),
      pick="File:Kwabenya NHIA Office, Accra.jpg",
      posts=("forged-land-documents-ghana-red-flags",
             "gipc-requirements-foreigners-2026-gipa-update")),
    T("ghana_flood", "Ghana flood", "Flooding in Ghana.",
      match=("flood", "water", "inundation"),
      posts=("accra-flood-zones-where-not-to-buy",)),
    T("ghana_bank_of_ghana", "Ghana bank building Accra",
      "The Bank of Ghana head office in Accra.",
      match=("bank", "accra", "ghana"),
      pick="File:Bank of Ghana High Street.jpg",
      posts=("fintech-licence-ghana-bank-of-ghana-requirements",)),
    T("ghana_computer", "Ghana computer", "Computer equipment in Ghana.",
      match=("computer", "laptop", "hardware", "electronics", "technician"),
      pick="File:A Ghanaian Computer Hardware Technician.jpg",
      posts=("internet-remote-workers-ghana-fibre-dual-sim-stack",)),
    T("ghana_weaver", "Ghana weaver", "A kente weaver at work in Ghana.",
      match=("weav", "kente", "loom", "textile", "cloth"),
      posts=("managing-artisans-staff-ghana-diaspora-employers",)),
    T("ghana_shoemaker", "Ghana shoemaker", "A shoemaker working in Ghana.",
      match=("shoemaker", "cobbler", "leather", "shoe", "sole"),
      posts=("diaspora-entrepreneurship-ecosystem",)),
    T("ghana_market_women", "Ghana women market", "Women trading at a market in Ghana.",
      match=("market", "women", "trader", "stall", "goods"),
      posts=("diaspora-entrepreneurship-ecosystem",
             "gra-tax-foreign-businesses-ghana-assessment-disputes")),
    T("ghana_block_factory", "Ghana factory", "A block-making factory in Ghana.",
      match=("factory", "block", "industrial", "manufactur", "bricks"),
      pick="File:Block factory02.jpg",
      posts=("building-material-inflation-ghana-timing",)),
]


def api(params, tries=3):
    url = API + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=40) as r:
                return json.loads(r.read())
        except Exception as exc:  # network hiccup / 429
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Commons API failed for {url}: {last}")


def strip_html(s):
    s = s or ""
    out, depth, skip = [], 0, False
    i = 0
    while i < len(s):
        c = s[i]
        if c == "<":
            depth += 1
            if s[i:i + 4].lower() in ("<br ", "<br/"):
                out.append(" ")
            skip = True
        elif c == ">":
            depth = max(0, depth - 1)
            skip = False
        elif not skip and depth == 0:
            out.append(c)
        i += 1
    return "".join(out).strip()


def clean_licence(name):
    return (name or "").strip().lower()


def acceptable(short, code):
    short = clean_licence(short)
    code = clean_licence(code)
    blob = f"{short} {code}"
    if any(b in blob for b in LICENCE_BLOCK):
        return False
    return any(short.startswith(a) or a in blob for a in LICENCE_ALLOW)


def search_candidates(spec, limit=25):
    query = spec["query"]
    data = api({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrnamespace": "6", "gsrlimit": str(limit),
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "1920",
    })
    pages = (data.get("query") or {}).get("pages") or {}
    out = []
    for p in pages.values():
        info = (p.get("imageinfo") or [{}])[0]
        mime = info.get("mime", "")
        if mime not in ("image/jpeg", "image/png"):
            continue
        w, h = info.get("width") or 0, info.get("height") or 0
        if w < MIN_WIDTH or h < MIN_HEIGHT:
            continue
        # Landscape only: these render as wide card/hero images.
        if w < h * 1.15 or w > h * MAX_ASPECT:
            continue
        title = p.get("title", "")
        meta = info.get("extmetadata") or {}
        short = strip_html((meta.get("LicenseShortName") or {}).get("value"))
        code = strip_html((meta.get("License") or {}).get("value"))
        if not acceptable(short, code):
            continue
        author = strip_html((meta.get("Artist") or {}).get("value"))
        lic_url = strip_html((meta.get("LicenseUrl") or {}).get("value"))
        desc = strip_html((meta.get("ImageDescription") or {}).get("value"))
        subject = strip_html((meta.get("ObjectName") or {}).get("value"))
        blob = " ".join([title, desc, subject]).lower()

        if is_negative(title, desc):
            continue
        # On-topic gate: the file must actually be about the theme.
        if spec["match"] and not any(m in blob for m in spec["match"]):
            continue
        # Provenance gate: a Ghanaian topic needs a Ghanaian photo.
        if spec["ghana_only"] and not has_ghana_marker(title, desc, subject):
            continue
        thumb = info.get("thumburl") or info.get("url")
        if not thumb:
            continue
        out.append({
            "title": title,
            "file_page": f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
            "download": thumb,
            "author": author or "Unknown",
            "licence": short or code or "see file page",
            "licence_url": lic_url,
            "description": (desc or subject)[:200],
            "width": w,
            "height": h,
        })
    return out


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, context=SSL_CTX, timeout=60) as r:
        data = r.read()
    if len(data) < 20000:
        raise RuntimeError(f"suspiciously small download ({len(data)} bytes)")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return len(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    if args.report:
        if not MANIFEST.exists():
            print("no manifest yet")
            return
        m = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for k, v in sorted(m.get("themes", {}).items()):
            print(f"{k:22} {v['licence']:14} {v['title'][:52]}")
            print(f"{'':22} {v['author'][:60]}")
        print(f"\nthemes={len(m.get('themes', {}))} mapped_posts={len(m.get('post_images', {}))}")
        missing = sorted({p["slug"] for p in json.loads((ROOT / "data" / "posts.json").read_text(encoding="utf-8"))
                          if p.get("status") == "published"} - set(m.get("post_images", {})))
        print(f"posts without a photo ({len(missing)}): {', '.join(missing) if missing else 'none'}")
        return

    manifest = {"themes": {}, "post_images": {}, "source": "Wikimedia Commons",
                "unresolved": []}
    for spec in THEMES:
        key, dest = spec["key"], OUT_DIR / f"{spec['key']}.jpg"
        chosen = None
        if dest.exists() and not args.force:
            print(f"skip  {key} (exists)")
        else:
            try:
                cands = search_candidates(spec)
            except RuntimeError as exc:
                print(f"WARN  {key}: {exc}")
                manifest["unresolved"].append(key)
                continue
            if not cands:
                print(f"WARN  {key}: NO on-topic licensed candidate ({spec['query']!r})")
                manifest["unresolved"].append(key)
                continue
            # Honour an explicit pick: Commons search order is relevance, not
            # editorial quality, so a chosen file is pinned to guarantee the
            # published photo matches its alt text and avoids files whose very
            # title makes them unsuitable for a commercial page.
            chosen = None
            if spec.get("pick"):
                cands = [c for c in cands if c["title"] == spec["pick"]]
                if not cands:
                    print(f"WARN  {key}: pinned file not found ({spec['pick']!r})")
                    manifest["unresolved"].append(key)
                    continue
            chosen = cands[0]
            try:
                size = download(chosen["download"], dest)
            except Exception as exc:
                print(f"WARN  {key}: download failed ({exc})")
                manifest["unresolved"].append(key)
                continue
            print(f"ok    {key} <- {chosen['title']} [{chosen['licence']}] {size // 1024}KB")

        if chosen:
            manifest["themes"][key] = {
                "file": f"/img/blog/{key}.jpg",
                "alt": spec["alt"],
                "query": spec["query"],
                "title": chosen["title"],
                "file_page": chosen["file_page"],
                "author": chosen["author"],
                "licence": chosen["licence"],
                "licence_url": chosen["licence_url"],
                "description": chosen["description"],
            }
        # Map every post that declared this theme to the image path.
        for s in spec["posts"]:
            prior = manifest["post_images"].get(s)
            if prior and prior != f"/img/blog/{key}.jpg":
                # Resolution is last-theme-wins, which is easy to get wrong when
                # re-pointing a post. Surface it instead of silently overriding.
                print(f"WARN  post {s!r} already mapped to {prior}, remapped to {key}")
            manifest["post_images"][s] = f"/img/blog/{key}.jpg"

    # Carry forward metadata for skipped themes so the manifest stays complete.
    if not args.force and MANIFEST.exists():
        prev = json.loads(MANIFEST.read_text(encoding="utf-8")).get("themes", {})
        for k, v in prev.items():
            manifest["themes"].setdefault(k, v)
            if f"/img/blog/{k}.jpg" in manifest["post_images"].values():
                manifest["unresolved"] = [u for u in manifest["unresolved"] if u != k]

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nmanifest -> {MANIFEST}")
    print(f"themes resolved: {len(manifest['themes'])}/{len(THEMES)}")
    print(f"posts mapped   : {len(manifest['post_images'])}/60")
    if manifest["unresolved"]:
        print("unresolved themes (posts fall back to designed covers): "
              + ", ".join(sorted(set(manifest["unresolved"]))))


if __name__ == "__main__":
    sys.exit(main())