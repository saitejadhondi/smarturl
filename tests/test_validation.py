from backend.src.services.validation_service import URLValidationService

def test_valid_https_url():
    assert URLValidationService.validate_url("https://example.com")[0]

def test_valid_http_url():
    assert URLValidationService.validate_url("http://example.com")[0]

def test_invalid_scheme():
    assert not URLValidationService.validate_url("javascript:alert(1)")[0]

def test_invalid_url():
    assert not URLValidationService.validate_url("not-a-url")[0]
