"""Caching layer for issue tracker integrations.

This module provides TTL-based caching with LRU eviction,
following the pattern from storage/query_cache.py.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import TicketEntity


@dataclass
class CacheEntry:
    """A single cache entry with TTL tracking."""

    value: Any
    created_at: float
    hits: int = 0


class TicketCache:
    """TTL-based cache with LRU eviction for ticket data.

    Thread-safe implementation following query_cache.py patterns.
    """

    def __init__(
        self,
        max_entries: int = 500,
        ttl_seconds: float = 300.0,  # 5 minutes default
    ):
        """Initialize the ticket cache.

        Args:
            max_entries: Maximum number of entries before LRU eviction
            ttl_seconds: Time-to-live for entries in seconds
        """
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = Lock()

        # Statistics
        self._hits = 0
        self._misses = 0

    def _compute_key(self, *args, **kwargs) -> str:
        """Compute a cache key from arguments.

        Args:
            *args: Positional arguments to hash
            **kwargs: Keyword arguments to hash

        Returns:
            16-character hex string key
        """
        # Create a deterministic string representation
        key_data = json.dumps(
            {"args": args, "kwargs": kwargs},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]

    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if a cache entry has expired.

        Args:
            entry: The cache entry to check

        Returns:
            True if expired, False otherwise
        """
        return time.time() - entry.created_at > self.ttl_seconds

    def _evict_if_needed(self) -> None:
        """Evict oldest entries if cache is full.

        Must be called while holding the lock.
        """
        while len(self._cache) >= self.max_entries:
            # Remove oldest entry (first item in OrderedDict)
            self._cache.popitem(last=False)

    def _prune_expired(self) -> int:
        """Remove all expired entries.

        Must be called while holding the lock.

        Returns:
            Number of entries removed
        """
        current_time = time.time()
        expired_keys = [
            key
            for key, entry in self._cache.items()
            if current_time - entry.created_at > self.ttl_seconds
        ]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)

    def get(self, key: str) -> Any | None:
        """Get a value from the cache.

        Args:
            key: The cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            if self._is_expired(entry):
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.hits += 1
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any) -> None:
        """Set a value in the cache.

        Args:
            key: The cache key
            value: The value to cache
        """
        with self._lock:
            # Prune expired entries periodically
            if len(self._cache) > 0 and len(self._cache) % 100 == 0:
                self._prune_expired()

            self._evict_if_needed()
            self._cache[key] = CacheEntry(
                value=value,
                created_at=time.time(),
            )

    def get_ticket(self, ticket_id: str, source: str) -> TicketEntity | None:
        """Get a cached ticket by ID.

        Args:
            ticket_id: The ticket identifier
            source: The ticket source (linear, github)

        Returns:
            Cached ticket or None
        """
        key = self._compute_key("ticket", ticket_id, source)
        return self.get(key)

    def set_ticket(self, ticket: TicketEntity) -> None:
        """Cache a ticket.

        Args:
            ticket: The ticket to cache
        """
        key = self._compute_key("ticket", ticket.id, ticket.source.value)
        self.set(key, ticket)

    def get_search_results(
        self,
        query: str | None,
        status: list[str] | None,
        labels: list[str] | None,
        source: str | None,
        project: str | None,
        limit: int,
    ) -> list[TicketEntity] | None:
        """Get cached search results.

        Args:
            query: Search query
            status: Status filter
            labels: Labels filter
            source: Source filter
            project: Project filter
            limit: Result limit

        Returns:
            Cached results or None
        """
        key = self._compute_key(
            "search",
            query=query,
            status=sorted(status) if status else None,
            labels=sorted(labels) if labels else None,
            source=source,
            project=project,
            limit=limit,
        )
        return self.get(key)

    def set_search_results(
        self,
        results: list[TicketEntity],
        query: str | None,
        status: list[str] | None,
        labels: list[str] | None,
        source: str | None,
        project: str | None,
        limit: int,
    ) -> None:
        """Cache search results.

        Args:
            results: The results to cache
            query: Search query
            status: Status filter
            labels: Labels filter
            source: Source filter
            project: Project filter
            limit: Result limit
        """
        key = self._compute_key(
            "search",
            query=query,
            status=sorted(status) if status else None,
            labels=sorted(labels) if labels else None,
            source=source,
            project=project,
            limit=limit,
        )
        self.set(key, results)

    def invalidate(self, source: str | None = None) -> int:
        """Invalidate cache entries.

        Args:
            source: If provided, only invalidate entries for this source

        Returns:
            Number of entries removed
        """
        with self._lock:
            if source is None:
                count = len(self._cache)
                self._cache.clear()
                return count

            # For source-specific invalidation, we need to check all entries
            # This is O(n) but invalidation should be rare
            keys_to_remove = []
            for key, entry in self._cache.items():
                value = entry.value
                if hasattr(value, "source") and value.source.value == source:
                    keys_to_remove.append(key)
                elif isinstance(value, list) and value:
                    if hasattr(value[0], "source") and value[0].source.value == source:
                        keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._cache[key]
            return len(keys_to_remove)

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        return self.invalidate()

    @property
    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0
            return {
                "entries": len(self._cache),
                "max_entries": self.max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "ttl_seconds": self.ttl_seconds,
            }
