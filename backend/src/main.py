from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import io

import qrcode

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
)
from fastapi.responses import (
    FileResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

from src.repositories.url_repository import URLRepository
from src.services.rate_limiter import RateLimiter
from src.services.validation_service import URLValidationService


# ============================================================
# Application
# ============================================================

app = FastAPI(
    title="SmartURL API",
    description=(
        "Smart URL Shortener with "
        "analytics, QR codes and AWS DynamoDB"
    ),
    version="1.2.0",
)


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

FRONTEND_DIR = PROJECT_ROOT / "frontend"

FRONTEND_STATIC_DIR = (
    FRONTEND_DIR / "static"
)


# ============================================================
# Services
# ============================================================

repository = URLRepository()

validation_service = URLValidationService()

rate_limiter = RateLimiter(
    max_requests=10,
    window_seconds=60,
)


# ============================================================
# Static files
# ============================================================

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


# ============================================================
# Request Models
# ============================================================

class CreateURLRequest(BaseModel):

    url: HttpUrl

    custom_alias: Optional[str] = None

    expires_at: Optional[datetime] = None


# ============================================================
# Helper Functions
# ============================================================

def get_client_ip(
    request: Request,
) -> str:
    """
    Get the client IP address.

    For the current EC2 setup we use the direct
    client host address.

    Later, when Nginx/reverse proxy is added,
    this can be extended to safely handle
    forwarded headers.
    """

    if request.client:

        return request.client.host

    return "unknown"


def ensure_future_expiration(
    expires_at: Optional[datetime],
) -> Optional[datetime]:
    """
    Validate expiration timestamp.
    """

    if expires_at is None:
        return None

    if expires_at.tzinfo is None:

        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    now = datetime.now(timezone.utc)

    if expires_at <= now:

        raise HTTPException(
            status_code=400,
            detail=(
                "Expiration time must be "
                "in the future"
            ),
        )

    return expires_at


# ============================================================
# Root / Health Check
# ============================================================

@app.get("/")
def health_check():

    return {
        "application": "SmartURL",
        "status": "running",
        "version": "1.2.0",
    }


# ============================================================
# Dashboard
# ============================================================

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
            detail="Dashboard not found",
        )

    return FileResponse(
        dashboard_file
    )


# ============================================================
# Create Short URL
# ============================================================

@app.post("/urls")
def create_short_url(
    request_data: CreateURLRequest,
    request: Request,
):
    """
    Create a new shortened URL.

    Rate limit:
        10 requests per minute per IP.
    """

    # --------------------------------------------------------
    # Rate limiting
    # --------------------------------------------------------

    client_ip = get_client_ip(request)

    if not rate_limiter.is_allowed(
        client_ip
    ):

        raise HTTPException(
            status_code=429,
            detail=(
                "Rate limit exceeded. "
                "Maximum 10 URL creation "
                "requests are allowed per minute."
            ),
            headers={
                "Retry-After": "60"
            },
        )

    # --------------------------------------------------------
    # Validate destination URL
    # --------------------------------------------------------

    destination_url = str(
        request_data.url
    )

    is_valid_url, url_error = (
        validation_service.validate_url(
            destination_url
        )
    )

    if not is_valid_url:

        raise HTTPException(
            status_code=400,
            detail=url_error,
        )

    # --------------------------------------------------------
    # Validate custom alias
    # --------------------------------------------------------

    custom_alias = (
        request_data.custom_alias
    )

    if custom_alias:

        custom_alias = custom_alias.strip()

        is_valid_alias, alias_error = (
            validation_service.validate_alias(
                custom_alias
            )
        )

        if not is_valid_alias:

            raise HTTPException(
                status_code=400,
                detail=alias_error,
            )

        # ----------------------------------------------------
        # Check duplicate alias
        # ----------------------------------------------------

        existing_url = (
            repository.get_url(
                custom_alias
            )
        )

        if existing_url:

            raise HTTPException(
                status_code=409,
                detail=(
                    "Custom alias is already in use"
                ),
            )

    # --------------------------------------------------------
    # Validate expiration
    # --------------------------------------------------------

    expires_at = ensure_future_expiration(
        request_data.expires_at
    )

    # --------------------------------------------------------
    # Create URL
    # --------------------------------------------------------

    try:

        result = repository.create_url(
            original_url=destination_url,
            custom_alias=custom_alias,
            expires_at=expires_at,
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:

        print(
            "Error creating URL:",
            error,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to create short URL"
            ),
        )

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    short_code = result["shortCode"]

    return {
        "message": "Short URL created successfully",

        "shortCode": short_code,

        "originalUrl": destination_url,

        "shortUrl": (
            f"/{short_code}"
        ),

        "analyticsUrl": (
            f"/analytics/{short_code}"
        ),

        "qrUrl": (
            f"/qr/{short_code}"
        ),

        "expiresAt": (
            result.get("expiresAt")
        ),
    }


