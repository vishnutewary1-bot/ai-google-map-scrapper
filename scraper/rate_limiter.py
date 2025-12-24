"""Advanced rate limiting for scraping operations."""
import asyncio
from datetime import datetime, timedelta
from typing import Dict
from loguru import logger
from collections import deque


class RateLimiter:
    """Advanced rate limiter with multiple strategies."""

    def __init__(
        self,
        max_requests_per_hour: int = 100,
        max_requests_per_minute: int = 20,
        base_delay_min: int = 3,
        base_delay_max: int = 8,
        cooldown_after_error: int = 60
    ):
        self.max_requests_per_hour = max_requests_per_hour
        self.max_requests_per_minute = max_requests_per_minute
        self.base_delay_min = base_delay_min
        self.base_delay_max = base_delay_max
        self.cooldown_after_error = cooldown_after_error

        # Track requests
        self.requests_history: deque = deque()  # Timestamps of requests
        self.last_request_time: datetime = None
        self.consecutive_errors = 0
        self.is_in_cooldown = False
        self.cooldown_until: datetime = None

        # Statistics
        self.total_requests = 0
        self.total_delays_applied = 0
        self.total_cooldowns = 0

    async def wait_if_needed(self):
        """Wait if rate limits require it."""
        # Check if in cooldown
        if self.is_in_cooldown:
            if datetime.now() < self.cooldown_until:
                wait_seconds = (self.cooldown_until - datetime.now()).total_seconds()
                logger.warning(f"In cooldown mode. Waiting {wait_seconds:.1f} seconds...")
                await asyncio.sleep(wait_seconds)
            self.is_in_cooldown = False
            self.cooldown_until = None

        # Clean old requests from history (older than 1 hour)
        cutoff_time = datetime.now() - timedelta(hours=1)
        while self.requests_history and self.requests_history[0] < cutoff_time:
            self.requests_history.popleft()

        # Check hourly limit
        if len(self.requests_history) >= self.max_requests_per_hour:
            oldest_request = self.requests_history[0]
            wait_until = oldest_request + timedelta(hours=1)
            wait_seconds = (wait_until - datetime.now()).total_seconds()

            if wait_seconds > 0:
                logger.warning(f"Hourly rate limit reached. Waiting {wait_seconds:.1f} seconds...")
                await asyncio.sleep(wait_seconds)
                self.total_delays_applied += 1

        # Check minute limit
        minute_ago = datetime.now() - timedelta(minutes=1)
        recent_requests = sum(1 for req_time in self.requests_history if req_time > minute_ago)

        if recent_requests >= self.max_requests_per_minute:
            wait_seconds = 60
            logger.warning(f"Per-minute rate limit reached. Waiting {wait_seconds} seconds...")
            await asyncio.sleep(wait_seconds)
            self.total_delays_applied += 1

        # Apply base delay between requests
        if self.last_request_time:
            import random
            base_delay = random.uniform(self.base_delay_min, self.base_delay_max)

            # Exponential backoff if consecutive errors
            if self.consecutive_errors > 0:
                backoff_multiplier = min(2 ** self.consecutive_errors, 8)  # Max 8x
                base_delay *= backoff_multiplier
                logger.info(f"Applying exponential backoff: {base_delay:.1f}s (errors: {self.consecutive_errors})")

            time_since_last = (datetime.now() - self.last_request_time).total_seconds()
            if time_since_last < base_delay:
                wait_time = base_delay - time_since_last
                logger.debug(f"Base delay: waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

        # Record this request
        now = datetime.now()
        self.requests_history.append(now)
        self.last_request_time = now
        self.total_requests += 1

    async def apply_extra_delay(self, delay_seconds: int):
        """Apply an extra delay (e.g., after every 10 requests)."""
        logger.info(f"Applying extra delay: {delay_seconds} seconds")
        await asyncio.sleep(delay_seconds)
        self.total_delays_applied += 1

    def record_success(self):
        """Record a successful request."""
        self.consecutive_errors = 0

    def record_error(self, trigger_cooldown: bool = True):
        """Record a failed request."""
        self.consecutive_errors += 1
        logger.warning(f"Request error recorded (consecutive: {self.consecutive_errors})")

        # Trigger cooldown after multiple consecutive errors
        if trigger_cooldown and self.consecutive_errors >= 3:
            self.enter_cooldown()

    def enter_cooldown(self):
        """Enter cooldown mode."""
        self.is_in_cooldown = True
        self.cooldown_until = datetime.now() + timedelta(seconds=self.cooldown_after_error)
        self.total_cooldowns += 1
        logger.error(f"Entering cooldown mode for {self.cooldown_after_error} seconds")

    def reset_errors(self):
        """Reset error counter."""
        self.consecutive_errors = 0

    async def wait_after_batch(self, batch_size: int = 10):
        """Wait after processing a batch of requests."""
        if self.total_requests % batch_size == 0:
            wait_time = 30 + (self.consecutive_errors * 10)  # Longer wait if errors
            logger.info(f"Batch of {batch_size} completed. Taking a {wait_time}s break...")
            await asyncio.sleep(wait_time)
            self.total_delays_applied += 1

    def get_stats(self) -> Dict:
        """Get rate limiter statistics."""
        requests_last_hour = len(self.requests_history)
        minute_ago = datetime.now() - timedelta(minutes=1)
        requests_last_minute = sum(1 for req_time in self.requests_history if req_time > minute_ago)

        return {
            'total_requests': self.total_requests,
            'requests_last_hour': requests_last_hour,
            'requests_last_minute': requests_last_minute,
            'consecutive_errors': self.consecutive_errors,
            'is_in_cooldown': self.is_in_cooldown,
            'total_delays_applied': self.total_delays_applied,
            'total_cooldowns': self.total_cooldowns,
            'max_requests_per_hour': self.max_requests_per_hour,
            'max_requests_per_minute': self.max_requests_per_minute
        }

    def is_healthy(self) -> bool:
        """Check if rate limiter is in healthy state."""
        return self.consecutive_errors < 5 and not self.is_in_cooldown
