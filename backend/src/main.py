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
from src.services.validation_service import URLValidationService


# =========================================================
# SmartURL Application
# =========================================================

app = FastAPI(
    title="SmartURL",
    description=(
        "Smart URL Shortener with analytics, "
        "QR codes and security validation"
    ),
    version="1.1.0",
)


repository = URLRepository()


# =========================================================
# Frontend Paths
# =========================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

FRONTEND_DIR = (
    PROJECT_ROOT / "frontend"
)

FRONTEND_STATIC_DIR = (
    FRONTEND_DIR / "static"
)


# ---------------------------------------------------------
# Static files
# ---------------------------------------------------------

if FRONTEND_STATIC_DIR.exists():

    app.mount(
        "/static",
        StaticFiles(
            directory=str(
                FRONTEND_STATIC_DIR
            )
        ),
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


def get_public_base_url(
    request: Request,
) -> str:

    return str(
        request.base_url
    ).rstrip("/")


def parse_expiration(
    expires_at: str | None,
):

    if not expires_at:

        return None

    try:

        expiration_time = (
            datetime.fromisoformat(
                expires_at.replace(
                    "Z",
                    "+00:00",
                )
            )
        )

    except ValueError:

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid expiration timestamp"
            ),
        )

    if expiration_time.tzinfo is None:

        expiration_time = (
            expiration_time.replace(
                tzinfo=timezone.utc
            )
        )

    return expiration_time


# =========================================================
# Health Check
# =========================================================

@app.get("/")
def health_check():

    return {
        "application": "SmartURL",
        "status": "running",
        "version": "1.1.0",
    }


# =========================================================
# Dashboard
# =========================================================

@app.get(
    "/dashboard",
    include_in_schema=False,
)
def dashboard():

    # -----------------------------------------------------
    # The current project stores index.html in:
    #
    # frontend/index.html
    #
    # -----------------------------------------------------

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


# =========================================================
# Create Short URL
# =========================================================

@app.post("/urls")
def create_short_url(
    request_data: CreateURLRequest,
    request: Request,
):

    # =====================================================
    # URL SECURITY VALIDATION
    # =====================================================

    url_string = str(
        request_data.url
    )

    is_valid_url, url_error = (
        URLValidationService.validate_url(
            url_string
        )
    )

    if not is_valid_url:

        raise HTTPException(
            status_code=400,
            detail=url_error,
        )

    # =====================================================
    # CUSTOM ALIAS VALIDATION
    # =====================================================

    if request_data.custom_alias:

        short_code = (
            request_data.custom_alias.strip()
        )

        is_valid_alias, alias_error = (
            URLValidationService.validate_alias(
                short_code
            )
        )

        if not is_valid_alias:

            raise HTTPException(
                status_code=400,
                detail=alias_error,
            )

        # -------------------------------------------------
        # Check duplicate alias
        # -------------------------------------------------

        existing_url = (
            repository.find_by_short_code(
                short_code
            )
        )

        if existing_url:

            raise HTTPException(
                status_code=409,
                detail=(
                    "Custom alias already exists"
                ),
            )

    # =====================================================
    # RANDOM SHORT CODE
    # =====================================================

    else:

        while True:

            short_code = (
                generate_short_code()
            )

            existing_url = (
                repository.find_by_short_code(
                    short_code
                )
            )

            if not existing_url:

                break

    # =====================================================
    # EXPIRATION
    # =====================================================

    expires_at = (
        request_data.expires_at
    )

    if expires_at:

        expiration_time = (
            parse_expiration(
                expires_at
            )
        )

        current_time = (
            datetime.now(
                timezone.utc
            )
        )

        if expiration_time <= current_time:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Expiration time must "
                    "be in the future"
                ),
            )

    # =====================================================
    # SAVE URL
    # =====================================================

    url_data = {

        "shortCode": short_code,

        "longUrl": url_string,

        "createdAt": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),

        "expiresAt": expires_at,

        "clickCount": 0,

        "status": "ACTIVE",
    }

    repository.save(
        url_data
    )

    # =====================================================
    # PUBLIC URLS
    # =====================================================

    public_base_url = (
        get_public_base_url(
            request
        )
    )

    short_url = (
        f"{public_base_url}/{short_code}"
    )

    analytics_url = (
        f"{public_base_url}/analytics/"
        f"{short_code}"
    )

    qr_url = (
        f"{public_base_url}/qr/"
        f"{short_code}"
    )

    # =====================================================
    # RESPONSE
    # =====================================================

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
            detail=(
                "Short URL not found"
            ),
        )

    return {

        "shortCode": short_code,

        "longUrl": (
            url_data.get(
                "longUrl"
            )
        ),

        "createdAt": (
            url_data.get(
                "createdAt"
            )
        ),

        "expiresAt": (
            url_data.get(
                "expiresAt"
            )
        ),

        "clickCount": (
            url_data.get(
                "clickCount",
                0,
            )
        ),

        "status": (
            url_data.get(
                "status"
            )
        ),
    }


