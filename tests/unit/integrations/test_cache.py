"""Tests for ticket cache (Milestone 8.3)."""

import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from claude_indexer.integrations.cache import TicketCache
from claude_indexer.integrations.models import (
    TicketEntity,
    TicketPriority,
    TicketSource,
    TicketStatus,
)


class TestTicketCacheInit:
    """Test TicketCache initialization."""

    def test_default_ttl(self):
        """Test default TTL is 300 seconds."""
        cache = TicketCache()
        assert cache.ttl_seconds == 300

    def test_custom_ttl(self):
        """Test custom TTL."""
        cache = TicketCache(ttl_seconds=600)
        assert cache.ttl_seconds == 600

    def test_default_max_entries(self):
        """Test default max entries is 500."""
        cache = TicketCache()
        assert cache.max_entries == 500

    def test_custom_max_entries(self):
        """Test custom max entries."""
        cache = TicketCache(max_entries=100)
        assert cache.max_entries == 100


class TestTicketCacheOperations:
    """Test basic cache operations."""

    @pytest.fixture
    def cache(self) -> TicketCache:
        """Create a cache instance for testing."""
        return TicketCache(ttl_seconds=60, max_entries=10)

    @pytest.fixture
    def sample_ticket(self) -> TicketEntity:
        """Create a sample ticket."""
        return TicketEntity(
            id="ticket-123",
            source=TicketSource.LINEAR,
            identifier="AVO-123",
            title="Test ticket",
            description="Test description",
            status=TicketStatus.OPEN,
            priority=TicketPriority.HIGH,
            labels=("bug",),
            url="https://example.com/ticket-123",
        )

    def test_set_and_get_ticket(self, cache, sample_ticket):
        """Test setting and getting a ticket."""
        cache.set_ticket(sample_ticket)
        result = cache.get_ticket("ticket-123", "linear")
        assert result is not None
        assert result.id == "ticket-123"
        assert result.title == "Test ticket"

    def test_get_nonexistent_ticket(self, cache):
        """Test getting a nonexistent ticket returns None."""
        result = cache.get_ticket("nonexistent", "linear")
        assert result is None

    def test_set_and_get_search_results(self, cache, sample_ticket):
        """Test setting and getting search results."""
        results = [sample_ticket]
        cache.set_search_results(
            results,
            query="test",
            status=["open"],
            labels=["bug"],
            source="linear",
            project=None,
            limit=20,
        )
        cached_results = cache.get_search_results(
            query="test",
            status=["open"],
            labels=["bug"],
            source="linear",
            project=None,
            limit=20,
        )
        assert cached_results is not None
        assert len(cached_results) == 1
        assert cached_results[0].id == "ticket-123"

    def test_get_nonexistent_search_results(self, cache):
        """Test getting nonexistent search results returns None."""
        result = cache.get_search_results(
            query="nonexistent",
            status=None,
            labels=None,
            source=None,
            project=None,
            limit=20,
        )
        assert result is None


class TestTicketCacheTTL:
    """Test TTL expiration."""

    def test_ticket_expires_after_ttl(self):
        """Test that tickets expire after TTL."""
        cache = TicketCache(ttl_seconds=1)
        ticket = TicketEntity(
            id="ticket-123",
            source=TicketSource.LINEAR,
            identifier="AVO-123",
            title="Test",
            description="Test",
            status=TicketStatus.OPEN,
            priority=TicketPriority.MEDIUM,
            labels=(),
            url="https://example.com",
        )
        cache.set_ticket(ticket)

        # Should be in cache immediately
        assert cache.get_ticket("ticket-123", "linear") is not None

        # Wait for TTL to expire
        time.sleep(1.5)

        # Should be expired now
        assert cache.get_ticket("ticket-123", "linear") is None

    def test_search_results_expire_after_ttl(self):
        """Test that search results expire after TTL."""
        cache = TicketCache(ttl_seconds=1)
        ticket = TicketEntity(
            id="ticket-123",
            source=TicketSource.GITHUB,
            identifier="owner/repo#123",
            title="Test",
            description="Test",
            status=TicketStatus.OPEN,
            priority=TicketPriority.LOW,
            labels=(),
            url="https://example.com",
        )
        cache.set_search_results(
            [ticket],
            query="test",
            status=None,
            labels=None,
            source=None,
            project=None,
            limit=20,
        )

        # Should be in cache immediately
        result = cache.get_search_results(
            query="test",
            status=None,
            labels=None,
            source=None,
            project=None,
            limit=20,
        )
        assert result is not None

        # Wait for TTL to expire
        time.sleep(1.5)

        # Should be expired now
        result = cache.get_search_results(
            query="test",
            status=None,
            labels=None,
            source=None,
            project=None,
            limit=20,
        )
        assert result is None


