import re


ROLE_KEYWORDS: dict[str, list[str]] = {
    "finance": [
        "finance", "accountant", "auditor", "cfo", "financial", "controller",
        "treasury", "investment", "banker", "portfolio", "asset",
        "wealth", "tax", "comptroller", "risk", "compliance", "actuary",
        "bookkeeper", "payroll", "underwriter", "merger", "acquisition",
    ],
    "tech": [
        "engineer", "developer", "software", "architect", "data", "devops",
        "backend", "frontend", "full stack", "fullstack", "cloud", "infrastructure",
        "site reliability", "sre", "security", "cyber", "ai", "ml", "machine learning",
        "product manager", "technical", "cto", "chief technology", "platform",
        "api", "integration", "systems", "network", "database", "qa", "test",
    ],
    "legal": [
        "lawyer", "solicitor", "barrister", "legal", "attorney", "counsel",
        "paralegal", "judge", "magistrate", "compliance", "regulatory",
        "general counsel", "notary", "advocate",
    ],
    "healthcare": [
        "doctor", "physician", "nurse", "surgeon", "clinical", "pharmacist",
        "medical", "health", "dentist", "psychiatrist", "therapist", "radiologist",
        "hospital", "healthcare", "veterinary", "vet",
    ],
    "real_estate": [
        "real estate", "property", "surveyor", "estate agent", "landlord",
        "construction", "architect", "civil engineer", "quantity surveyor",
        "facilities", "housing", "mortgage", "valuation",
    ],
    "consulting": [
        "consultant", "consulting", "advisory", "analyst", "strategy",
        "management consultant", "business analyst", "transformation",
        "change management", "digital transformation",
    ],
    "education": [
        "teacher", "lecturer", "professor", "academic", "education", "researcher",
        "headteacher", "principal", "dean", "tutor", "instructor", "phd",
        "fellow", "postdoc", "scientist", "research",
    ],
    "entrepreneur": [
        "founder", "co-founder", "cofounder", "ceo", "chief executive",
        "director", "managing director", "owner", "entrepreneur", "startup",
        "proprietor", "partner", "principal",
    ],
    "public_sector": [
        "civil servant", "government", "diplomat", "ambassador", "policy",
        "public sector", "minister", "mp", "councillor", "mayor", "consul",
        "diplomatic", "embassy", "foreign service",
    ],
}


def _word_boundary(kw: str) -> re.Pattern:
    return re.compile(rf"(?<![a-z]){re.escape(kw)}(?![a-z])", re.IGNORECASE)


_ROLE_PATTERNS: dict[str, list[re.Pattern]] = {
    seg: [_word_boundary(kw) for kw in kws]
    for seg, kws in ROLE_KEYWORDS.items()
}


def segment_by_role(role: str | None) -> str | None:
    if not role:
        return None
    role_lower = role.lower().strip()
    for segment, patterns in _ROLE_PATTERNS.items():
        for pat in patterns:
            if pat.search(role_lower):
                return segment
    return None


_ORIGIN_PATTERNS: dict[str, list[re.Pattern]] = {
    "gh": [_word_boundary(kw) for kw in ["ghana", "ghanaian"]],
}


def determine_origin(country_of_residence: str | None, nationality: str | None) -> str | None:
    for val in [country_of_residence, nationality]:
        if val:
            vl = val.lower()
            for origin, patterns in _ORIGIN_PATTERNS.items():
                for pat in patterns:
                    if pat.search(vl):
                        return origin
    return None
