from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import secrets
import string

import qrcode

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

from src.repositories.url_repository import URLRepository


# =========================================================
# PROJECT PATHS
# =========================================================

CURRENT_FILE = Path(__file__).resolve()

PROJECT_ROOT = CURRENT_FILE.parents[2]

FRONTEND_DIR = PROJECT_ROOT / "frontend"

FRONTEND_STATIC_DIR = FRONTEND_DIR / "static"


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="SmartURL",
    description=(
        "Smart URL Shortener with expiration, "
        "analytics and QR codes"
    ),
    version="2.0.0",
)


# =========================================================
# REPOSITORY
# =========================================================

repository = URLRepository()


# =========================================================
# STATIC FILES
# =========================================================

if FRONTEND_STATIC_DIR.exists():

    app.mount(
        "/static",
        StaticFiles(
            directory=str(FRONTEND_STATIC_DIR)
        ),
        name="static",
    )


# =========================================================
# REQUEST MODELS
# =========================================================

class CreateURLRequest(BaseModel):

    url: HttpUrl

    custom_alias: str | None = None

    expires_at: str | None = None


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def generate_short_code(
    length: int = 6,
) -> str:

    characters = (
        string.ascii_letters
        + string.digits
    )

    return "".join(
        secrets.choice(characters)
        for _ in range(length)
    )


def get_base_url(request: Request) -> str:

    return str(
        request.base_url
    ).rstrip("/")


def parse_expiration(
    expires_at: str | None,
):

    if not expires_at:
        return None

    try:

        expiration_time = datetime.fromisoformat(
            expires_at.replace(
                "Z",
                "+00:00",
            )
        )

    except ValueError:

        raise HTTPException(
            status_code=400,
            detail="Invalid expiration timestamp",
        )

    if expiration_time.tzinfo is None:

        expiration_time = expiration_time.replace(
            tzinfo=timezone.utc
        )

    return expiration_time


def classify_browser(
    user_agent: str,
) -> str:

    user_agent = (
        user_agent or ""
    ).lower()

    if "edg/" in user_agent:

        return "edge"

    if "chrome" in user_agent:

        return "chrome"

    if "firefox" in user_agent:

        return "firefox"

    if "safari" in user_agent:

        return "safari"

    if "curl" in user_agent:

        return "curl"

    if "postman" in user_agent:

        return "postman"

    return "other"


def classify_device(
    user_agent: str,
) -> str:

    user_agent = (
        user_agent or ""
    ).lower()

    mobile_keywords = [
        "mobile",
        "android",
        "iphone",
        "ipad",
        "ipod",
    ]

    for keyword in mobile_keywords:

        if keyword in user_agent:

            return "mobile"

    if "tablet" in user_agent:

        return "tablet"

    return "desktop"


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/")
def health_check():

    return {
        "application": "SmartURL",
        "status": "running",
        "version": "2.0.0",
    }


# =========================================================
# CREATE SHORT URL
# =========================================================

@app.post("/urls")
def create_short_url(
    request_data: CreateURLRequest,
    request: Request,
):

    # -----------------------------------------------------
    # Generate or validate short code
    # -----------------------------------------------------

    if request_data.custom_alias:

        short_code = (
            request_data.custom_alias.strip()
        )

        if not short_code:

            raise HTTPException(
                status_code=400,
                detail="Custom alias cannot be empty",
            )

        existing_url = (
            repository.find_by_short_code(
                short_code
            )
        )

        if existing_url:

            raise HTTPException(
                status_code=409,
                detail="Custom alias already exists",
            )

    else:

        while True:

            short_code = generate_short_code()

            existing_url = (
                repository.find_by_short_code(
                    short_code
                )
            )

            if not existing_url:

                break

    # -----------------------------------------------------
    # Validate expiration
    # -----------------------------------------------------

    expiration_time = parse_expiration(
        request_data.expires_at
    )

    if expiration_time:

        current_time = datetime.now(
            timezone.utc
        )

        if expiration_time <= current_time:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Expiration time must be "
                    "in the future"
                ),
            )

    # -----------------------------------------------------
    # Store URL
    # -----------------------------------------------------

    url_data = {

        "shortCode": short_code,

        "longUrl": str(
            request_data.url
        ),

        "createdAt": datetime.now(
            timezone.utc
        ).isoformat(),

        "expiresAt": request_data.expires_at,

        "clickCount": 0,

        "status": "ACTIVE",
    }

    repository.save(
        url_data
    )

    # -----------------------------------------------------
    # Build public URLs dynamically
    #
    # This prevents localhost:8000 from being returned
    # when the application is accessed through EC2.
    # -----------------------------------------------------

    base_url = get_base_url(
        request
    )

    short_url = (
        f"{base_url}/{short_code}"
    )

    analytics_url = (
        f"{base_url}/analytics/{short_code}"
    )

    qr_url = (
        f"{base_url}/qr/{short_code}"
    )

    return {

        "message": (
            "Short URL created successfully"
        ),

        "data": url_data,

        "shortUrl": short_url,

        "analyticsUrl": analytics_url,

        "qrUrl": qr_url,
    }


# =========================================================
# GET URL DETAILS
# =========================================================

