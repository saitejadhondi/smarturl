import secrets
import string

CHARACTERS = string.ascii_letters + string.digits

def generate_short_code(length: int = 6) -> str:
    """Generate a cryptographically secure short URL code."""
    return "".join(secrets.choice(CHARACTERS) for _ in range(length))
