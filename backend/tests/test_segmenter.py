import pytest

from app.services.segmenter import segment_by_role, determine_origin


class TestSegmentByRole:
    def test_returns_none_for_none(self):
        assert segment_by_role(None) is None

    def test_returns_none_for_empty(self):
        assert segment_by_role("") is None

    def test_finance(self):
        assert segment_by_role("Accountant") == "finance"
        assert segment_by_role("CFO") == "finance"
        assert segment_by_role("Financial Analyst") == "finance"

    def test_tech(self):
        assert segment_by_role("Software Engineer") == "tech"
        assert segment_by_role("DevOps Engineer") == "tech"
        assert segment_by_role("Data Scientist") == "tech"
        assert segment_by_role("CTO") == "tech"

    def test_legal(self):
        assert segment_by_role("Lawyer") == "legal"
        assert segment_by_role("Solicitor") == "legal"
        assert segment_by_role("General Counsel") == "legal"

    def test_healthcare(self):
        assert segment_by_role("Doctor") == "healthcare"
        assert segment_by_role("Nurse") == "healthcare"
        assert segment_by_role("Pharmacist") == "healthcare"

    def test_real_estate(self):
        assert segment_by_role("Real Estate Agent") == "real_estate"
        assert segment_by_role("Property Manager") == "real_estate"
        assert segment_by_role("Construction Manager") == "real_estate"

    def test_consulting(self):
        assert segment_by_role("Management Consultant") == "consulting"
        assert segment_by_role("Strategy Consultant") == "consulting"
        assert segment_by_role("Business Analyst") == "consulting"

    def test_education(self):
        assert segment_by_role("Professor") == "education"
        assert segment_by_role("Teacher") == "education"
        assert segment_by_role("Researcher") == "education"

    def test_entrepreneur(self):
        assert segment_by_role("CEO") == "entrepreneur"
        assert segment_by_role("Founder") == "entrepreneur"
        assert segment_by_role("Managing Director") == "entrepreneur"

    def test_public_sector(self):
        assert segment_by_role("Civil Servant") == "public_sector"
        assert segment_by_role("Diplomat") == "public_sector"
        assert segment_by_role("Ambassador") == "public_sector"

    def test_developer_only_in_tech_not_real_estate(self):
        assert segment_by_role("Software Developer") == "tech"
        assert segment_by_role("Web Developer") == "tech"


class TestDetermineOrigin:
    def test_from_nationality(self):
        assert determine_origin(None, "Ghanaian") == "gh"

    def test_from_country_of_residence(self):
        assert determine_origin("Ghana", "American") == "gh"

    def test_returns_none_for_unrelated(self):
        assert determine_origin("United States", "American") is None