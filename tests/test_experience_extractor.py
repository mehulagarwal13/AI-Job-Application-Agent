from app.services.job_sources.experience_extractor import extract_min_years_required


def test_plus_years():
    assert extract_min_years_required("We need 5+ years of Python") == 5


def test_range():
    assert extract_min_years_required("3-5 years experience required") == 3


def test_minimum_of():
    assert extract_min_years_required("Minimum of 4 years in backend work") == 4


def test_at_least():
    assert extract_min_years_required("at least 2 years with FastAPI") == 2


def test_years_of_experience():
    assert extract_min_years_required("7 years of experience in data") == 7


def test_no_requirement_returns_none():
    assert extract_min_years_required("Great team, remote friendly") is None


def test_empty_returns_none():
    assert extract_min_years_required("") is None
