import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "backend" / "src"))

from services.validation_service import validate_url

def test_valid_https_url():
    assert validate_url("https://example.com")

def test_valid_http_url():
    assert validate_url("http://example.com")

def test_invalid_scheme():
    assert not validate_url("javascript:alert(1)")

def test_invalid_url():
    assert not validate_url("not-a-url")
