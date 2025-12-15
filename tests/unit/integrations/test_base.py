"""Tests for integration base client (Milestone 8.3)."""

import time
from unittest.mock import MagicMock, patch

import pytest

from claude_indexer.integrations.base import IntegrationClient
from claude_indexer.integrations.models import (
    TicketEntity,
    TicketSource,
    TicketStatus,
)


class ConcreteClient(IntegrationClient):
    """Concrete implementation for testing abstract base class."""

    def __init__(self, api_key: str = "test-key", requests_per_minute: int = 60):
        super().__init__(api_key, requests_per_minute=requests_per_minute)
        self.call_count = 0

    @property
    def source(self) -> TicketSource:
        """Return the ticket source for this client."""
        return TicketSource.LINEAR

    def search_tickets(
        self,
        query: str | None = None,
        status: list[TicketStatus] | None = None,
        labels: list[str] | None = None,
        project: str | None = None,
        limit: int = 20,
    ) -> list[TicketEntity]:
        """Mock search implementation."""
        self.call_count += 1
        return []

    def get_ticket(
        self,
        ticket_id: str,
        include_comments: bool = True,
        include_prs: bool = True,
    ) -> TicketEntity | None:
        """Mock get implementation."""
        self.call_count += 1
        return None

    def list_projects(self) -> list[dict]:
        """Mock list projects implementation."""
        return []


class TestIntegrationClientInit:
    """Test IntegrationClient initialization."""

    def test_init_with_api_key(self):
        """Test initialization with API key."""
        client = ConcreteClient(api_key="my-api-key")
        assert client.api_key == "my-api-key"

    def test_init_with_rate_limit(self):
        """Test initialization with custom rate limit."""
        client = ConcreteClient(requests_per_minute=30)
        assert client._requests_per_minute == 30

    def test_init_default_rate_limit(self):
        """Test default rate limit is 60."""
        client = ConcreteClient()
        assert client._requests_per_minute == 60


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_check_rate_limits_initially_ok(self):
        """Test that rate limits are initially OK."""
        client = ConcreteClient(requests_per_minute=60)
        # Should not raise
        client._check_rate_limits()

    def test_record_request(self):
        """Test recording a request updates timestamp list."""
        client = ConcreteClient(requests_per_minute=60)
        initial_count = len(client._request_times)
        client._record_request()
        assert len(client._request_times) == initial_count + 1

    def test_rate_limit_cleanup_old_timestamps(self):
        """Test that old timestamps are cleaned up."""
        client = ConcreteClient(requests_per_minute=60)
        # Add old timestamps (more than 60 seconds ago)
        old_time = time.time() - 120
        client._request_times = [old_time] * 10
        # Calling _check_rate_limits cleans up old entries
        client._check_rate_limits()
        # Old timestamps should be removed
        assert len(client._request_times) == 0

    def test_rate_limit_blocks_when_exceeded(self):
        """Test that rate limit causes blocking when exceeded."""
        client = ConcreteClient(requests_per_minute=5)
        # Fill up the rate limit
        now = time.time()
        client._request_times = [now] * 5
        # This should cause a sleep rather than raise
        # Let's mock sleep to verify it's called
        with patch("time.sleep") as mock_sleep:
            client._check_rate_limits()
            # Should have called sleep since we're at the limit
            mock_sleep.assert_called()


