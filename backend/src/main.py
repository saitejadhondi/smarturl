from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
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


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

FRONTEND_DIR = PROJECT_ROOT / "frontend"
FRONTEND_STATIC_DIR = FRONTEND_DIR / "static"


# ---------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------

app = FastAPI(
    title="SmartURL",
    description="Smart URL shortener with expiration, analytics and QR codes",
    version="2.0.0",
)


# Serve frontend static files
app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_STATIC_DIR)),
    name="static",
)


repository = URLRepository()

rate_limiter = InMemoryRateLimiter(
    settings.RATE_LIMIT_REQUESTS,
    settings.RATE_LIMIT_WINDOW_SECONDS,
)


# ---------------------------------------------------------
# Request Models
# ---------------------------------------------------------

class CreateURLRequest(BaseModel):
    url: HttpUrl
    custom_alias: str | None = None
    expires_at: str | None = None


# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------

def generate_short_code(length: int = 6) -> str:
    characters = string.ascii_letters + string.digits

    return "".join(
        secrets.choice(characters)
        for _ in range(length)
    )


def parse_expiration(value: str | None):

    if not value:
        return None

    try:

        expiration = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail="Invalid expiration timestamp",
        ) from exc

    if expiration.tzinfo is None:

        expiration = expiration.replace(
            tzinfo=timezone.utc
        )

    if expiration <= datetime.now(timezone.utc):

        raise HTTPException(
            status_code=400,
            detail="Expiration time must be in the future",
        )

    return expiration


def check_rate_limit(request: Request):

    client_ip = (
        request.client.host
        if request.client
        else "unknown"
    )

    if not rate_limiter.allow(client_ip):

        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later.",
        )


# ---------------------------------------------------------
# Health Check
# ---------------------------------------------------------

@app.get("/")
def health_check():

    return {
        "application": "SmartURL",
        "status": "running",
        "version": app.version,
    }


# ---------------------------------------------------------
# Dashboard
# ---------------------------------------------------------

@app.get(
    "/dashboard",
    include_in_schema=False
)
def dashboard():

    return FileResponse(
        str(FRONTEND_DIR / "index.html")
    )


# ---------------------------------------------------------
# Create Short URL
# ---------------------------------------------------------

@app.post("/urls")
def create_short_url(
    data: CreateURLRequest,
    request: Request,
):

    check_rate_limit(request)

    destination = str(data.url)

    safe, reason = validate_destination_url(
        destination
    )

    if not safe:

        raise HTTPException(
            status_code=400,
            detail=reason,
        )


    # -----------------------------------------------------
    # Custom Alias
    # -----------------------------------------------------

    if data.custom_alias:

        short_code = data.custom_alias.strip()

        if not short_code:

            raise HTTPException(
                status_code=400,
                detail="Custom alias cannot be empty",
            )

        if len(short_code) > 50:

            raise HTTPException(
                status_code=400,
                detail="Custom alias must contain 1 to 50 characters",
            )

        if not short_code.replace(
            "-",
            ""
        ).replace(
            "_",
            ""
        ).isalnum():

            raise HTTPException(
                status_code=400,
                detail=(
                    "Alias may contain letters, "
                    "numbers, hyphens and underscores"
                ),
            )

        reserved_aliases = {
            "analytics",
            "qr",
            "docs",
            "redoc",
            "dashboard",
            "static",
            "urls",
        }

        if short_code in reserved_aliases:

            raise HTTPException(
                status_code=400,
                detail="This alias is reserved",
            )

        existing = repository.find_by_short_code(
            short_code
        )

        if existing:

            raise HTTPException(
                status_code=409,
                detail="Custom alias already exists",
            )


    # -----------------------------------------------------
    # Random Short Code
    # -----------------------------------------------------

    else:

        while True:

            short_code = generate_short_code()

            existing = repository.find_by_short_code(
                short_code
            )

            if not existing:

                break


    # -----------------------------------------------------
    # Expiration
    # -----------------------------------------------------

    expiration = parse_expiration(
        data.expires_at
    )


    # -----------------------------------------------------
    # Save URL
    # -----------------------------------------------------

    url_data = {

        "shortCode": short_code,

        "longUrl": destination,

        "createdAt": datetime.now(
            timezone.utc
        ).isoformat(),

        "expiresAt": (
            expiration.isoformat()
            if expiration
            else None
        ),

        "clickCount": 0,

        "status": "ACTIVE",
    }


    repository.save(
        url_data
    )


    return {

        "message": "Short URL created successfully",

        "data": url_data,

        "shortUrl": (
            f"{settings.BASE_URL}/{short_code}"
        ),

        "analyticsUrl": (
            f"{settings.BASE_URL}/analytics/{short_code}"
        ),

        "qrUrl": (
            f"{settings.BASE_URL}/qr/{short_code}"
        ),
    }


