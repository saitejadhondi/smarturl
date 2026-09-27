# SmartURL --- Complete Setup & Deployment Guide

SmartURL is a Python/FastAPI URL shortener using AWS DynamoDB for URL
data and click analytics. This guide is intentionally step-by-step so a
new developer can start from an AWS account and GitHub repository and
run the application.

## 1. What you need

Install or have access to:

-   Git
-   Python 3.10+
-   pip
-   AWS account
-   AWS Console access
-   SSH client
-   An EC2 key pair
-   Permission to create IAM roles/policies, DynamoDB tables, EC2
    instances, and security groups

The example region used below is `us-east-1`. You can use another
region, but use the same region consistently for DynamoDB and EC2.

------------------------------------------------------------------------

## 2. Application architecture

``` text
Internet / Browser
        |
        v
     Nginx                  (production)
        |
        v
   Uvicorn :8000
        |
        v
     FastAPI
        |
   +----+-------------------+
   |                        |
   v                        v
URL/alias validation    Rate limiter
   |
   v
URL Repository
   |
   +-----------------------------+
   |                             |
   v                             v
SmartURLUrls              SmartURLClicks
DynamoDB                  DynamoDB
```

The application provides:

-   Random short codes
-   Custom aliases
-   URL expiration
-   URL validation
-   Alias validation
-   Click counter
-   Click events
-   User-Agent/referrer tracking
-   Analytics
-   QR codes
-   Rate limiting
-   Swagger/OpenAPI
-   Web dashboard

------------------------------------------------------------------------

# 3. Clone the GitHub repository

Replace `<YOUR-GITHUB-REPOSITORY>` with the actual repository URL.

``` bash
git clone <YOUR-GITHUB-REPOSITORY>
cd smarturl
```

Expected structure:

``` text
smarturl/
├── backend/
├── frontend/
├── README.md
└── .gitignore
```

Never commit AWS credentials, `.env` files containing secrets, SSH
private keys, passwords, or tokens.

------------------------------------------------------------------------

# 4. Create the DynamoDB tables

SmartURL requires exactly two tables by default:

``` text
SmartURLUrls
SmartURLClicks
```

Open:

``` text
AWS Console
  -> DynamoDB
  -> Tables
  -> Create table
```

Use the AWS region selected for your project.

## 4.1 Create SmartURLUrls

Enter:

``` text
Table name: SmartURLUrls
Partition key: shortCode
Type: String
```

Do not add a sort key.

For capacity, choose:

``` text
On-demand / PAY_PER_REQUEST
```

Create the table and wait until its status is:

``` text
ACTIVE
```

The application can store ordinary attributes such as:

``` text
shortCode
originalUrl
createdAt
clickCount
status
expiresAt
```

Only `shortCode` is a key and therefore must be defined during table
creation.

## 4.2 Create SmartURLClicks

Create another table:

``` text
Table name: SmartURLClicks
Partition key: shortCode
Type: String
Sort key: clickId
Type: String
Capacity: On-demand / PAY_PER_REQUEST
```

Wait for:

``` text
ACTIVE
```

The application stores:

``` text
shortCode
clickId
timestamp
userAgent
referrer
```

## 4.3 Verify

In DynamoDB -\> Tables, you should see:

``` text
SmartURLUrls
SmartURLClicks
```

------------------------------------------------------------------------

# 5. Create the IAM policy

The EC2 application needs DynamoDB access. Use a least-privilege policy
instead of giving the server AdministratorAccess.

Open:

``` text
AWS Console
  -> IAM
  -> Policies
  -> Create policy
  -> JSON
```

First find your 12-digit AWS account ID from the AWS account menu.

Paste this policy and replace `YOUR_AWS_ACCOUNT_ID`.

If using another region, replace `us-east-1`.

``` json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SmartURLDynamoDBAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query",
        "dynamodb:DescribeTable"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:YOUR_AWS_ACCOUNT_ID:table/SmartURLUrls",
        "arn:aws:dynamodb:us-east-1:YOUR_AWS_ACCOUNT_ID:table/SmartURLClicks"
      ]
    }
  ]
}
```

Name:

``` text
SmartURL-DynamoDB-Policy
```

Description:

``` text
Least-privilege DynamoDB permissions for SmartURL.
```

Create the policy.

The application currently uses:

``` text
GetItem
PutItem
UpdateItem
Query
DescribeTable
```

It does not need unrestricted DynamoDB access.

------------------------------------------------------------------------

# 6. Create the EC2 IAM role

Do not put AWS access keys inside the Python project.

