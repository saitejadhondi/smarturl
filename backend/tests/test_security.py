from src.utils.security import validate_destination_url, classify_user_agent

def test_valid_url():
    ok, _ = validate_destination_url("https://example.com")
    assert ok

def test_localhost_rejected():
    ok, _ = validate_destination_url("http://localhost:8000")
    assert not ok

def test_bad_scheme_rejected():
    ok, _ = validate_destination_url("ftp://example.com")
    assert not ok

def test_mobile_browser():
    x = classify_user_agent("Android Mobile Chrome")
    assert x["device"] == "mobile"
    assert x["browser"] == "Chrome"