# =========================================================
# Analytics
# =========================================================

@app.get(
    "/analytics/{short_code}"
)
def get_analytics(
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
            detail=(
                "Short URL not found"
            ),
        )

    clicks = (
        repository.get_clicks(
            short_code
        )
    )

    clicks.sort(
        key=lambda click: click.get(
            "timestamp",
            "",
        )
    )

    first_click = None

    last_click = None

    if clicks:

        first_click = (
            clicks[0].get(
                "timestamp"
            )
        )

        last_click = (
            clicks[-1].get(
                "timestamp"
            )
        )

    return {

        "shortCode": short_code,

        "longUrl": (
            url_data.get(
                "longUrl"
            )
        ),

        "status": (
            url_data.get(
                "status"
            )
        ),

        "clickCount": (
            url_data.get(
                "clickCount",
                0,
            )
        ),

        "totalAnalyticsEvents": len(
            clicks
        ),

        "firstClick": first_click,

        "lastClick": last_click,

        "clicks": clicks,
    }


# =========================================================
# QR Code
# =========================================================

@app.get(
    "/qr/{short_code}"
)
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
            detail=(
                "Short URL not found"
            ),
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

    expires_at = (
        url_data.get(
            "expiresAt"
        )
    )

    if expires_at:

        expiration_time = (
            parse_expiration(
                expires_at
            )
        )

        current_time = (
            datetime.now(
                timezone.utc
            )
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
    # Build short URL
    # -----------------------------------------------------

    public_base_url = (
        get_public_base_url(
            request
        )
    )

    short_url = (
        f"{public_base_url}/{short_code}"
    )

    # -----------------------------------------------------
    # Generate QR
    # -----------------------------------------------------

    qr = qrcode.QRCode(
        version=1,
        error_correction=(
            qrcode.constants.ERROR_CORRECT_M
        ),
        box_size=10,
        border=4,
    )

    qr.add_data(
        short_url
    )

    qr.make(
        fit=True
    )

    image = qr.make_image(
        fill_color="black",
        back_color="white",
    )

    # -----------------------------------------------------
    # PNG
    # -----------------------------------------------------

    buffer = BytesIO()

    image.save(
        buffer,
        format="PNG",
    )

    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="image/png",
        headers={
            "Content-Disposition": (
                f'inline; filename="'
                f'smarturl-{short_code}.png"'
            )
        },
    )


# =========================================================
# Redirect
# =========================================================

@app.get(
    "/{short_code}"
)
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
            detail=(
                "Short URL not found"
            ),
        )

    # -----------------------------------------------------
    # Status
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
    # Expiration
    # -----------------------------------------------------

    expires_at = (
        url_data.get(
            "expiresAt"
        )
    )

    if expires_at:

        expiration_time = (
            parse_expiration(
                expires_at
            )
        )

        current_time = (
            datetime.now(
                timezone.utc
            )
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
    # Atomic click counter
    # -----------------------------------------------------

    repository.increment_click_count(
        short_code
    )

    # -----------------------------------------------------
    # Analytics event
    # -----------------------------------------------------

    repository.record_click(

        short_code=short_code,

        user_agent=(
            request.headers.get(
                "user-agent",
                "",
            )
        ),

        referrer=(
            request.headers.get(
                "referer",
                "",
            )
        ),
    )

    # -----------------------------------------------------
    # Redirect
    # -----------------------------------------------------

    return RedirectResponse(
        url=url_data["longUrl"],
        status_code=302,
    )