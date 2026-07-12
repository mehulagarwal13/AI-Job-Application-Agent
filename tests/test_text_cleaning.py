from app.services.text_extraction import clean_text
from app.services.job_sources.html_utils import strip_html
from app.services.job_ingestion import compute_dedup_key


def test_dehyphenation():
    assert "development" in clean_text("develop-\nment of APIs")


def test_bullet_normalization():
    assert "•" not in clean_text("• Python\n• SQL")


def test_whitespace_collapse():
    cleaned = clean_text("too    many     spaces")
    assert "  " not in cleaned


def test_strip_html_keeps_structure():
    text = strip_html("<p>First</p><p>Second</p>")
    assert "First" in text and "Second" in text
    assert "<p>" not in text


def test_strip_html_unescapes_entities():
    assert "&" in strip_html("Fish &amp; Chips")


def test_dedup_key_ignores_formatting():
    a = compute_dedup_key("Senior Backend Engineer", "ACME Corp.")
    b = compute_dedup_key("senior   backend-engineer", "acme corp")
    assert a == b


def test_dedup_key_differs_for_different_roles():
    a = compute_dedup_key("Backend Engineer", "ACME")
    b = compute_dedup_key("Frontend Engineer", "ACME")
    assert a != b