Instead, attach an IAM role to EC2.

Open:

``` text
AWS Console
  -> IAM
  -> Roles
  -> Create role
```

Choose:

``` text
Trusted entity type: AWS service
Use case: EC2
```

Choose **Next**.

Attach:

``` text
SmartURL-DynamoDB-Policy
```

Choose **Next**.

Role name:

``` text
SmartURL-EC2-Role
```

Description:

``` text
IAM role for the SmartURL application running on EC2.
```

Create the role.

Open the role afterward and verify its trust relationship allows:

``` text
ec2.amazonaws.com
```

to assume the role.

------------------------------------------------------------------------

# 7. Create the EC2 security group

Open:

``` text
AWS Console
  -> EC2
  -> Security Groups
  -> Create security group
```

Name:

``` text
SmartURL-SG
```

Description:

``` text
Security group for SmartURL EC2 server.
```

Select the VPC used by the instance.

## Inbound rules

Add:

### SSH

``` text
Type: SSH
Port: 22
Source: My IP
```

Use your own IP for SSH instead of `0.0.0.0/0` whenever possible.

### HTTP

``` text
Type: HTTP
Port: 80
Source: 0.0.0.0/0
```

### HTTPS

``` text
Type: HTTPS
Port: 443
Source: 0.0.0.0/0
```

### Port 8000 --- temporary testing only

``` text
Type: Custom TCP
Port: 8000
Source: 0.0.0.0/0
```

Port 8000 is useful while testing:

``` text
http://EC2-PUBLIC-IP:8000
```

After Nginx is configured, remove public port 8000 and expose only
80/443.

------------------------------------------------------------------------

# 8. Launch the EC2 instance

Open:

``` text
AWS Console
  -> EC2
  -> Instances
  -> Launch instance
```

## Name

``` text
SmartURL-Server
```

## AMI

Choose an Ubuntu Server LTS image.

## Instance type

Choose a small general-purpose instance suitable for your development
workload. Check current AWS pricing and eligibility before launching
because AWS pricing/free-tier rules can change.

## Key pair

Create or select a key pair.

Example:

``` text
SmartURL-Key
```

Download the `.pem` file.

Never upload the private key to GitHub.

## Network

Select your VPC/subnet.

Security group:

``` text
SmartURL-SG
```

## IAM role

In **Advanced details**, find **IAM instance profile** and select:

``` text
SmartURL-EC2-Role
```

Launch the instance.

Wait for:

``` text
Instance state: Running
Status checks: 2/2
```

------------------------------------------------------------------------

# 9. Connect to EC2

Copy the instance's current public IPv4 address.

Linux/macOS:

``` bash
chmod 400 SmartURL-Key.pem
ssh -i SmartURL-Key.pem ubuntu@<EC2-PUBLIC-IP>
```

Windows PowerShell:

``` powershell
ssh -i .\SmartURL-Key.pem ubuntu@<EC2-PUBLIC-IP>
```

Ubuntu normally uses:

``` text
ubuntu
```

as the SSH username.

------------------------------------------------------------------------

# 10. Install server dependencies

On EC2:

``` bash
sudo apt update
```

Install:

``` bash
sudo apt install -y python3 python3-pip python3-venv git
```

Verify:

``` bash
python3 --version
git --version
```

------------------------------------------------------------------------

# 11. Clone SmartURL on EC2

``` bash
cd ~
git clone <YOUR-GITHUB-REPOSITORY>
cd smarturl
```

Check:

``` bash
ls
```

You should see:

``` text
backend
frontend
README.md
```

------------------------------------------------------------------------

# 12. Create the Python virtual environment

This project uses the environment at the project root:

``` text
smarturl/
├── venv/
├── backend/
└── frontend/
```

Create it:

``` bash
cd ~/smarturl
python3 -m venv venv
```

Activate it:

``` bash
source venv/bin/activate
```

Verify:

``` bash
which python
```

Expected:

``` text
/home/ubuntu/smarturl/venv/bin/python
```

If you are already inside `~/smarturl/backend`, activate it with:

``` bash
source ../venv/bin/activate
```

Do not use:

``` bash
source backend/venv/bin/activate
```

from inside the backend directory.

------------------------------------------------------------------------

# 13. Configure SmartURL

Go to:

``` bash
cd ~/smarturl/backend
```

Inspect:

``` bash
cat src/config.py
```

The configuration should provide the values used by the repository:

``` text
AWS_REGION
URL_TABLE_NAME
CLICK_TABLE_NAME
```

For this example:

