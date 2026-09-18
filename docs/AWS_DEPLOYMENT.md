# AWS Deployment

Use the EC2 IAM role instead of storing AWS access keys.

DynamoDB application permissions should be limited to the two SmartURL tables and the actions the app needs: GetItem, PutItem, UpdateItem, Query and DeleteItem.

Environment:
```bash
export AWS_REGION=us-east-1
export URL_TABLE_NAME=SmartURLUrls
export CLICK_TABLE_NAME=SmartURLClicks
export BASE_URL=http://YOUR_EC2_PUBLIC_IP:8000
```

For public production use, add HTTPS and a domain/reverse proxy. Monitor AWS usage and billing.
