import time
from collections import defaultdict
from threading import Lock


class RateLimiter:
    """
    Simple in-memory rate limiter.

    Each client is identified by an IP address.

    Example:
        10 requests per 60 seconds.
    """

    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: int = 60,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

        self.requests = defaultdict(list)

        self.lock = Lock()

    def is_allowed(self, client_id: str) -> bool:
        """
        Check whether the client is allowed to make another request.

        Returns:
            True  -> request is allowed
            False -> rate limit exceeded
        """

        current_time = time.time()

        with self.lock:

            request_times = self.requests[client_id]

            # Remove requests outside the current time window.
            request_times[:] = [
                request_time
                for request_time in request_times
                if current_time - request_time
                < self.window_seconds
            ]

            # Check limit.
            if len(request_times) >= self.max_requests:
                return False

            # Record current request.
            request_times.append(current_time)

            return True

    def get_remaining_requests(
        self,
        client_id: str,
    ) -> int:
        """
        Return the number of requests remaining
        for the current client.
        """

        current_time = time.time()

        with self.lock:

            request_times = self.requests[client_id]

            request_times[:] = [
                request_time
                for request_time in request_times
                if current_time - request_time
                < self.window_seconds
            ]

            remaining = (
                self.max_requests
                - len(request_times)
            )

            return max(remaining, 0)

    def reset(self) -> None:
        """
        Clear all rate-limiter data.

        Useful for testing.
        """

        with self.lock:
            self.requests.clear()