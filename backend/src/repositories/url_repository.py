import uuid
from datetime import datetime, timezone
import boto3
from boto3.dynamodb.conditions import Key
from src.config import settings

class URLRepository:
    def __init__(self):
        db = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
        self.table = db.Table(settings.URL_TABLE_NAME)
        self.click_table = db.Table(settings.CLICK_TABLE_NAME)

    def save(self, data):
        self.table.put_item(Item=data)
        return data

    def find_by_short_code(self, short_code):
        return self.table.get_item(Key={"shortCode": short_code}).get("Item")

    def increment_click_count(self, short_code):
        return self.table.update_item(
            Key={"shortCode": short_code},
            UpdateExpression="SET clickCount = if_not_exists(clickCount, :zero) + :one",
            ExpressionAttributeValues={":zero": 0, ":one": 1},
            ReturnValues="ALL_NEW",
        ).get("Attributes", {})

    def mark_expired(self, short_code):
        return self.table.update_item(
            Key={"shortCode": short_code},
            UpdateExpression="SET #status = :expired",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":expired": "EXPIRED"},
            ReturnValues="ALL_NEW",
        ).get("Attributes", {})

    def record_click(self, short_code, user_agent="", referrer=""):
        item = {
            "shortCode": short_code,
            "clickId": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "userAgent": user_agent or "unknown",
            "referrer": referrer or "direct",
        }
        self.click_table.put_item(Item=item)
        return item

    def get_clicks(self, short_code):
        items = []
        response = self.click_table.query(
            KeyConditionExpression=Key("shortCode").eq(short_code)
        )
        items.extend(response.get("Items", []))
        while "LastEvaluatedKey" in response:
            response = self.click_table.query(
                KeyConditionExpression=Key("shortCode").eq(short_code),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))
        return items