# ---------------------------------------------------------
# URL Details
# ---------------------------------------------------------

@app.get("/urls/{short_code}")
def get_url_details(
    short_code: str
):

    url_data = repository.find_by_short_code(
        short_code
    )

    if not url_data:

        raise HTTPException(
            status_code=404,
            detail="Short URL not found",
        )

    return {
        "data": url_data
    }


# ---------------------------------------------------------
# Analytics
# ---------------------------------------------------------

@app.get("/analytics/{short_code}")
def get_analytics(
    short_code: str
):

    url_data = repository.find_by_short_code(
        short_code
    )

    if not url_data:

        raise HTTPException(
            status_code=404,
            detail="Short URL not found",
        )


    clicks = repository.get_clicks(
        short_code
    )


    clicks.sort(
        key=lambda click: click.get(
            "timestamp",
            ""
        )
    )


    browsers = {}

    devices = {}

    referrers = {}


    for click in clicks:

        classification = classify_user_agent(
            click.get(
                "userAgent",
                ""
            )
        )


        browser = classification["browser"]

        browsers[browser] = (
            browsers.get(
                browser,
                0
            ) + 1
        )


        device = classification["device"]

        devices[device] = (
            devices.get(
                device,
                0
            ) + 1
        )


        referrer = click.get(
            "referrer",
            "direct"
        )

        referrers[referrer] = (
            referrers.get(
                referrer,
                0
            ) + 1
        )


    return {

        "shortCode": short_code,

        "longUrl": url_data.get(
            "longUrl"
        ),

        "status": url_data.get(
            "status"
        ),

        "clickCount": url_data.get(
            "clickCount",
            0
        ),

        "analyticsEventCount": len(
            clicks
        ),

        "firstClick": (
            clicks[0].get("timestamp")
            if clicks
            else None
        ),

        "lastClick": (
            clicks[-1].get("timestamp")
            if clicks
            else None
        ),

        "browsers": browsers,

        "devices": devices,

        "referrers": referrers,

        "clicks": clicks,
    }


# ---------------------------------------------------------
# QR Code
# ---------------------------------------------------------

@app.get("/qr/{short_code}")
def generate_qr(
    short_code: str
):

    url_data = repository.find_by_short_code(
        short_code
    )

    if not url_data:

        raise HTTPException(
            status_code=404,
            detail="Short URL not found",
        )


    smart_url = (
        f"{settings.BASE_URL}/{short_code}"
    )


    image = qrcode.make(
        smart_url
    )


    buffer = BytesIO()

    image.save(
        buffer,
        format="PNG"
    )

    buffer.seek(0)


    return StreamingResponse(
        buffer,
        media_type="image/png",
        headers={
            "Content-Disposition": (
                f'inline; filename="{short_code}.png"'
            )
        },
    )


# ---------------------------------------------------------
# Redirect
# ---------------------------------------------------------

@app.get("/{short_code}")
def redirect_to_original_url(
    short_code: str,
    request: Request,
):

    url_data = repository.find_by_short_code(
        short_code
    )


    if not url_data:

        raise HTTPException(
            status_code=404,
            detail="Short URL not found",
        )


    if url_data.get(
        "status"
    ) != "ACTIVE":

        raise HTTPException(
            status_code=410,
            detail="Short URL is no longer active",
        )


    expires_at = url_data.get(
        "expiresAt"
    )


    if expires_at:

        try:

            expiration = datetime.fromisoformat(
                expires_at.replace(
                    "Z",
                    "+00:00"
                )
            )

        except ValueError as exc:

            raise HTTPException(
                status_code=500,
                detail="Invalid expiration timestamp",
            ) from exc


        if expiration.tzinfo is None:

            expiration = expiration.replace(
                tzinfo=timezone.utc
            )


        if datetime.now(
            timezone.utc
        ) >= expiration:

            repository.mark_expired(
                short_code
            )

            raise HTTPException(
                status_code=410,
                detail="Short URL has expired",
            )


    # -----------------------------------------------------
    # Click Tracking
    # -----------------------------------------------------

    repository.increment_click_count(
        short_code
    )


    repository.record_click(

        short_code=short_code,

        user_agent=request.headers.get(
            "user-agent",
            ""
        ),

        referrer=request.headers.get(
            "referer",
            ""
        ),
    )


    return RedirectResponse(
        url=url_data["longUrl"],
        status_code=302,
    )