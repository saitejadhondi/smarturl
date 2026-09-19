from datetime import datetime, timezone
from pathlib import Path
import secrets
import string

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

from src.repositories.url_repository import URLRepository


# =========================================================
# Application
# =========================================================

app = FastAPI(
    title="SmartURL",
    description="Smart URL Shortener with analytics and QR codes",
    version="1.0.0",
)


repository = URLRepository()


# =========================================================
# Frontend Paths
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

FRONTEND_DIR = PROJECT_ROOT / "frontend"

STATIC_DIR = FRONTEND_DIR / "static"

INDEX_FILE = FRONTEND_DIR / "index.html"


# Serve frontend static files
if STATIC_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static",
    )


# =========================================================
# Request Models
# =========================================================

class CreateURLRequest(BaseModel):
    url: HttpUrl
    custom_alias: str | None = None
    expires_at: str | None = None


# =========================================================
# Helper Functions
# =========================================================

def generate_short_code(length: int = 6) -> str:
    """Generate a random short URL code."""

    characters = string.ascii_letters + string.digits

    return "".join(
        secrets.choice(characters)
        for _ in range(length)
    )


def validate_expiration(expires_at: str | None):
    """Validate expiration timestamp."""

    if not expires_at:
        return

    try:
        expiration_time = datetime.fromisoformat(
            expires_at.replace("Z", "+00:00")
        )

        if expiration_time.tzinfo is None:
            expiration_time = expiration_time.replace(
                tzinfo=timezone.utc
            )

        current_time = datetime.now(timezone.utc)

        if expiration_time <= current_time:
            raise HTTPException(
                status_code=400,
                detail="Expiration time must be in the future",
            )

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid expiration timestamp",
        )


# =========================================================
# Health Check
# =========================================================

@app.get("/")
def health_check():

    return {
        "application": "SmartURL",
        "status": "running",
        "version": "1.0.0",
    }


# =========================================================
# Dashboard
# =========================================================

@app.get("/dashboard", include_in_schema=False)
def dashboard():

    if not INDEX_FILE.exists():

        raise HTTPException(
            status_code=500,
            detail="Frontend dashboard not found",
        )

    return FileResponse(
        str(INDEX_FILE)
    )


# =========================================================
# Create Short URL
# =========================================================

@app.post("/urls")
def create_short_url(
    request_data: CreateURLRequest,
    request: Request
):

    # -----------------------------------------------------
    # Custom alias
    # -----------------------------------------------------

    if request_data.custom_alias:

        short_code = request_data.custom_alias.strip()

        if not short_code:

            raise HTTPException(
                status_code=400,
                detail="Custom alias cannot be empty",
            )

        existing_url = repository.find_by_short_code(
            short_code
        )

        if existing_url:

            raise HTTPException(
                status_code=409,
                detail="Custom alias already exists",
            )

    # -----------------------------------------------------
    # Random short code
    # -----------------------------------------------------

    else:

        while True:

            short_code = generate_short_code()

            existing_url = repository.find_by_short_code(
                short_code
            )

            if not existing_url:
                break

    # -----------------------------------------------------
    # Expiration
    # -----------------------------------------------------

    expires_at = request_data.expires_at

    validate_expiration(
        expires_at
    )

    # -----------------------------------------------------
    # Save URL
    # -----------------------------------------------------

    url_data = {
        "shortCode": short_code,
        "longUrl": str(request_data.url),
        "createdAt": datetime.now(
            timezone.utc
        ).isoformat(),
        "expiresAt": expires_at,
        "clickCount": 0,
        "status": "ACTIVE",
    }

    repository.save(
        url_data
    )

    # -----------------------------------------------------
    # Public URL
    # -----------------------------------------------------

    public_base_url = str(
        request.base_url
    ).rstrip("/")

    short_url = (
        f"{public_base_url}/{short_code}"
    )

    analytics_url = (
        f"{public_base_url}/analytics/{short_code}"
    )

    qr_url = (
        f"{public_base_url}/qr/{short_code}"
    )

    return {
        "message": "Short URL created successfully",

        "data": url_data,

        "shortUrl": short_url,

        "analyticsUrl": analytics_url,

        "qrUrl": qr_url,
    }


# =========================================================
# Get URL Information
# =========================================================

@app.get("/urls/{short_code}")
def get_url(
    short_code: str,
    request: Request
):

    url_data = repository.find_by_short_code(
        short_code
    )

    if not url_data:

        raise HTTPException(
            status_code=404,
            detail="Short URL not found",
        )

    public_base_url = str(
        request.base_url
    ).rstrip("/")

    return {
        "data": url_data,

        "shortUrl": (
            f"{public_base_url}/{short_code}"
        ),

        "analyticsUrl": (
            f"{public_base_url}/analytics/{short_code}"
        ),

        "qrUrl": (
            f"{public_base_url}/qr/{short_code}"
        ),
    }


# =========================================================
# Analytics API
# =========================================================

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

    total_clicks = len(
        clicks
    )

    first_click = None
    last_click = None

    if clicks:

        first_click = clicks[0].get(
            "timestamp"
        )

        last_click = clicks[-1].get(
            "timestamp"
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

        "totalAnalyticsEvents": total_clicks,

        "firstClick": first_click,

        "lastClick": last_click,

        "clicks": clicks,
    }


# =========================================================
# Redirect Short URL
# =========================================================

@app.get("/{short_code}")
def redirect_to_original_url(
    short_code: str,
    request: Request
):

    url_data = repository.find_by_short_code(
        short_code
    )

    if not url_data:

        raise HTTPException(
            status_code=404,
            detail="Short URL not found",
        )

    # -----------------------------------------------------
    # Check status
    # -----------------------------------------------------

    if url_data.get("status") != "ACTIVE":

        raise HTTPException(
            status_code=410,
            detail="Short URL is no longer active",
        )

    # -----------------------------------------------------
    # Check expiration
    # -----------------------------------------------------

    expires_at = url_data.get(
        "expiresAt"
    )

    if expires_at:

        try:

            expiration_time = datetime.fromisoformat(
                expires_at.replace(
                    "Z",
                    "+00:00"
                )
            )

            if expiration_time.tzinfo is None:

                expiration_time = expiration_time.replace(
                    tzinfo=timezone.utc
                )

            current_time = datetime.now(
                timezone.utc
            )

            if current_time >= expiration_time:

                repository.mark_expired(
                    short_code
                )

                raise HTTPException(
                    status_code=410,
                    detail="Short URL has expired",
                )

        except ValueError:

            raise HTTPException(
                status_code=500,
                detail="Invalid expiration timestamp",
            )

    # -----------------------------------------------------
    # Record click
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

    # -----------------------------------------------------
    # Redirect
    # -----------------------------------------------------

    return RedirectResponse(
        url=url_data["longUrl"],
        status_code=302,
    )