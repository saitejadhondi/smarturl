from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

from repositories.url_repository import URLRepository
from services.url_service import URLService

app = FastAPI(
    title="SmartURL API",
    description="Intelligent URL Shortener and Analytics Platform",
    version="1.0.0",
)

repository = URLRepository()
service = URLService()

class CreateURLRequest(BaseModel):
    url: HttpUrl
    custom_alias: str | None = None
    expires_at: str | None = None

@app.get("/")
def health_check():
    return {
        "application": "SmartURL",
        "status": "running",
        "version": "1.0.0",
    }

@app.post("/urls")
def create_url(request: CreateURLRequest):
    try:
        url_data = service.create_short_url(
            long_url=str(request.url),
            custom_alias=request.custom_alias,
            expires_at=request.expires_at,
        )
        repository.save(url_data)
        return {
            "message": "Short URL created successfully",
            "data": url_data,
        }
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

@app.get("/urls/{short_code}")
def get_url(short_code: str):
    url_data = repository.find_by_short_code(short_code)
    if not url_data:
        raise HTTPException(status_code=404, detail="Short URL not found")
    return {"data": url_data}
