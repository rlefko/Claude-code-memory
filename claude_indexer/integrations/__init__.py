"""Issue tracker integrations for Claude Code Memory.

This package provides clients for external issue tracking systems
(Linear, GitHub Issues) that can be queried via MCP tools.
"""

from .base import IntegrationClient
from .cache import TicketCache
from .github import GitHubIssuesClient
from .linear import LinearClient
from .models import (
    GITHUB_STATUS_MAP,
    LINEAR_PRIORITY_MAP,
    LINEAR_STATUS_MAP,
    TicketComment,
    TicketEntity,
    TicketPriority,
    TicketSource,
    TicketStatus,
    normalize_github_status,
    normalize_linear_priority,
    normalize_linear_status,
    parse_github_identifier,
)

__all__ = [
    # Clients
    "IntegrationClient",
    "LinearClient",
    "GitHubIssuesClient",
    # Cache
    "TicketCache",
    # Models
    "TicketEntity",
    "TicketComment",
    "TicketSource",
    "TicketStatus",
    "TicketPriority",
    # Mappings
    "LINEAR_STATUS_MAP",
    "LINEAR_PRIORITY_MAP",
    "GITHUB_STATUS_MAP",
    # Utilities
    "normalize_linear_status",
    "normalize_linear_priority",
    "normalize_github_status",
    "parse_github_identifier",
]