@app.get("/urls/{short_code}")
def get_url_details(
    short_code: str,
):

    url_data = (
        repository.find_by_short_code(
            short_code
        )
    )

    if not url_data:

        raise HTTPException(
            status_code=404,
            detail="Short URL not found",
        )

    return {
        "data": url_data
    }


# =========================================================
# ANALYTICS
# =========================================================

@app.get("/analytics/{short_code}")
def get_analytics(
    short_code: str,
):

    # -----------------------------------------------------
    # Find URL
    # -----------------------------------------------------

    url_data = (
        repository.find_by_short_code(
            short_code
        )
    )

    if not url_data:

        raise HTTPException(
            status_code=404,
            detail="Short URL not found",
        )

    # -----------------------------------------------------
    # Get click events
    # -----------------------------------------------------

    clicks = repository.get_clicks(
        short_code
    )

    # -----------------------------------------------------
    # Sort clicks chronologically
    # -----------------------------------------------------

    clicks.sort(
        key=lambda click: click.get(
            "timestamp",
            "",
        )
    )

    # -----------------------------------------------------
    # Analytics counters
    # -----------------------------------------------------

    browser_counts = {}

    device_counts = {}

    referrer_counts = {}

    for click in clicks:

        user_agent = click.get(
            "userAgent",
            "unknown",
        )

        referrer = click.get(
            "referrer",
            "direct",
        )

        browser = classify_browser(
            user_agent
        )

        device = classify_device(
            user_agent
        )

        browser_counts[browser] = (
            browser_counts.get(
                browser,
                0,
            )
            + 1
        )

        device_counts[device] = (
            device_counts.get(
                device,
                0,
            )
            + 1
        )

        referrer_counts[referrer] = (
            referrer_counts.get(
                referrer,
                0,
            )
            + 1
        )

    # -----------------------------------------------------
    # First and last click
    # -----------------------------------------------------

    first_click = None

    last_click = None

    if clicks:

        first_click = clicks[0].get(
            "timestamp"
        )

        last_click = clicks[-1].get(
            "timestamp"
        )

    # -----------------------------------------------------
    # Return analytics
    # -----------------------------------------------------

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
            0,
        ),

        "analyticsEventCount": len(
            clicks
        ),

        "firstClick": first_click,

        "lastClick": last_click,

        "browsers": browser_counts,

        "devices": device_counts,

        "referrers": referrer_counts,

        "clicks": clicks,
    }


# =========================================================
# QR CODE
# =========================================================

@app.get("/qr/{short_code}")
def generate_qr_code(
    short_code: str,
    request: Request,
):

    # -----------------------------------------------------
    # Find URL
    # -----------------------------------------------------

    url_data = (
        repository.find_by_short_code(
            short_code
        )
    )

    if not url_data:

        raise HTTPException(
            status_code=404,
            detail="Short URL not found",
        )

    # -----------------------------------------------------
    # Build public SmartURL dynamically
    # -----------------------------------------------------

    base_url = get_base_url(
        request
    )

    smart_url = (
        f"{base_url}/{short_code}"
    )

    # -----------------------------------------------------
    # Generate QR code
    # -----------------------------------------------------

    image = qrcode.make(
        smart_url
    )

    buffer = BytesIO()

    image.save(
        buffer,
        format="PNG",
    )

    buffer.seek(0)

    # -----------------------------------------------------
    # Return PNG
    # -----------------------------------------------------

    return StreamingResponse(
        buffer,
        media_type="image/png",
        headers={
            "Content-Disposition": (
                f'inline; filename="{short_code}.png"'
            )
        },
    )


# =========================================================
# REDIRECT
# =========================================================

@app.get("/{short_code}")
def redirect_to_original_url(
    short_code: str,
    request: Request,
):

    # -----------------------------------------------------
    # Find URL
    # -----------------------------------------------------

    url_data = (
        repository.find_by_short_code(
            short_code
        )
    )

    if not url_data:

        raise HTTPException(
            status_code=404,
            detail="Short URL not found",
        )

    # -----------------------------------------------------
    # Check status
    # -----------------------------------------------------

    if url_data.get(
        "status"
    ) != "ACTIVE":

        raise HTTPException(
            status_code=410,
            detail=(
                "Short URL is no longer active"
            ),
        )

    # -----------------------------------------------------
    # Check expiration
    # -----------------------------------------------------

    expires_at = url_data.get(
        "expiresAt"
    )

    if expires_at:

        expiration_time = parse_expiration(
            expires_at
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
                detail=(
                    "Short URL has expired"
                ),
            )

    # -----------------------------------------------------
    # Increment click counter
    # -----------------------------------------------------

    repository.increment_click_count(
        short_code
    )

    # -----------------------------------------------------
    # Store analytics event
    # -----------------------------------------------------

    repository.record_click(

        short_code=short_code,

        user_agent=request.headers.get(
            "user-agent",
            "",
        ),

        referrer=request.headers.get(
            "referer",
            "",
        ),
    )

    # -----------------------------------------------------
    # Redirect
    # -----------------------------------------------------

    return RedirectResponse(

        url=url_data[
            "longUrl"
        ],

        status_code=302,
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.get(
    "/dashboard",
    include_in_schema=False,
)
def dashboard():

    dashboard_file = (
        FRONTEND_DIR / "index.html"
    )

    if not dashboard_file.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                "Dashboard frontend not found"
            ),
        )

    return FileResponse(
        str(dashboard_file)
    )