from fastapi.testclient import TestClient

from backend.src import main


client = TestClient(main.app)


def test_health_and_dashboard_assets():
    assert client.get("/").json()["status"] == "running"
    assert client.get("/favicon.ico").status_code == 204
    assert client.get("/dashboard").status_code == 200
    assert client.get("/assets/app.js").status_code == 200


def test_create_short_url_returns_absolute_links(monkeypatch):
    class Repository:
        def create_url(self, **kwargs):
            return {"shortCode": "abc123", "expiresAt": None}

    monkeypatch.setattr(main, "repository", Repository())
    monkeypatch.setattr(main.rate_limiter, "is_allowed", lambda _ip: True)
    monkeypatch.setattr(main.settings, "BASE_URL", "https://short.example")

    response = client.post(
        "/urls",
        json={"url": "https://example.com"},
    )

    assert response.status_code == 200
    assert response.json()["shortUrl"] == "https://short.example/abc123"
    assert response.json()["analyticsUrl"] == (
        "https://short.example/analytics/abc123"
    )


def test_analytics_clicks_are_chronological(monkeypatch):
    class Repository:
        def get_url(self, _short_code):
            return {"originalUrl": "https://example.com", "clickCount": 2}

        def get_click_events(self, _short_code):
            return [
                {"timestamp": "2026-02-02T00:00:00+00:00"},
                {"timestamp": "2026-02-01T00:00:00+00:00"},
            ]

    monkeypatch.setattr(main, "repository", Repository())

    response = client.get("/analytics/abc123")

    assert response.status_code == 200
    assert response.json()["firstClick"]["timestamp"].startswith("2026-02-01")
    assert response.json()["lastClick"]["timestamp"].startswith("2026-02-02")