class TestTicketCacheLRU:
    """Test LRU eviction."""

    def test_lru_eviction_on_max_entries(self):
        """Test that oldest entries are evicted when max is reached."""
        cache = TicketCache(ttl_seconds=300, max_entries=3)

        # Add 3 tickets
        for i in range(3):
            ticket = TicketEntity(
                id=f"ticket-{i}",
                source=TicketSource.LINEAR,
                identifier=f"AVO-{i}",
                title=f"Test {i}",
                description="Test",
                status=TicketStatus.OPEN,
                priority=TicketPriority.MEDIUM,
                labels=(),
                url=f"https://example.com/{i}",
            )
            cache.set_ticket(ticket)

        # Add a 4th ticket - this should evict ticket-0 (oldest)
        ticket = TicketEntity(
            id="ticket-3",
            source=TicketSource.LINEAR,
            identifier="AVO-3",
            title="Test 3",
            description="Test",
            status=TicketStatus.OPEN,
            priority=TicketPriority.MEDIUM,
            labels=(),
            url="https://example.com/3",
        )
        cache.set_ticket(ticket)

        # ticket-0 should be evicted (oldest by insertion order)
        assert cache.get_ticket("ticket-0", "linear") is None
        # Others should still be present
        assert cache.get_ticket("ticket-1", "linear") is not None
        assert cache.get_ticket("ticket-2", "linear") is not None
        assert cache.get_ticket("ticket-3", "linear") is not None


class TestTicketCacheInvalidation:
    """Test cache invalidation."""

    def test_invalidate_by_source(self):
        """Test invalidating entries by source."""
        cache = TicketCache()
        linear_ticket = TicketEntity(
            id="ticket-1",
            source=TicketSource.LINEAR,
            identifier="AVO-1",
            title="Linear ticket",
            description="Test",
            status=TicketStatus.OPEN,
            priority=TicketPriority.HIGH,
            labels=(),
            url="https://linear.app/1",
        )
        github_ticket = TicketEntity(
            id="ticket-2",
            source=TicketSource.GITHUB,
            identifier="owner/repo#2",
            title="GitHub ticket",
            description="Test",
            status=TicketStatus.OPEN,
            priority=TicketPriority.MEDIUM,
            labels=(),
            url="https://github.com/2",
        )
        cache.set_ticket(linear_ticket)
        cache.set_ticket(github_ticket)

        # Both should be present
        assert cache.get_ticket("ticket-1", "linear") is not None
        assert cache.get_ticket("ticket-2", "github") is not None

        # Invalidate linear entries
        cache.invalidate(source="linear")

        # Linear should be gone, GitHub should remain
        assert cache.get_ticket("ticket-1", "linear") is None
        assert cache.get_ticket("ticket-2", "github") is not None

    def test_clear_all(self):
        """Test clearing all cache entries."""
        cache = TicketCache()
        ticket1 = TicketEntity(
            id="ticket-1",
            source=TicketSource.LINEAR,
            identifier="AVO-1",
            title="Test 1",
            description="Test",
            status=TicketStatus.OPEN,
            priority=TicketPriority.HIGH,
            labels=(),
            url="https://example.com/1",
        )
        ticket2 = TicketEntity(
            id="ticket-2",
            source=TicketSource.GITHUB,
            identifier="owner/repo#2",
            title="Test 2",
            description="Test",
            status=TicketStatus.OPEN,
            priority=TicketPriority.MEDIUM,
            labels=(),
            url="https://example.com/2",
        )
        cache.set_ticket(ticket1)
        cache.set_ticket(ticket2)

        cache.clear()

        assert cache.get_ticket("ticket-1", "linear") is None
        assert cache.get_ticket("ticket-2", "github") is None


class TestTicketCacheThreadSafety:
    """Test thread safety."""

    def test_concurrent_reads_and_writes(self):
        """Test concurrent read/write operations."""
        cache = TicketCache(ttl_seconds=300, max_entries=100)

        def write_ticket(i: int):
            ticket = TicketEntity(
                id=f"ticket-{i}",
                source=TicketSource.LINEAR,
                identifier=f"AVO-{i}",
                title=f"Test {i}",
                description="Test",
                status=TicketStatus.OPEN,
                priority=TicketPriority.MEDIUM,
                labels=(),
                url=f"https://example.com/{i}",
            )
            cache.set_ticket(ticket)
            return cache.get_ticket(f"ticket-{i}", "linear")

        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(write_ticket, i) for i in range(50)]
            results = [f.result() for f in futures]

        # All operations should succeed
        assert all(r is not None for r in results)

    def test_concurrent_invalidation(self):
        """Test concurrent invalidation doesn't cause errors."""
        cache = TicketCache()

        # Pre-populate cache
        for i in range(20):
            ticket = TicketEntity(
                id=f"ticket-{i}",
                source=TicketSource.GITHUB,
                identifier=f"owner/repo#{i}",
                title=f"Test {i}",
                description="Test",
                status=TicketStatus.OPEN,
                priority=TicketPriority.LOW,
                labels=(),
                url=f"https://example.com/{i}",
            )
            cache.set_ticket(ticket)

        def invalidate_and_check():
            cache.clear()
            return True

        # Run concurrent invalidations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(invalidate_and_check) for _ in range(20)]
            results = [f.result() for f in futures]

        # All operations should complete without error
        assert all(r is True for r in results)


class TestCacheStats:
    """Test cache statistics."""

    def test_hit_rate_tracking(self):
        """Test that hit rate is tracked correctly."""
        cache = TicketCache()
        ticket = TicketEntity(
            id="ticket-1",
            source=TicketSource.LINEAR,
            identifier="AVO-1",
            title="Test",
            description="Test",
            status=TicketStatus.OPEN,
            priority=TicketPriority.HIGH,
            labels=(),
            url="https://example.com",
        )
        cache.set_ticket(ticket)

        # First access - hit
        cache.get_ticket("ticket-1", "linear")
        # Second access - hit
        cache.get_ticket("ticket-1", "linear")
        # Miss - nonexistent
        cache.get_ticket("nonexistent", "linear")

        stats = cache.stats
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 2 / 3
