"""Data models for issue tracker integrations.

This module defines unified data structures for tickets from
Linear, GitHub Issues, and other issue tracking systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TicketSource(Enum):
    """Source systems for tickets."""

    LINEAR = "linear"
    GITHUB = "github"


class TicketStatus(Enum):
    """Normalized ticket status across platforms."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class TicketPriority(Enum):
    """Normalized priority levels."""

    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


# Status mappings for Linear
LINEAR_STATUS_MAP: dict[str, TicketStatus] = {
    "backlog": TicketStatus.OPEN,
    "todo": TicketStatus.OPEN,
    "unstarted": TicketStatus.OPEN,
    "started": TicketStatus.IN_PROGRESS,
    "in progress": TicketStatus.IN_PROGRESS,
    "in review": TicketStatus.IN_PROGRESS,
    "done": TicketStatus.DONE,
    "completed": TicketStatus.DONE,
    "cancelled": TicketStatus.CANCELLED,
    "canceled": TicketStatus.CANCELLED,
    "duplicate": TicketStatus.CANCELLED,
}

# Priority mappings for Linear (0 = no priority, 1 = urgent, 4 = low)
LINEAR_PRIORITY_MAP: dict[int, TicketPriority] = {
    0: TicketPriority.NONE,
    1: TicketPriority.URGENT,
    2: TicketPriority.HIGH,
    3: TicketPriority.MEDIUM,
    4: TicketPriority.LOW,
}

# Status mappings for GitHub
GITHUB_STATUS_MAP: dict[str, TicketStatus] = {
    "open": TicketStatus.OPEN,
    "closed": TicketStatus.DONE,
}


@dataclass(frozen=True)
class TicketComment:
    """A comment on a ticket."""

    id: str
    author: str
    body: str
    created_at: datetime
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "author": self.author,
            "body": self.body,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass(frozen=True)
class TicketEntity:
    """Unified ticket representation across Linear and GitHub.

    This dataclass provides a normalized view of tickets from different
    issue tracking systems, enabling consistent search and retrieval.
    """

    id: str  # Platform-specific ID
    source: TicketSource  # linear or github
    identifier: str  # Human-readable (e.g., "AVO-123", "owner/repo#456")
    title: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    labels: tuple[str, ...] = field(default_factory=tuple)
    assignee: str | None = None
    url: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Rich content (loaded on get_ticket)
    comments: tuple[TicketComment, ...] = field(default_factory=tuple)
    linked_prs: tuple[str, ...] = field(default_factory=tuple)  # PR URLs

    # Metadata for filtering
    project: str | None = None  # Linear project or GitHub repo
    team: str | None = None  # Linear team
    milestone: str | None = None

    def to_search_result(self, score: float = 0.0) -> dict[str, Any]:
        """Convert to search result format for MCP.

        Args:
            score: Optional relevance score (0.0-1.0)

        Returns a lightweight representation suitable for search results.
        """
        return {
            "type": "ticket",
            "score": score,
            "data": {
                "id": self.id,
                "identifier": self.identifier,
                "source": self.source.value,
                "title": self.title,
                "status": self.status.value,
                "priority": self.priority.value,
                "labels": list(self.labels),
                "url": self.url,
                "content_preview": (
                    self.description[:200] + "..."
                    if len(self.description) > 200
                    else self.description
                ),
            },
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to full dictionary for MCP get_ticket response."""
        return {
            "id": self.id,
            "identifier": self.identifier,
            "source": self.source.value,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "labels": list(self.labels),
            "assignee": self.assignee,
            "url": self.url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "comments": [c.to_dict() for c in self.comments],
            "linked_prs": list(self.linked_prs),
            "project": self.project,
            "team": self.team,
            "milestone": self.milestone,
        }

    def to_vector_content(self) -> str:
        """Generate content for vector embedding.

        Creates a searchable text representation optimized for
        semantic search.
        """
        parts = [
            f"[{self.identifier}] {self.title}",
            f"Status: {self.status.value}",
            f"Priority: {self.priority.value}",
        ]
        if self.labels:
            parts.append(f"Labels: {', '.join(self.labels)}")
        if self.assignee:
            parts.append(f"Assignee: {self.assignee}")
        if self.description:
            parts.append(self.description[:500])  # Truncate for embedding
        return " | ".join(parts)


def normalize_linear_status(
    state_name: str, state_type: str | None = None
) -> TicketStatus:
    """Normalize Linear state to TicketStatus.

    Args:
        state_name: The name of the Linear state (e.g., "In Progress")
        state_type: Optional state type from Linear API (e.g., "started", "completed")

    Returns:
        Normalized TicketStatus
    """
    # Try state type first (more reliable)
    if state_type:
        state_type_lower = state_type.lower()
        if state_type_lower in LINEAR_STATUS_MAP:
            return LINEAR_STATUS_MAP[state_type_lower]

    # Fall back to state name
    state_name_lower = state_name.lower()
    return LINEAR_STATUS_MAP.get(state_name_lower, TicketStatus.OPEN)


def normalize_linear_priority(priority: int | None) -> TicketPriority:
    """Normalize Linear priority to TicketPriority.

    Args:
        priority: Linear priority value (0-4)

    Returns:
        Normalized TicketPriority
    """
    if priority is None:
        return TicketPriority.NONE
    return LINEAR_PRIORITY_MAP.get(priority, TicketPriority.NONE)


def normalize_github_status(state: str) -> TicketStatus:
    """Normalize GitHub issue state to TicketStatus.

    Args:
        state: GitHub issue state ("open" or "closed")

    Returns:
        Normalized TicketStatus
    """
    return GITHUB_STATUS_MAP.get(state.lower(), TicketStatus.OPEN)


def infer_github_priority(labels: list[str]) -> TicketPriority:
    """Infer priority from GitHub labels.

    Common label patterns:
    - P0, priority:critical, critical -> URGENT
    - P1, priority:high, high-priority -> HIGH
    - P2, priority:medium -> MEDIUM
    - P3, priority:low, low-priority -> LOW

    Args:
        labels: List of label names from GitHub issue

    Returns:
        Inferred TicketPriority
    """
    labels_lower = [label.lower() for label in labels]

    # Check for urgent/critical
    for label in labels_lower:
        if any(
            term in label for term in ["p0", "critical", "urgent", "priority: critical"]
        ):
            return TicketPriority.URGENT

    # Check for high
    for label in labels_lower:
        if any(term in label for term in ["p1", "high", "priority: high"]):
            return TicketPriority.HIGH

    # Check for medium
    for label in labels_lower:
        if any(term in label for term in ["p2", "medium", "priority: medium"]):
            return TicketPriority.MEDIUM

    # Check for low
    for label in labels_lower:
        if any(term in label for term in ["p3", "low", "priority: low"]):
            return TicketPriority.LOW

    return TicketPriority.NONE


def parse_github_identifier(identifier: str) -> tuple[str, str, int] | None:
    """Parse GitHub issue identifier into components.

    Args:
        identifier: Format "owner/repo#123" or just "#123"

    Returns:
        Tuple of (owner, repo, issue_number) or None if invalid
    """
    if "#" not in identifier:
        return None

    parts = identifier.split("#")
    if len(parts) != 2:
        return None

    try:
        issue_number = int(parts[1])
    except ValueError:
        return None

    repo_part = parts[0]
    if "/" in repo_part:
        repo_parts = repo_part.split("/")
        if len(repo_parts) == 2:
            return (repo_parts[0], repo_parts[1], issue_number)

    return None
