# SmartURL

A GitHub-ready URL shortener built with Python, FastAPI, AWS DynamoDB, QR codes, analytics, rate limiting, URL validation, Docker, tests, and a web dashboard.

Features: URL shortening, custom aliases, expiration, atomic click counting, click-event analytics, QR generation, basic rate limiting, lightweight URL validation, dashboard, tests and Docker.

DynamoDB:
- SmartURLUrls: partition key `shortCode` (String)
- SmartURLClicks: partition key `shortCode` (String), sort key `clickId` (String)

Run on your existing EC2:
```bash
cd ~/smarturl
source venv/bin/activate
pip install -r backend/requirements.txt
export AWS_REGION=us-east-1
export URL_TABLE_NAME=SmartURLUrls
export CLICK_TABLE_NAME=SmartURLClicks
export BASE_URL=http://YOUR_EC2_PUBLIC_IP:8000
uvicorn backend.src.main:app --host 0.0.0.0 --port 8000
```

Open `/docs` for Swagger and `/dashboard` for the web UI.

Never commit `.env` or AWS credentials. Use the EC2 IAM role.
