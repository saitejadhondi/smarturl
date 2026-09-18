from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}

def validate_url(url: str) -> bool:
    """Validate that the URL uses HTTP/HTTPS and has a hostname."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme.lower() in ALLOWED_SCHEMES
            and bool(parsed.netloc)
        )
    except Exception:
        return False
