from datetime import datetime, timezone

from .validation_service import URLValidationService
from ..utils.short_code import generate_short_code

class URLService:
    def create_short_url(
        self,
        long_url: str,
        custom_alias: str | None = None,
        expires_at: str | None = None,
    ) -> dict:
        is_valid, error = URLValidationService.validate_url(long_url)
        if not is_valid:
            raise ValueError(error)

        short_code = custom_alias or generate_short_code()

        return {
            "shortCode": short_code,
            "originalUrl": long_url,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "expiresAt": expires_at,
            "clickCount": 0,
            "status": "ACTIVE",
        }
