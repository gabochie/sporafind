ROLE_KEYWORDS: dict[str, list[str]] = {
    "finance": [
        "finance", "accountant", "auditor", "cfo", "financial", "controller",
        "treasury", "investment", "banker", "analyst", "portfolio", "asset",
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
        "consultant", "hospital", "healthcare", "veterinary", "vet",
    ],
    "real_estate": [
        "real estate", "property", "surveyor", "estate agent", "landlord",
        "developer", "construction", "architect", "civil engineer", "quantity surveyor",
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


def segment_by_role(role: str | None) -> str | None:
    if not role:
        return None
    role_lower = role.lower().strip()
    for segment, keywords in ROLE_KEYWORDS.items():
        for kw in keywords:
            if kw in role_lower:
                return segment
    return None


def determine_origin(country_of_residence: str | None, nationality: str | None) -> str | None:
    gh_keywords = ["ghana", "ghanaian"]
    for val in [country_of_residence, nationality]:
        if val:
            vl = val.lower()
            for kw in gh_keywords:
                if kw in vl:
                    return "gh"
    return None
