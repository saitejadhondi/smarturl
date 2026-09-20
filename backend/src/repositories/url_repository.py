import secrets
import string
import uuid

from datetime import datetime, timezone

import boto3

from boto3.dynamodb.conditions import Key

from src.config import settings


class URLRepository:
    """
    Repository layer for SmartURL.

    Handles:
        - URL storage
        - URL lookup
        - click counter
        - click analytics
        - expiration status
    """

    def __init__(self):

        db = boto3.resource(
            "dynamodb",
            region_name=settings.AWS_REGION,
        )

        self.table = db.Table(
            settings.URL_TABLE_NAME
        )

        self.click_table = db.Table(
            settings.CLICK_TABLE_NAME
        )

    # ========================================================
    # Generate Short Code
    # ========================================================

    def generate_short_code(
        self,
        length: int = 6,
    ) -> str:
        """
        Generate a random URL-safe short code.
        """

        characters = (
            string.ascii_letters
            + string.digits
        )

        return "".join(
            secrets.choice(characters)
            for _ in range(length)
        )

    # ========================================================
    # Save URL
    # ========================================================

    def save(self, data):

        self.table.put_item(
            Item=data
        )

        return data

    # ========================================================
    # Create URL
    # ========================================================

    def create_url(
        self,
        original_url: str,
        custom_alias=None,
        expires_at=None,
    ):
        """
        Create a new shortened URL.

        If custom_alias is provided,
        it is used as the short code.

        Otherwise a random short code
        is generated.
        """

        # ----------------------------------------------------
        # Custom alias
        # ----------------------------------------------------

        if custom_alias:

            short_code = custom_alias

            existing = (
                self.find_by_short_code(
                    short_code
                )
            )

            if existing:

                raise ValueError(
                    "Custom alias is already in use"
                )

        # ----------------------------------------------------
        # Random short code
        # ----------------------------------------------------

        else:

            for _ in range(10):

                short_code = (
                    self.generate_short_code()
                )

                existing = (
                    self.find_by_short_code(
                        short_code
                    )
                )

                if not existing:
                    break

            else:

                raise ValueError(
                    "Unable to generate a unique short code"
                )

        # ----------------------------------------------------
        # Timestamp
        # ----------------------------------------------------

        created_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        # ----------------------------------------------------
        # Normalize expiration
        # ----------------------------------------------------

        expiration_value = None

        if expires_at:

            if isinstance(
                expires_at,
                datetime,
            ):

                if expires_at.tzinfo is None:

                    expires_at = (
                        expires_at.replace(
                            tzinfo=timezone.utc
                        )
                    )

                expiration_value = (
                    expires_at.isoformat()
                )

            else:

                expiration_value = str(
                    expires_at
                )

        # ----------------------------------------------------
        # DynamoDB item
        # ----------------------------------------------------

        item = {
            "shortCode": short_code,

            "originalUrl": original_url,

            "createdAt": created_at,

            "clickCount": 0,

            "status": "ACTIVE",
        }

        if expiration_value:

            item["expiresAt"] = (
                expiration_value
            )

        # ----------------------------------------------------
        # Save
        # ----------------------------------------------------

        return self.save(item)

    # ========================================================
    # Find By Short Code
    # ========================================================

    def find_by_short_code(
        self,
        short_code: str,
    ):

        response = self.table.get_item(
            Key={
                "shortCode": short_code
            }
        )

        return response.get(
            "Item"
        )

    # ========================================================
    # Get URL
    # ========================================================

    def get_url(
        self,
        short_code: str,
    ):

        return self.find_by_short_code(
            short_code
        )

    # ========================================================
    # Increment Click Count
    # ========================================================

    def increment_click_count(
        self,
        short_code: str,
    ):

        response = self.table.update_item(

            Key={
                "shortCode": short_code
            },

            UpdateExpression=(
                "SET clickCount = "
                "if_not_exists(clickCount, :zero) "
                "+ :one"
            ),

            ExpressionAttributeValues={
                ":zero": 0,
                ":one": 1,
            },

            ReturnValues="ALL_NEW",
        )

        return response.get(
            "Attributes",
            {},
        )

    # ========================================================
    # Mark Expired
    # ========================================================

    def mark_expired(
        self,
        short_code: str,
    ):

        response = self.table.update_item(

            Key={
                "shortCode": short_code
            },

            UpdateExpression=(
                "SET #status = :expired"
            ),

            ExpressionAttributeNames={
                "#status": "status"
            },

            ExpressionAttributeValues={
                ":expired": "EXPIRED"
            },

            ReturnValues="ALL_NEW",
        )

        return response.get(
            "Attributes",
            {},
        )

    # ========================================================
    # Record Click
    # ========================================================

    def record_click(
        self,
        short_code: str,
        user_agent="",
        referrer="",
    ):

        item = {

            "shortCode": short_code,

            "clickId": str(
                uuid.uuid4()
            ),

            "timestamp": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),

            "userAgent": (
                user_agent
                or "unknown"
            ),

            "referrer": (
                referrer
                or "direct"
            ),
        }

        self.click_table.put_item(
            Item=item
        )

        return item

    # ========================================================
    # Get Clicks
    # ========================================================

    def get_clicks(
        self,
        short_code: str,
    ):

        items = []

        response = self.click_table.query(

            KeyConditionExpression=(
                Key("shortCode").eq(
                    short_code
                )
            )
        )

        items.extend(
            response.get(
                "Items",
                []
            )
        )

        while "LastEvaluatedKey" in response:

            response = self.click_table.query(

                KeyConditionExpression=(
                    Key("shortCode").eq(
                        short_code
                    )
                ),

                ExclusiveStartKey=(
                    response[
                        "LastEvaluatedKey"
                    ]
                ),
            )

            items.extend(
                response.get(
                    "Items",
                    []
                )
            )

        return items

    # ========================================================
    # Get Click Events
    # ========================================================

    def get_click_events(
        self,
        short_code: str,
    ):

        return self.get_clicks(
            short_code
        )