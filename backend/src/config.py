import os

class Settings:
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    URL_TABLE_NAME = os.getenv("URL_TABLE_NAME", "SmartURLUrls")
    CLICK_TABLE_NAME = os.getenv("CLICK_TABLE_NAME", "SmartURLClicks")
    BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "30"))
    RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

settings = Settings()
