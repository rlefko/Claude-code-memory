"""Abstract base class for issue tracker integrations.

This module provides the base class that all issue tracker clients
must implement, along with common functionality for rate limiting
and retry logic.
"""

from __future__ import annotations

import random
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import TicketEntity, TicketSource, TicketStatus


class IntegrationClient(ABC):
    """Abstract base class for issue tracker integrations.

    Provides common functionality for rate limiting and retry logic,
    following the patterns established in the embeddings module.
    """

    def __init__(
        self,
        api_key: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        requests_per_minute: int = 60,
    ):
        """Initialize the integration client.

        Args:
            api_key: API key for authentication
            max_retries: Maximum number of retry attempts
            base_delay: Base delay for exponential backoff (seconds)
            max_delay: Maximum delay between retries (seconds)
            requests_per_minute: Rate limit (requests per minute)
        """
        self.api_key = api_key
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._requests_per_minute = requests_per_minute

        # Rate limiting state
        self._request_times: list[float] = []

    @property
    @abstractmethod
    def source(self) -> TicketSource:
        """Return the ticket source for this client."""
        pass

    @abstractmethod
    def search_tickets(
        self,
        query: str | None = None,
        status: list[TicketStatus] | None = None,
        labels: list[str] | None = None,
        project: str | None = None,
        limit: int = 20,
    ) -> list[TicketEntity]:
        """Search for tickets matching criteria.

        Args:
            query: Text search query for title/description
            status: Filter by ticket status
            labels: Filter by labels
            project: Filter by project/repo
            limit: Maximum number of results

        Returns:
            List of matching tickets
        """
        pass

    @abstractmethod
    def get_ticket(
        self,
        ticket_id: str,
        include_comments: bool = True,
        include_prs: bool = True,
    ) -> TicketEntity | None:
        """Get full ticket details by ID.

        Args:
            ticket_id: The ticket identifier
            include_comments: Whether to fetch comments
            include_prs: Whether to fetch linked PRs

        Returns:
            Full ticket details or None if not found
        """
        pass

    @abstractmethod
    def list_projects(self) -> list[dict[str, str]]:
        """List available projects/repos.

        Returns:
            List of projects with id and name
        """
        pass

    def _check_rate_limits(self) -> None:
        """Check and enforce rate limits.

        Blocks if rate limit would be exceeded.
        Follows the pattern from openai.py embeddings.
        """
        current_time = time.time()

        # Clean old entries (older than 1 minute)
        self._request_times = [t for t in self._request_times if current_time - t < 60]

        # Check if would exceed limit
        if len(self._request_times) >= self._requests_per_minute:
            sleep_time = 60 - (current_time - self._request_times[0]) + 1
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _record_request(self) -> None:
        """Record a request for rate limiting."""
        self._request_times.append(time.time())

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = self.base_delay * (2**attempt)
        delay = min(delay, self.max_delay)
        # Add jitter (10-30% of delay)
        jitter = random.uniform(0.1, 0.3) * delay
        return delay + jitter

    def _should_retry(self, error: Exception, attempt: int) -> bool:
        """Determine if error should trigger retry.

        Args:
            error: The exception that occurred
            attempt: Current attempt number (0-indexed)

        Returns:
            True if should retry, False otherwise
        """
        if attempt >= self.max_retries:
            return False

        error_str = str(error).lower()
        transient_errors = [
            "rate limit",
            "timeout",
            "connection",
            "429",
            "503",
            "502",
            "500",
            "temporarily unavailable",
        ]
        return any(err in error_str for err in transient_errors)

    def _execute_with_retry(self, operation: callable, *args, **kwargs):
        """Execute an operation with retry logic.

        Args:
            operation: The function to execute
            *args: Positional arguments for the operation
            **kwargs: Keyword arguments for the operation

        Returns:
            Result of the operation

        Raises:
            Exception: If all retries are exhausted
        """
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                self._check_rate_limits()
                result = operation(*args, **kwargs)
                self._record_request()
                return result
            except Exception as e:
                last_error = e
                if self._should_retry(e, attempt):
                    delay = self._calculate_delay(attempt)
                    time.sleep(delay)
                else:
                    raise

        if last_error:
            raise last_error
