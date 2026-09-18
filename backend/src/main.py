from datetime import datetime, timezone
from io import BytesIO
import secrets
import string

import qrcode
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

from src.config import settings
from src.repositories.url_repository import URLRepository
from src.services.rate_limiter import InMemoryRateLimiter
from src.utils.security import classify_user_agent, validate_destination_url

app = FastAPI(title="SmartURL", version="2.0.0")
app.mount("/static", StaticFiles(directory="/app/frontend/static"), name="static")

repository = URLRepository()
limiter = InMemoryRateLimiter(settings.RATE_LIMIT_REQUESTS, settings.RATE_LIMIT_WINDOW_SECONDS)

class CreateURLRequest(BaseModel):
    url: HttpUrl
    custom_alias: str | None = None
    expires_at: str | None = None

def generate_short_code(length=6):
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))

def parse_expiration(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(400, "Invalid expiration timestamp") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if dt <= datetime.now(timezone.utc):
        raise HTTPException(400, "Expiration time must be in the future")
    return dt

def check_limit(request):
    key = request.client.host if request.client else "unknown"
    if not limiter.allow(key):
        raise HTTPException(429, "Rate limit exceeded. Try again later.")

@app.get("/")
def health():
    return {"application": "SmartURL", "status": "running", "version": app.version}

@app.get("/dashboard", include_in_schema=False)
def dashboard():
    return FileResponse("/app/frontend/index.html")

@app.post("/urls")
def create_url(data: CreateURLRequest, request: Request):
    check_limit(request)
    destination = str(data.url)
    safe, reason = validate_destination_url(destination)
    if not safe:
        raise HTTPException(400, reason)

    if data.custom_alias:
        code = data.custom_alias.strip()
        if not code or len(code) > 50:
            raise HTTPException(400, "Custom alias must contain 1 to 50 characters")
        if not code.replace("-", "").replace("_", "").isalnum():
            raise HTTPException(400, "Alias may contain letters, numbers, hyphens and underscores")
        if code in {"analytics", "qr", "docs", "redoc", "dashboard", "static", "urls"}:
            raise HTTPException(400, "This alias is reserved")
        if repository.find_by_short_code(code):
            raise HTTPException(409, "Custom alias already exists")
    else:
        while True:
            code = generate_short_code()
            if not repository.find_by_short_code(code):
                break

    expiration = parse_expiration(data.expires_at)
    item = {
        "shortCode": code,
        "longUrl": destination,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "expiresAt": expiration.isoformat() if expiration else None,
        "clickCount": 0,
        "status": "ACTIVE",
    }
    repository.save(item)
    return {
        "message": "Short URL created successfully",
        "data": item,
        "shortUrl": f"{settings.BASE_URL}/{code}",
        "analyticsUrl": f"{settings.BASE_URL}/analytics/{code}",
        "qrUrl": f"{settings.BASE_URL}/qr/{code}",
    }

@app.get("/urls/{short_code}")
def details(short_code: str):
    item = repository.find_by_short_code(short_code)
    if not item:
        raise HTTPException(404, "Short URL not found")
    return {"data": item}

@app.get("/analytics/{short_code}")
def analytics(short_code: str):
    item = repository.find_by_short_code(short_code)
    if not item:
        raise HTTPException(404, "Short URL not found")
    clicks = repository.get_clicks(short_code)
    clicks.sort(key=lambda x: x.get("timestamp", ""))
    browsers, devices, referrers = {}, {}, {}
    for click in clicks:
        info = classify_user_agent(click.get("userAgent", ""))
        browsers[info["browser"]] = browsers.get(info["browser"], 0) + 1
        devices[info["device"]] = devices.get(info["device"], 0) + 1
        ref = click.get("referrer", "direct")
        referrers[ref] = referrers.get(ref, 0) + 1
    return {
        "shortCode": short_code,
        "longUrl": item.get("longUrl"),
        "status": item.get("status"),
        "clickCount": item.get("clickCount", 0),
        "analyticsEventCount": len(clicks),
        "firstClick": clicks[0].get("timestamp") if clicks else None,
        "lastClick": clicks[-1].get("timestamp") if clicks else None,
        "browsers": browsers,
        "devices": devices,
        "referrers": referrers,
        "clicks": clicks,
    }

@app.get("/qr/{short_code}")
def qr(short_code: str):
    if not repository.find_by_short_code(short_code):
        raise HTTPException(404, "Short URL not found")
    image = qrcode.make(f"{settings.BASE_URL}/{short_code}")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png")

@app.get("/{short_code}")
def redirect(short_code: str, request: Request):
    item = repository.find_by_short_code(short_code)
    if not item:
        raise HTTPException(404, "Short URL not found")
    if item.get("status") != "ACTIVE":
        raise HTTPException(410, "Short URL is no longer active")

    expires_at = item.get("expiresAt")
    if expires_at:
        try:
            expiration = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(500, "Invalid expiration timestamp") from exc
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= expiration:
            repository.mark_expired(short_code)
            raise HTTPException(410, "Short URL has expired")

    repository.increment_click_count(short_code)
    repository.record_click(
        short_code,
        request.headers.get("user-agent", ""),
        request.headers.get("referer", ""),
    )
    return RedirectResponse(item["longUrl"], status_code=302)