``` text
AWS_REGION=us-east-1
URL_TABLE_NAME=SmartURLUrls
CLICK_TABLE_NAME=SmartURLClicks
```

If the project's `config.py` uses a `.env` file, create the required
file according to that implementation.

Example:

``` env
AWS_REGION=us-east-1
URL_TABLE_NAME=SmartURLUrls
CLICK_TABLE_NAME=SmartURLClicks
```

Do not commit the real `.env`.

A safe `.env.example` can contain placeholder values.

------------------------------------------------------------------------

# 14. Verify IAM access from EC2

Install AWS CLI if necessary:

``` bash
sudo apt install -y awscli
```

Run:

``` bash
aws sts get-caller-identity
```

The command should succeed without:

``` bash
aws configure
```

when the EC2 IAM role is correctly attached.

Verify DynamoDB:

``` bash
aws dynamodb list-tables --region us-east-1
```

Expected tables:

``` text
SmartURLClicks
SmartURLUrls
```

If you receive `AccessDenied`, check:

``` text
EC2 instance
 -> IAM instance profile
 -> SmartURL-EC2-Role
 -> SmartURL-DynamoDB-Policy
 -> DynamoDB table ARNs
```

------------------------------------------------------------------------

# 15. Install Python dependencies

From:

``` text
~/smarturl/backend
```

run:

``` bash
pip install -r requirements.txt
```

Verify:

``` bash
pip show fastapi
pip show uvicorn
pip show boto3
pip show qrcode
```

------------------------------------------------------------------------

# 16. Start SmartURL for the first test

From:

``` text
~/smarturl/backend
```

with `(venv)` active:

``` bash
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Expected:

``` text
Application startup complete.
Uvicorn running on http://0.0.0.0:8000
```

Keep the terminal open.

------------------------------------------------------------------------

# 17. Test the application

Open:

``` text
http://<EC2-PUBLIC-IP>:8000/
```

Open Swagger:

``` text
http://<EC2-PUBLIC-IP>:8000/docs
```

Open dashboard:

``` text
http://<EC2-PUBLIC-IP>:8000/dashboard
```

------------------------------------------------------------------------

# 18. Create your first short URL

Open:

``` text
http://<EC2-PUBLIC-IP>:8000/docs
```

Find:

``` text
POST /urls
```

Select:

``` text
Try it out
```

Use:

``` json
{
  "url": "https://www.google.com"
}
```

Click **Execute**.

A successful response should contain:

``` json
{
  "message": "Short URL created successfully",
  "shortCode": "xxxxxx",
  "originalUrl": "https://www.google.com/",
  "shortUrl": "/xxxxxx",
  "analyticsUrl": "/analytics/xxxxxx",
  "qrUrl": "/qr/xxxxxx",
  "expiresAt": null
}
```

------------------------------------------------------------------------

# 19. Test the redirect

If the returned code is:

``` text
aB72xQ
```

open:

``` text
http://<EC2-PUBLIC-IP>:8000/aB72xQ
```

It should redirect to the original URL.

------------------------------------------------------------------------

# 20. Test analytics

Open:

``` text
http://<EC2-PUBLIC-IP>:8000/analytics/aB72xQ
```

You should see:

``` text
shortCode
originalUrl
clickCount
totalAnalyticsEvents
firstClick
lastClick
clicks
```

------------------------------------------------------------------------

# 21. Test QR

Open:

``` text
http://<EC2-PUBLIC-IP>:8000/qr/aB72xQ
```

A PNG QR code should appear.

Scan it from a phone to verify the redirect.

------------------------------------------------------------------------

# 22. Test rate limiting

The current default is:

``` text
10 URL creation requests
per 60 seconds
per client IP
```

Use Swagger:

``` text
POST /urls
```

Send more than 10 requests within one minute.

The API should eventually return:

``` text
429 Too Many Requests
```

The in-memory limiter is appropriate for the current single-instance
deployment. A multi-instance production deployment should use a shared
limiter such as Redis.

------------------------------------------------------------------------

# 23. Make the application persistent with systemd

The manual Uvicorn command stops when its terminal/process stops.

For a persistent EC2 service, use systemd.

First stop the manually running Uvicorn process:

``` text
Ctrl+C
```

Verify the Python path:

``` bash
source ~/smarturl/venv/bin/activate
which python
```

Expected:

``` text
/home/ubuntu/smarturl/venv/bin/python
```

Create:

``` bash
sudo nano /etc/systemd/system/smarturl.service
```

Paste:

``` ini
[Unit]
Description=SmartURL FastAPI Application
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/smarturl/backend
Environment="PATH=/home/ubuntu/smarturl/venv/bin"
ExecStart=/home/ubuntu/smarturl/venv/bin/uvicorn src.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Save and exit.