# ============================================================
# Get URL Information
# ============================================================

@app.get("/urls/{short_code}")
def get_url(
    short_code: str,
):

    result = repository.get_url(
        short_code
    )

    if not result:

        raise HTTPException(
            status_code=404,
            detail="Short URL not found",
        )

    return result


# ============================================================
# Analytics
# ============================================================

@app.get(
    "/analytics/{short_code}"
)
def get_analytics(
    short_code: str,
):

    url_data = repository.get_url(
        short_code
    )

    if not url_data:

        raise HTTPException(
            status_code=404,
            detail="Short URL not found",
        )

    clicks = (
        repository.get_click_events(
            short_code
        )
    )

    return {
        "shortCode": short_code,

        "originalUrl": (
            url_data.get("originalUrl")
        ),

        "clickCount": (
            url_data.get("clickCount", 0)
        ),

        "totalAnalyticsEvents": len(
            clicks
        ),

        "firstClick": (
            clicks[0]
            if clicks
            else None
        ),

        "lastClick": (
            clicks[-1]
            if clicks
            else None
        ),

        "clicks": clicks,
    }


# ============================================================
# QR Code
# ============================================================

@app.get(
    "/qr/{short_code}"
)
def generate_qr_code(
    short_code: str,
):

    url_data = repository.get_url(
        short_code
    )

    if not url_data:

        raise HTTPException(
            status_code=404,
            detail="Short URL not found",
        )

    # --------------------------------------------------------
    # Check expiration
    # --------------------------------------------------------

    expires_at = url_data.get(
        "expiresAt"
    )

    if expires_at:

        try:

            expiration_datetime = (
                datetime.fromisoformat(
                    expires_at
                )
            )

            if expiration_datetime.tzinfo is None:

                expiration_datetime = (
                    expiration_datetime.replace(
                        tzinfo=timezone.utc
                    )
                )

            now = datetime.now(
                timezone.utc
            )

            if expiration_datetime <= now:

                raise HTTPException(
                    status_code=410,
                    detail=(
                        "Short URL has expired"
                    ),
                )

        except ValueError:

            pass

    # --------------------------------------------------------
    # Build QR destination
    # --------------------------------------------------------

    base_url = (
        "http://100.53.178.159:8000"
    )

    redirect_url = (
        f"{base_url}/{short_code}"
    )

    # --------------------------------------------------------
    # Generate QR
    # --------------------------------------------------------

    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=4,
    )

    qr.add_data(
        redirect_url
    )

    qr.make(
        fit=True
    )

    image = qr.make_image(
        fill_color="black",
        back_color="white",
    )

    buffer = io.BytesIO()

    image.save(
        buffer,
        format="PNG",
    )

    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="image/png",
    )


# ============================================================
# Redirect
# ============================================================

@app.get(
    "/{short_code}"
)
def redirect_short_url(
    short_code: str,
    request: Request,
):
    """
    Redirect the user to the original URL.

    Also:
        1. Check expiration
        2. Atomically increment click count
        3. Store analytics event
    """

    url_data = repository.get_url(
        short_code
    )

    if not url_data:

        raise HTTPException(
            status_code=404,
            detail="Short URL not found",
        )

    # --------------------------------------------------------
    # Check expiration
    # --------------------------------------------------------

    expires_at = url_data.get(
        "expiresAt"
    )

    if expires_at:

        try:

            expiration_datetime = (
                datetime.fromisoformat(
                    expires_at
                )
            )

            if expiration_datetime.tzinfo is None:

                expiration_datetime = (
                    expiration_datetime.replace(
                        tzinfo=timezone.utc
                    )
                )

            now = datetime.now(
                timezone.utc
            )

            if expiration_datetime <= now:

                repository.mark_expired(
                    short_code
                )

                raise HTTPException(
                    status_code=410,
                    detail=(
                        "Short URL has expired"
                    ),
                )

        except ValueError:

            pass

    # --------------------------------------------------------
    # Increment click count
    # --------------------------------------------------------

    try:

        repository.increment_click_count(
            short_code
        )

    except Exception as error:

        print(
            "Click counter error:",
            error,
        )

    # --------------------------------------------------------
    # Record analytics event
    # --------------------------------------------------------

    try:

        user_agent = request.headers.get(
            "user-agent",
            "",
        )

        referrer = request.headers.get(
            "referer",
            "",
        )

        repository.record_click(
            short_code=short_code,
            user_agent=user_agent,
            referrer=referrer,
        )

    except Exception as error:

        print(
            "Analytics event error:",
            error,
        )

    # --------------------------------------------------------
    # Redirect
    # --------------------------------------------------------

    return RedirectResponse(
        url=url_data["originalUrl"],
        status_code=302,
    )