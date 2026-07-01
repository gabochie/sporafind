import pytest

from app.services.diaspora_scraper import (
    _extract_city,
    _extract_region,
    DIRECTORY_SOURCES,
    ORGS_TARGETED,
)


class TestExtractCity:
    def test_from_location_field(self):
        assert _extract_city("Baltimore, MD", "some text") == "Baltimore"

    def test_from_text_pattern(self):
        assert _extract_city("", "Located in Houston, TX area") == "Houston"

    def test_returns_empty_when_no_match(self):
        assert _extract_city("", "Some random text without location") == ""

    def test_from_text_maryland(self):
        assert _extract_city("", "Silver Spring, Maryland") == "Silver Spring"

    def test_handles_multi_word_city(self):
        assert _extract_city("", "San Antonio, Texas business") == "San Antonio"


class TestExtractRegion:
    def test_from_location_field(self):
        assert _extract_region("Austin, TX", "") == "TX"

    def test_from_text_md(self):
        assert _extract_region("", "Baltimore, MD") == "MD"

    def test_from_text_maryland_expanded(self):
        assert _extract_region("", "Silver Spring, Maryland") == "MD"

    def test_from_text_texas_expanded(self):
        assert _extract_region("", "Houston, Texas") == "TX"

    def test_returns_empty_when_no_match(self):
        assert _extract_region("", "No region here") == ""


class TestDirectorySources:
    def test_all_sources_have_required_fields(self):
        for s in DIRECTORY_SOURCES:
            assert s["id"]
            assert s["name"]
            assert s["url"].startswith("http")
            assert s["parser"]
            assert s["type"]


class TestOrgsTargeted:
    def test_all_orgs_have_required_fields(self):
        for org in ORGS_TARGETED:
            assert org["name"]
            assert org["locality"]
            assert org["region"] in ("MD", "TX")
            assert org["country"] == "United States"
            assert org["org_type"]
            assert isinstance(org["tags"], list)
            assert isinstance(org["origin"], (str, type(None)))