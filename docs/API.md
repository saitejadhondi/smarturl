# API

GET `/` — health check

POST `/urls` — create a short URL

GET `/urls/{short_code}` — URL details

GET `/{short_code}` — redirect and record a click

GET `/analytics/{short_code}` — click analytics, browser/device/referrer summaries

GET `/qr/{short_code}` — PNG QR code

GET `/dashboard` — web dashboard
