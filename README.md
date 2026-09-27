# SmartURL

SmartURL is an AWS-powered URL shortener built with Python, FastAPI, DynamoDB, Boto3, and a lightweight web dashboard.

## Features

- Random short URL generation
- Custom aliases
- URL expiration
- URL and alias validation
- Click counting
- Click analytics
- User-Agent and referrer tracking
- QR code generation
- API rate limiting
- DynamoDB persistence
- Swagger/OpenAPI documentation
- Web dashboard

## Architecture

```text
Browser
   |
   v
FastAPI / Uvicorn
   |
   +-- URL validation
   +-- Alias validation
   +-- Rate limiter
   +-- QR generation
   |
   v
URL Repository
   |
   +--> DynamoDB: SmartURLUrls
   |
   +--> DynamoDB: SmartURLClicks
```

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python |
| API | FastAPI |
| Server | Uvicorn |
| Database | Amazon DynamoDB |
| AWS SDK | Boto3 |
| QR | qrcode |
| Frontend | HTML, CSS, JavaScript |
| API Docs | Swagger / OpenAPI |
| Deployment | AWS EC2 |
| Version Control | Git / GitHub |

## Project Structure

```text
smarturl/
├── backend/
│   ├── requirements.txt
│   ├── src/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   └── url_repository.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── rate_limiter.py
│   │   │   ├── validation_service.py
│   │   │   └── url_service.py
│   │   └── utils/
│   │       └── security.py
│   └── tests/
├── frontend/
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   └── static/
│       └── style.css
├── .gitignore
└── README.md
```

## Prerequisites

Install:

- Python 3.10+
- Git
- AWS account
- AWS CLI
- An AWS DynamoDB setup

Check versions:

```bash
python3 --version
git --version
```

## AWS Requirements

SmartURL currently uses two DynamoDB tables.

### SmartURLUrls

Partition key:

```text
shortCode
```

Type:

```text
String
```

### SmartURLClicks

Partition key:

```text
shortCode
```

Type:

```text
String
```

Sort key:

```text
clickId
```

Type:

```text
String
```

PAY_PER_REQUEST billing is suitable for this project.

## AWS Authentication

### Local development

Configure AWS credentials using the AWS CLI:

```bash
aws configure
```

Then verify:

```bash
aws sts get-caller-identity
```

Never commit AWS access keys or secret keys to GitHub.

### EC2

For EC2, prefer an IAM role attached to the instance instead of storing long-lived AWS credentials on the server.

The role should have only the DynamoDB permissions required by the application.

## Configuration

The application expects configuration such as:

```text
AWS_REGION=us-east-1
URL_TABLE_NAME=SmartURLUrls
CLICK_TABLE_NAME=SmartURLClicks
```

Use the configuration mechanism implemented by `backend/src/config.py`.

If using a `.env` file, create it locally:

```env
AWS_REGION=us-east-1
URL_TABLE_NAME=SmartURLUrls
CLICK_TABLE_NAME=SmartURLClicks
```

Do not commit `.env`.

Add this to `.gitignore`:

```text
.env
.env.*
!.env.example
```

## Run Locally

Clone the repository:

```bash
git clone <YOUR-GITHUB-REPOSITORY>
cd smarturl
```

Create a virtual environment:

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

### Windows PowerShell

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
cd backend
pip install -r requirements.txt
```

Start the API:

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000/dashboard
```

Swagger:

```text
http://localhost:8000/docs
```

ReDoc:

```text
http://localhost:8000/redoc
```

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Health/status |
| GET | `/dashboard` | Web dashboard |
| POST | `/urls` | Create short URL |
| GET | `/urls/{short_code}` | URL information |
| GET | `/analytics/{short_code}` | Analytics |
| GET | `/qr/{short_code}` | QR code |
| GET | `/{short_code}` | Redirect |
| GET | `/docs` | Swagger |
| GET | `/redoc` | ReDoc |

## Create a Short URL

Request:

```http
POST /urls
```

Example:

```json
{
  "url": "https://www.example.com"
}
```

Example response:

```json
{
  "message": "Short URL created successfully",
  "shortCode": "aB72xQ",
  "originalUrl": "https://www.example.com/",
  "shortUrl": "/aB72xQ",
  "analyticsUrl": "/analytics/aB72xQ",
  "qrUrl": "/qr/aB72xQ",
  "expiresAt": null
}
```

## Custom Alias

```json
{
  "url": "https://www.example.com",
  "custom_alias": "my-site"
}
```

The short URL becomes:

```text
http://localhost:8000/my-site
```

Aliases support letters, numbers, hyphens, and underscores. Reserved application routes and duplicate aliases are rejected.

## Expiration

Example:

