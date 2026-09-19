from datetime import datetime, timezone
from io import BytesIO
import os
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

from repositories.url_repository import URLRepository


# =========================================================
# SmartURL Application
# =========================================================

app = FastAPI(
    title="SmartURL",
    description="Smart URL Shortener with analytics and QR codes",
    version="1.0.0",
)


repository = URLRepository()


# =========================================================
# Configuration
# =========================================================

PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "http://100.53.178.159:8000"
).rstrip("/")


# =========================================================
# Frontend Configuration
# =========================================================

FRONTEND_PATHS = [
    "/app/frontend",
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "../../frontend"
        )
    ),
]


def get_frontend_path():
    for path in FRONTEND_PATHS:
        if os.path.exists(path):
            return path

    return None


FRONTEND_PATH = get_frontend_path()


if FRONTEND_PATH:

    STATIC_PATH = os.path.join(
        FRONTEND_PATH,
        "static"
    )

    if os.path.exists(STATIC_PATH):

        app.mount(
            "/static",
            StaticFiles(directory=STATIC_PATH),
            name="static"
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

    characters = (
        string.ascii_letters +
        string.digits
    )

    return "".join(
        secrets.choice(characters)
        for _ in range(length)
    )


def build_short_url(short_code: str) -> str:

    return (
        f"{PUBLIC_BASE_URL}/{short_code}"
    )


def build_analytics_url(short_code: str) -> str:

    return (
        f"{PUBLIC_BASE_URL}/analytics/{short_code}"
    )


def build_qr_url(short_code: str) -> str:

    return (
        f"{PUBLIC_BASE_URL}/qr/{short_code}"
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

@app.get(
    "/dashboard",
    include_in_schema=False
)
def dashboard():

    if not FRONTEND_PATH:

        raise HTTPException(
            status_code=404,
            detail="Frontend not found",
        )

    index_file = os.path.join(
        FRONTEND_PATH,
        "index.html"
    )

    if not os.path.exists(index_file):

        raise HTTPException(
            status_code=404,
            detail="Dashboard not found",
        )

    return FileResponse(
        index_file
    )


# =========================================================
# Create Short URL
# =========================================================

@app.post("/urls")
def create_short_url(
    request_data: CreateURLRequest
):

    # -----------------------------------------------------
    # Custom Alias
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

    # -----------------------------------------------------
    # Random Short Code
    # -----------------------------------------------------

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
    # Expiration Validation
    # -----------------------------------------------------

    expires_at = request_data.expires_at

    if expires_at:

        try:

            expiration_time = datetime.fromisoformat(
                expires_at.replace(
                    "Z",
                    "+00:00"
                )
            )

            current_time = datetime.now(
                timezone.utc
            )

            if expiration_time.tzinfo is None:

                expiration_time = (
                    expiration_time.replace(
                        tzinfo=timezone.utc
                    )
                )

            if expiration_time <= current_time:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Expiration time must be "
                        "in the future"
                    ),
                )

        except ValueError:

            raise HTTPException(
                status_code=400,
                detail="Invalid expiration timestamp",
            )

    # -----------------------------------------------------
    # URL Data
    # -----------------------------------------------------

    url_data = {

        "shortCode": short_code,

        "longUrl": str(
            request_data.url
        ),

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
    # Public URLs
    # -----------------------------------------------------

    short_url = build_short_url(
        short_code
    )

    analytics_url = build_analytics_url(
        short_code
    )

    qr_url = build_qr_url(
        short_code
    )

    # -----------------------------------------------------
    # Response
    # -----------------------------------------------------

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
# Get URL Information
# =========================================================

@app.get(
    "/urls/{short_code}"
)
def get_url(
    short_code: str
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

        "data": url_data,

        "shortUrl": build_short_url(
            short_code
        ),

        "analyticsUrl": build_analytics_url(
            short_code
        ),

        "qrUrl": build_qr_url(
            short_code
        ),
    }


# =========================================================
# Analytics API
# =========================================================

@app.get(
    "/analytics/{short_code}"
)
def get_analytics(
    short_code: str
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

    clicks = repository.get_clicks(
        short_code
    )

    clicks.sort(
        key=lambda click: click.get(
            "timestamp",
            ""
        )
    )

    total_analytics_events = len(
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

        "totalAnalyticsEvents": (
            total_analytics_events
        ),

        "firstClick": first_click,

        "lastClick": last_click,

        "clicks": clicks,
    }


# =========================================================
# QR Code API
# =========================================================

@app.get(
    "/qr/{short_code}"
)
def generate_qr_code(
    short_code: str
):

    # -----------------------------------------------------
    # Verify Short URL
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
    # Check URL Status
    # -----------------------------------------------------

    if url_data.get(
        "status"
    ) != "ACTIVE":

        raise HTTPException(
            status_code=410,
            detail="Short URL is no longer active",
        )

    # -----------------------------------------------------
    # Check Expiration
    # -----------------------------------------------------

    expires_at = url_data.get(
        "expiresAt"
    )

    if expires_at:

        try:

            expiration_time = (
                datetime.fromisoformat(
                    expires_at.replace(
                        "Z",
                        "+00:00"
                    )
                )
            )

            current_time = datetime.now(
                timezone.utc
            )

            if expiration_time.tzinfo is None:

                expiration_time = (
                    expiration_time.replace(
                        tzinfo=timezone.utc
                    )
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
                detail=(
                    "Invalid expiration timestamp"
                ),
            )

    # -----------------------------------------------------
    # QR Target
    # -----------------------------------------------------

    target_url = build_short_url(
        short_code
    )

    # -----------------------------------------------------
    # Generate QR Code
    # -----------------------------------------------------

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )

    qr.add_data(
        target_url
    )

    qr.make(
        fit=True
    )

    image = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    # -----------------------------------------------------
    # Store Image In Memory
    # -----------------------------------------------------

    image_buffer = BytesIO()

    image.save(
        image_buffer,
        format="PNG"
    )

    image_buffer.seek(0)

    # -----------------------------------------------------
    # Return PNG
    # -----------------------------------------------------

    return StreamingResponse(
        image_buffer,
        media_type="image/png",
        headers={
            "Content-Disposition": (
                f'inline; filename="{short_code}.png"'
            )
        },
    )


# =========================================================
# Redirect Short URL
# =========================================================

@app.get(
    "/{short_code}"
)
def redirect_to_original_url(
    short_code: str,
    request: Request
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

    # -----------------------------------------------------
    # Status Check
    # -----------------------------------------------------

    if url_data.get(
        "status"
    ) != "ACTIVE":

        raise HTTPException(
            status_code=410,
            detail="Short URL is no longer active",
        )

    # -----------------------------------------------------
    # Expiration Check
    # -----------------------------------------------------

    expires_at = url_data.get(
        "expiresAt"
    )

    if expires_at:

        try:

            expiration_time = (
                datetime.fromisoformat(
                    expires_at.replace(
                        "Z",
                        "+00:00"
                    )
                )
            )

            current_time = datetime.now(
                timezone.utc
            )

            if expiration_time.tzinfo is None:

                expiration_time = (
                    expiration_time.replace(
                        tzinfo=timezone.utc
                    )
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
                detail=(
                    "Invalid expiration timestamp"
                ),
            )

    # -----------------------------------------------------
    # Atomic Click Counter
    # -----------------------------------------------------

    repository.increment_click_count(
        short_code
    )

    # -----------------------------------------------------
    # Analytics Event
    # -----------------------------------------------------

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