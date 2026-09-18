from datetime import datetime, timezone

from services.validation_service import validate_url
from utils.short_code import generate_short_code

class URLService:
    def create_short_url(
        self,
        long_url: str,
        custom_alias: str | None = None,
        expires_at: str | None = None,
    ) -> dict:
        if not validate_url(long_url):
            raise ValueError("Invalid URL")

        short_code = custom_alias or generate_short_code()

        return {
            "shortCode": short_code,
            "longUrl": long_url,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "expiresAt": expires_at,
            "clickCount": 0,
            "status": "ACTIVE",
        }