```json
{
  "url": "https://www.example.com",
  "custom_alias": "temporary",
  "expires_at": "2027-01-01T00:00:00Z"
}
```

An expired short URL returns:

```text
410 Gone
```

and is marked `EXPIRED`.

## Redirect and Analytics

Opening:

```text
http://localhost:8000/aB72xQ
```

causes SmartURL to:

1. Find the short code.
2. Check expiration.
3. Increment the click counter.
4. Record the click event.
5. Redirect to the destination URL.

Analytics:

```text
GET /analytics/aB72xQ
```

Tracked information includes:

- Click ID
- Timestamp
- User-Agent
- Referrer
- Total click count

## QR Codes

Open:

```text
http://localhost:8000/qr/aB72xQ
```

The endpoint returns a PNG QR code pointing to the short URL.

## Rate Limiting

URL creation is currently protected by an in-memory rate limiter:

```text
10 requests / 60 seconds / client IP
```

Exceeding the limit returns:

```text
429 Too Many Requests
```

The in-memory implementation is intended for the current single-instance deployment. A multi-instance production deployment should use a shared store such as Redis for distributed rate limiting.

## URL Validation

Only HTTP and HTTPS destinations are accepted.

The current validation layer rejects invalid URLs, localhost destinations, loopback addresses, and common private IPv4 ranges.

This is an initial security layer and should not be treated as complete SSRF protection for a hardened internet-facing service.

## Run Tests

If tests are present:

```bash
cd backend
pytest -v
```

## Deploy to AWS EC2

Clone:

```bash
git clone <YOUR-GITHUB-REPOSITORY>
cd smarturl
```

Create the environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install:

```bash
cd backend
pip install -r requirements.txt
```

Configure the EC2 IAM role with the required DynamoDB permissions.

Start:

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Then:

```text
http://<EC2-PUBLIC-IP>:8000/dashboard
```

Swagger:

```text
http://<EC2-PUBLIC-IP>:8000/docs
```

For a persistent production deployment, use a process manager such as systemd and put Nginx in front of Uvicorn.

## Production Architecture

```text
Internet
   |
   v
Domain / HTTPS
   |
   v
Nginx
   |
   v
Uvicorn
   |
   v
FastAPI
   |
   +--> DynamoDB: SmartURLUrls
   |
   +--> DynamoDB: SmartURLClicks
```

Recommended production improvements:

- Nginx reverse proxy
- HTTPS/SSL
- Custom domain
- systemd process management
- Structured logging
- CloudWatch monitoring
- Shared rate limiting
- Stronger SSRF protection
- Automated tests
- CI/CD
- Secrets management
- Monitoring and alerting

## Security

Never commit:

```text
AWS access keys
AWS secret keys
.env
SSH private keys
passwords
API tokens
```

Prefer:

- EC2 IAM roles
- Least-privilege IAM policies
- Environment variables
- AWS Secrets Manager where appropriate

## GitHub Workflow

Recommended workflow:

```text
VS Code
   |
   v
Edit
   |
   v
Test
   |
   v
git add
   |
   v
git commit
   |
   v
git push
   |
   v
GitHub
   |
   v
EC2: git pull
   |
   v
Restart application
```

Example:

```bash
git status
git add .
git commit -m "Update SmartURL"
git push origin main
```

On EC2:

```bash
cd ~/smarturl
git pull origin main
```

## Troubleshooting

### Port 8000 is already in use

```bash
sudo lsof -i :8000
```

Stop the old process if necessary.

### DynamoDB access fails

```bash
aws sts get-caller-identity
```

Verify the AWS identity, region, table names, and IAM permissions.

### Dashboard returns 404

Verify:

```text
smarturl/frontend/index.html
```

exists.

### Short URL returns 404

Verify the short code exists in `SmartURLUrls` and that the partition key is:

```text
shortCode
```

## Future Improvements

- Advanced analytics dashboard
- Clicks-over-time charts
- Device/browser analytics
- Geographic analytics
- User authentication
- User-specific URL management
- Admin dashboard
- Redis-based distributed rate limiting
- Custom domain
- HTTPS
- CI/CD
- CloudWatch monitoring
- Stronger SSRF protection
- Automated integration tests

## Author

**Saiteja Dhondi**

Technologies:

```text
Python
FastAPI
AWS
DynamoDB
Boto3
HTML
CSS
JavaScript
Git
GitHub
```

## License

Choose a license for the repository. For example, MIT can be used if you want others to reuse and modify the project under the MIT License terms.

## Quick Start

```bash
git clone <YOUR-GITHUB-REPOSITORY>
cd smarturl
python3 -m venv venv
source venv/bin/activate
cd backend
pip install -r requirements.txt
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Then open:

```text
http://localhost:8000/dashboard
```

API documentation:

```text
http://localhost:8000/docs
```
