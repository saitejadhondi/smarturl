from urllib.parse import urlparse

def validate_destination_url(url):
    try:
        parsed = urlparse(url)
    except ValueError:
        return False, "Invalid URL"
    if parsed.scheme.lower() not in {"http", "https"}:
        return False, "Only http and https URLs are allowed"
    if not parsed.hostname:
        return False, "URL must contain a hostname"
    if parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}:
        return False, "Local destinations are not allowed"
    return True, ""

def classify_user_agent(user_agent):
    ua = (user_agent or "").lower()
    if "ipad" in ua or "tablet" in ua:
        device = "tablet"
    elif "mobile" in ua or "android" in ua or "iphone" in ua:
        device = "mobile"
    else:
        device = "desktop"
    if "edg" in ua:
        browser = "Edge"
    elif "chrome" in ua:
        browser = "Chrome"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "safari" in ua:
        browser = "Safari"
    elif "curl" in ua:
        browser = "curl"
    else:
        browser = "Other"
    return {"device": device, "browser": browser}
