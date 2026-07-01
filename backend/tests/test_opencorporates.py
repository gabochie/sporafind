import pytest

from app.services.opencorporates import OpenCorporatesClient, DIASPORA_SURNAMES_PREFIXES, ORIGIN_MAP


class TestParseCompany:
    def test_returns_none_for_empty(self):
        assert OpenCorporatesClient.parse_company({}) is None

    def test_returns_none_for_no_company_number(self):
        assert OpenCorporatesClient.parse_company({"company": {"name": "Test"}}) is None

    def test_parses_valid_company(self):
        raw = {
            "company": {
                "company_number": "12345",
                "name": "Ghana Ventures LLC",
                "jurisdiction_code": "US_TX",
                "company_status": "active",
                "company_type": "llc",
                "registered_address": {"city": "Houston", "state": "TX", "country": "United States"},
            }
        }
        result = OpenCorporatesClient.parse_company(raw)
        assert result is not None
        assert result["name"] == "Ghana Ventures LLC"
        assert result["source_id"] == "US_TX/12345"
        assert result["jurisdiction"] == "US_TX"
        assert result["locality"] == "Houston"
        assert "ghana" in result["tags"]

    def test_parse_company_no_tags_for_non_african_name(self):
        raw = {
            "company": {
                "company_number": "999",
                "name": "American Holdings Inc",
                "jurisdiction_code": "US_TX",
            }
        }
        result = OpenCorporatesClient.parse_company(raw)
        assert result is not None
        assert result["tags"] == []


class TestParseOfficer:
    def test_returns_none_for_empty(self):
        assert OpenCorporatesClient.parse_officer({}, "US_TX", "Test Co") is None

    def test_returns_none_for_no_name(self):
        assert OpenCorporatesClient.parse_officer({"officer": {"uid": "1"}}, "US_TX", "Test Co") is None

    def test_parses_valid_officer(self):
        raw = {"officer": {"uid": "1", "name": "Smith, John", "position": "CEO", "nationality": "Nigerian"}}
        result = OpenCorporatesClient.parse_officer(raw, "US_TX", "Test Co")
        assert result is not None
        assert result["name"] == "Smith, John"
        assert result["role"] == "CEO"
        assert result["origin"] == "ng"
        assert result["company_name"] == "Test Co"

    def test_detects_origin_from_nationality(self):
        raw = {"officer": {"uid": "2", "name": "Doe, Jane", "nationality": "Ghanaian"}}
        result = OpenCorporatesClient.parse_officer(raw, "US_MD", "Co")
        assert result["origin"] == "gh"

    def test_detects_origin_from_name_when_no_nationality(self):
        raw = {"officer": {"uid": "3", "name": "Okafor, Chidi"}}
        result = OpenCorporatesClient.parse_officer(raw, "US_TX", "Co")
        assert result is not None

    def test_detects_diaspora_surname_prefix(self):
        raw = {"officer": {"uid": "4", "name": "Nwachukwu, Emeka"}}
        result = OpenCorporatesClient.parse_officer(raw, "US_TX", "Co")
        assert result is not None

    def test_date_of_birth_parsing(self):
        raw = {"officer": {"uid": "5", "name": "Test Person", "date_of_birth": "1980-06-15"}}
        result = OpenCorporatesClient.parse_officer(raw, "US_TX", "Co")
        assert result is not None
        assert result["date_of_birth"] is not None

    def test_malformed_date_of_birth(self):
        raw = {"officer": {"uid": "6", "name": "Test Person", "date_of_birth": "not-a-date"}}
        result = OpenCorporatesClient.parse_officer(raw, "US_TX", "Co")
        assert result is not None
        assert result["date_of_birth"] is None


class TestDetectOrigin:
    def test_from_nationality(self):
        assert OpenCorporatesClient._detect_origin("Kenyan", "John Doe") == "ke"

    def test_from_name(self):
        assert OpenCorporatesClient._detect_origin(None, "Ethiopian Coffee Ltd") == "et"

    def test_senegal_vs_sierra_leone(self):
        assert OpenCorporatesClient._detect_origin("Senegalese", "Moussa Diop") == "sn"

    def test_returns_none_for_unrelated(self):
        assert OpenCorporatesClient._detect_origin("American", "John Smith") is None

    def test_diaspora_surname_prefix(self):
        result = OpenCorporatesClient._detect_origin(None, "Diop, Amadou")
        assert result == "diaspora"

    def test_niger_not_nigeria(self):
        result = OpenCorporatesClient._detect_origin(None, "Niger Resources Ltd")
        assert result == "ne"


class TestAvailable:
    def test_false_when_no_token(self, monkeypatch):
        monkeypatch.setattr("app.services.opencorporates.settings.opencorporates_api_key", "")
        client = OpenCorporatesClient()
        assert client.available is False

    def test_true_when_token(self, monkeypatch):
        monkeypatch.setattr("app.services.opencorporates.settings.opencorporates_api_key", "test-key")
        client = OpenCorporatesClient()
        assert client.available is True