class TestRetryLogic:
    """Test retry and backoff logic."""

    def test_calculate_delay_base(self):
        """Test base delay calculation."""
        client = ConcreteClient()
        delay = client._calculate_delay(attempt=0)
        assert delay >= 1.0  # Base delay
        assert delay <= 1.5  # Base + jitter (max 30%)

    def test_calculate_delay_exponential(self):
        """Test exponential backoff."""
        client = ConcreteClient()
        # Mock random to get consistent results
        with patch("random.uniform", return_value=0.2):
            delay_0 = client._calculate_delay(attempt=0)
            delay_1 = client._calculate_delay(attempt=1)
            delay_2 = client._calculate_delay(attempt=2)
        # Each delay should be roughly double
        assert delay_1 > delay_0
        assert delay_2 > delay_1

    def test_calculate_delay_max_cap(self):
        """Test delay is capped at maximum."""
        client = ConcreteClient()
        delay = client._calculate_delay(attempt=10)
        # max_delay (30) + max jitter (30% of 30 = 9)
        assert delay <= 40

    def test_should_retry_rate_limit_error(self):
        """Test that rate limit errors trigger retry."""
        client = ConcreteClient()
        error = Exception("rate limit exceeded")
        assert client._should_retry(error, attempt=0)

    def test_should_retry_timeout_error(self):
        """Test that timeout errors trigger retry."""
        client = ConcreteClient()
        error = Exception("connection timeout")
        assert client._should_retry(error, attempt=0)

    def test_should_retry_server_error(self):
        """Test that 5xx errors trigger retry."""
        client = ConcreteClient()
        error = Exception("500 Internal Server Error")
        assert client._should_retry(error, attempt=0)

    def test_should_not_retry_auth_error(self):
        """Test that auth errors do not trigger retry."""
        client = ConcreteClient()
        error = Exception("401 Unauthorized")
        assert not client._should_retry(error, attempt=0)

    def test_should_not_retry_not_found(self):
        """Test that 404 errors do not trigger retry."""
        client = ConcreteClient()
        error = Exception("404 Not Found")
        assert not client._should_retry(error, attempt=0)

    def test_should_not_retry_max_attempts(self):
        """Test that max attempts stops retry."""
        client = ConcreteClient()
        error = Exception("rate limit exceeded")
        # max_retries defaults to 3, so attempt=3 should stop
        assert not client._should_retry(error, attempt=3)


class TestExecuteWithRetry:
    """Test execute_with_retry wrapper."""

    def test_successful_execution(self):
        """Test successful execution without retry."""
        client = ConcreteClient()
        mock_func = MagicMock(return_value="success")
        result = client._execute_with_retry(mock_func)
        assert result == "success"
        assert mock_func.call_count == 1

    def test_retry_on_transient_error(self):
        """Test retry on transient error."""
        client = ConcreteClient()
        mock_func = MagicMock(side_effect=[Exception("timeout"), "success"])
        with patch.object(client, "_calculate_delay", return_value=0.01):
            with patch("time.sleep"):
                result = client._execute_with_retry(mock_func)
        assert result == "success"
        assert mock_func.call_count == 2

    def test_no_retry_on_permanent_error(self):
        """Test no retry on permanent error."""
        client = ConcreteClient()
        mock_func = MagicMock(side_effect=Exception("401 Unauthorized"))
        with pytest.raises(Exception) as exc_info:
            client._execute_with_retry(mock_func)
        assert "401 Unauthorized" in str(exc_info.value)
        assert mock_func.call_count == 1

    def test_max_retries_exceeded(self):
        """Test that max retries are respected."""
        client = ConcreteClient()
        mock_func = MagicMock(side_effect=Exception("timeout"))
        with patch.object(client, "_calculate_delay", return_value=0.01):
            with patch("time.sleep"):
                with pytest.raises(Exception) as exc_info:
                    client._execute_with_retry(mock_func)
        assert "timeout" in str(exc_info.value)
        # max_retries is 3, so it tries 4 times total (0, 1, 2, 3)
        assert mock_func.call_count == 4


class TestAbstractMethods:
    """Test that abstract methods must be implemented."""

    def test_cannot_instantiate_base_class(self):
        """Test that base class cannot be instantiated directly."""
        with pytest.raises(TypeError):
            IntegrationClient(api_key="test")  # type: ignore

    def test_concrete_class_works(self):
        """Test that concrete implementation works."""
        client = ConcreteClient()
        assert client is not None
