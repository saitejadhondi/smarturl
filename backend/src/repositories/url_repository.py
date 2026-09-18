class URLRepository:
    """Temporary in-memory repository. Replaced by DynamoDB in the AWS stage."""

    def __init__(self):
        self.urls = {}

    def save(self, url_data: dict) -> dict:
        short_code = url_data["shortCode"]
        self.urls[short_code] = url_data
        return url_data

    def find_by_short_code(self, short_code: str):
        return self.urls.get(short_code)

    def delete(self, short_code: str) -> bool:
        if short_code not in self.urls:
            return False
        del self.urls[short_code]
        return True