Run:

``` bash
sudo systemctl daemon-reload
sudo systemctl enable smarturl
sudo systemctl start smarturl
```

Check:

``` bash
sudo systemctl status smarturl
```

You want:

``` text
Active: active (running)
```

Logs:

``` bash
sudo journalctl -u smarturl -f
```

Press `Ctrl+C` to stop viewing logs.

Now SmartURL can keep running without an SSH terminal.

------------------------------------------------------------------------

# 24. Install Nginx

For a production-style deployment:

``` bash
sudo apt update
sudo apt install -y nginx
```

Check:

``` bash
sudo systemctl status nginx
```

The final architecture will be:

``` text
Internet
   |
   v
Nginx :80/:443
   |
   v
Uvicorn 127.0.0.1:8000
   |
   v
FastAPI
```

------------------------------------------------------------------------

# 25. Configure Nginx

Create:

``` bash
sudo nano /etc/nginx/sites-available/smarturl
```

Replace `your-domain.com` with your actual domain:

``` nginx
server {
    listen 80;
    listen [::]:80;

    server_name your-domain.com www.your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;

        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable:

``` bash
sudo ln -s /etc/nginx/sites-available/smarturl /etc/nginx/sites-enabled/smarturl
```

Remove the default site:

``` bash
sudo rm -f /etc/nginx/sites-enabled/default
```

Test:

``` bash
sudo nginx -t
```

Restart:

``` bash
sudo systemctl restart nginx
```

------------------------------------------------------------------------

# 26. Add a domain

Use a domain registrar of your choice.

Create an A record pointing to the EC2 public IP or, preferably, an
Elastic IP.

Example:

``` text
Type: A
Name: smarturl
Value: <EC2-IP>
```

Then:

``` text
smarturl.yourdomain.com
```

can point to the server.

Do not hard-code a temporary EC2 public IP in application code.

------------------------------------------------------------------------

# 27. Enable HTTPS

After DNS resolves to the EC2 server:

``` bash
sudo apt install -y certbot python3-certbot-nginx
```

Run:

``` bash
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

Follow the prompts.

Then test:

``` text
https://your-domain.com
```

The final short URLs should look like:

``` text
https://your-domain.com/aB72xQ
```

instead of:

``` text
http://<EC2-IP>:8000/aB72xQ
```

------------------------------------------------------------------------

# 28. Updating the application

## On your development machine

Edit in VS Code.

Test.

Then:

``` bash
git status
git add .
git commit -m "Update SmartURL"
git push origin main
```

## On EC2

``` bash
cd ~/smarturl
git pull origin main
```

Restart:

``` bash
sudo systemctl restart smarturl
```

Check:

``` bash
sudo systemctl status smarturl
```

------------------------------------------------------------------------

# 29. Troubleshooting

## `venv/bin/activate: No such file`

Find the environment:

``` bash
find ~/smarturl -maxdepth 3 -type f -path "*/bin/activate" 2>/dev/null
```

If it shows:

``` text
/home/ubuntu/smarturl/venv/bin/activate
```

from `~/smarturl/backend` use:

``` bash
source ../venv/bin/activate
```

## `URLRepository object has no attribute create_url`

Pull the latest repository:

``` bash
cd ~/smarturl
git pull origin main
```

Then verify:

``` bash
grep -n "def create_url" backend/src/repositories/url_repository.py
```

The current repository should provide the methods expected by `main.py`.

## DynamoDB `AccessDenied`

Run:

``` bash
aws sts get-caller-identity
```

Then verify the IAM role and policy.

Check the policy contains the correct:

``` text
AWS region
AWS account ID
SmartURLUrls ARN
SmartURLClicks ARN
```

## DynamoDB `ResourceNotFoundException`

Run:

``` bash
aws dynamodb list-tables --region us-east-1
```

Verify:

``` text
SmartURLUrls
SmartURLClicks
```

## Dashboard 404

Verify:

``` bash
ls -l ~/smarturl/frontend/index.html
```

Also test locally on EC2:

``` bash
curl http://127.0.0.1:8000/dashboard
```

## Port 8000 already in use

``` bash
sudo lsof -i :8000
```

If systemd already manages SmartURL, do not start another manual Uvicorn
process.

Use:

``` bash
sudo systemctl restart smarturl
```

## Nginx 502

Check:

``` bash
sudo systemctl status smarturl
```

Then:

``` bash
curl http://127.0.0.1:8000/
```

Check Nginx:

``` bash
sudo nginx -t
```

Logs:

``` bash
sudo journalctl -u smarturl -n 100
sudo tail -n 100 /var/log/nginx/error.log
```

## SSH failure

Verify:

-   EC2 is running
-   Correct public IP
-   Correct `.pem`
-   SSH port 22 is allowed
-   SSH source is your current IP
-   Correct username: `ubuntu`

------------------------------------------------------------------------

# 30. Security checklist

Before production:

-   [ ] Never commit AWS credentials.
-   [ ] Use an EC2 IAM role.
-   [ ] Use least-privilege DynamoDB permissions.
-   [ ] Restrict SSH to trusted IPs.
-   [ ] Use HTTPS.
-   [ ] Use a domain.
-   [ ] Put Nginx in front of Uvicorn.
-   [ ] Run Uvicorn with systemd.
-   [ ] Remove public port 8000 after Nginx works.
-   [ ] Use a shared rate limiter for multiple instances.
-   [ ] Add stronger SSRF protection for untrusted destination URLs.
-   [ ] Add monitoring/logging.
-   [ ] Keep dependencies updated.
-   [ ] Review IAM permissions periodically.

------------------------------------------------------------------------

# 31. Project structure

``` text
smarturl/
├── backend/
│   ├── requirements.txt
│   ├── src/
│   │   ├── __init__.py
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

------------------------------------------------------------------------

# 32. API reference

  Method   Endpoint                    Purpose
  -------- --------------------------- ------------------
  GET      `/`                         Health/status
  GET      `/dashboard`                Dashboard
  POST     `/urls`                     Create short URL
  GET      `/urls/{short_code}`        URL information
  GET      `/analytics/{short_code}`   Analytics
  GET      `/qr/{short_code}`          QR image
  GET      `/{short_code}`             Redirect
  GET      `/docs`                     Swagger
  GET      `/redoc`                    ReDoc

Example create request:

``` json
{
  "url": "https://www.example.com",
  "custom_alias": "example"
}
```

Example expiring request:

``` json
{
  "url": "https://www.example.com",
  "custom_alias": "temporary",
  "expires_at": "2027-01-01T00:00:00Z"
}
```

------------------------------------------------------------------------

# 33. Quick reference

### Local

``` bash
git clone <YOUR-GITHUB-REPOSITORY>
cd smarturl
python3 -m venv venv
source venv/bin/activate
cd backend
pip install -r requirements.txt
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Dashboard:

``` text
http://localhost:8000/dashboard
```

Swagger:

``` text
http://localhost:8000/docs
```

### EC2

``` bash
cd ~/smarturl
source venv/bin/activate
cd backend
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Production/systemd:

``` bash
sudo systemctl restart smarturl
sudo systemctl status smarturl
```

### GitHub -\> EC2 deployment

``` bash
git add .
git commit -m "Update SmartURL"
git push origin main
```

Then EC2:

``` bash
cd ~/smarturl
git pull origin main
sudo systemctl restart smarturl
```

------------------------------------------------------------------------

# 34. AWS official documentation

For the current AWS console workflow, see the official AWS
documentation:

-   IAM role creation:
    https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create.html
-   IAM roles for EC2:
    https://docs.aws.amazon.com/sdkref/latest/guide/access-iam-roles-for-ec2.html
-   Attach an IAM role to EC2:
    https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/attach-iam-role.html
-   DynamoDB table creation:
    https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/getting-started-step-1.html
-   EC2 security groups:
    https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/creating-security-group.html
-   EC2 launch wizard:
    https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-launch-instance-wizard.html

------------------------------------------------------------------------

# 35. Future improvements

-   Make `/` the main SmartURL dashboard.
-   Nginx + HTTPS + custom domain.
-   Better analytics charts.
-   Clicks-over-time visualization.
-   Device/browser analytics.
-   Geographic analytics.
-   Authentication.
-   User-specific URL management.
-   Admin dashboard.
-   Redis distributed rate limiting.
-   Stronger SSRF protection.
-   Automated tests.
-   GitHub Actions CI/CD.
-   CloudWatch monitoring.
-   Application metrics and alerting.

------------------------------------------------------------------------

# Author

**Saiteja Dhondi**

SmartURL demonstrates:

``` text
Python
FastAPI
REST APIs
AWS EC2
AWS IAM
AWS DynamoDB
Boto3
URL Shortening
Analytics
QR Codes
Rate Limiting
Linux
Git
GitHub
Nginx
Production Deployment
```
