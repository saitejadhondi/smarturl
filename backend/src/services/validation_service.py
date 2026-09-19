from urllib.parse import urlparse


class URLValidationService:
    """Validate destination URLs and custom aliases."""

    ALLOWED_SCHEMES = {
        "http",
        "https",
    }

    BLOCKED_HOSTS = {
        "localhost",
        "localhost.localdomain",
    }

    RESERVED_ALIASES = {
        "admin",
        "api",
        "dashboard",
        "docs",
        "favicon",
        "health",
        "analytics",
        "qr",
        "urls",
        "static",
    }

    @staticmethod
    def validate_url(
        url: str,
    ) -> tuple[bool, str]:
        """
        Validate a destination URL.

        Returns:
            (True, "") when valid.
            (False, error_message) when invalid.
        """

        if not url:

            return (
                False,
                "URL is required",
            )

        url = url.strip()

        if len(url) > 2048:

            return (
                False,
                "URL cannot exceed 2048 characters",
            )

        try:

            parsed = urlparse(url)

        except Exception:

            return (
                False,
                "Invalid URL",
            )

        scheme = (
            parsed.scheme.lower()
        )

        if scheme not in (
            URLValidationService.ALLOWED_SCHEMES
        ):

            return (
                False,
                "Only HTTP and HTTPS URLs are allowed",
            )

        if not parsed.netloc:

            return (
                False,
                "URL must contain a valid hostname",
            )

        hostname = parsed.hostname

        if not hostname:

            return (
                False,
                "URL must contain a valid hostname",
            )

        hostname = hostname.lower()

        # -------------------------------------------------
        # Block localhost
        # -------------------------------------------------

        if hostname in (
            URLValidationService.BLOCKED_HOSTS
        ):

            return (
                False,
                "Localhost URLs are not allowed",
            )

        # -------------------------------------------------
        # Block IPv4 loopback
        # -------------------------------------------------

        if hostname.startswith("127."):

            return (
                False,
                "Loopback URLs are not allowed",
            )

        # -------------------------------------------------
        # Block 10.0.0.0/8
        # -------------------------------------------------

        if hostname.startswith("10."):

            return (
                False,
                "Private network URLs are not allowed",
            )

        # -------------------------------------------------
        # Block 192.168.0.0/16
        # -------------------------------------------------

        if hostname.startswith(
            "192.168."
        ):

            return (
                False,
                "Private network URLs are not allowed",
            )

        # -------------------------------------------------
        # Block 172.16.0.0/12
        # -------------------------------------------------

        if hostname.startswith("172."):

            parts = hostname.split(".")

            if len(parts) == 4:

                try:

                    second_octet = int(
                        parts[1]
                    )

                    if 16 <= second_octet <= 31:

                        return (
                            False,
                            "Private network URLs are not allowed",
                        )

                except ValueError:

                    pass

        return True, ""

    @staticmethod
    def validate_alias(
        alias: str,
    ) -> tuple[bool, str]:
        """
        Validate a custom short URL alias.
        """

        if not alias:

            return (
                False,
                "Alias is required",
            )

        alias = alias.strip()

        if len(alias) < 3:

            return (
                False,
                "Alias must contain at least 3 characters",
            )

        if len(alias) > 50:

            return (
                False,
                "Alias cannot exceed 50 characters",
            )

        # -------------------------------------------------
        # Reserved routes
        # -------------------------------------------------

        if alias.lower() in (
            URLValidationService.RESERVED_ALIASES
        ):

            return (
                False,
                f"'{alias}' is a reserved alias",
            )

        # -------------------------------------------------
        # Allowed characters
        # -------------------------------------------------

        allowed_characters = (
            "abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789-_"
        )

        for character in alias:

            if character not in allowed_characters:

                return (
                    False,
                    (
                        "Alias can contain only "
                        "letters, numbers, hyphens "
                        "and underscores"
                    ),
                )

        # -------------------------------------------------
        # First character
        # -------------------------------------------------

        if not alias[0].isalnum():

            return (
                False,
                "Alias must start with a letter or number",
            )

        return True, ""