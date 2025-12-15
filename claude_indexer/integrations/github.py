"""GitHub Issues integration.

This module provides a client for the GitHub REST API,
enabling search and retrieval of issues.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any

import requests

from .base import IntegrationClient
from .cache import TicketCache
from .models import (
    TicketComment,
    TicketEntity,
    TicketPriority,
    TicketSource,
    TicketStatus,
    normalize_github_status,
    parse_github_identifier,
)


class GitHubIssuesClient(IntegrationClient):
    """Client for GitHub REST API (Issues).

    Provides search and retrieval of GitHub issues with
    rate limiting, retry logic, and caching.
    """

    API_BASE = "https://api.github.com"

    def __init__(
        self,
        token: str | None = None,
        cache_ttl_seconds: float = 300.0,
        max_retries: int = 3,
    ):
        """Initialize GitHub client.

        Args:
            token: GitHub token (defaults to GITHUB_TOKEN env var)
            cache_ttl_seconds: Cache TTL in seconds
            max_retries: Maximum retry attempts
        """
        token = token or os.environ.get("GITHUB_TOKEN", "")
        if not token:
            raise ValueError(
                "GitHub token required. Set GITHUB_TOKEN environment variable "
                "or pass token parameter."
            )

        super().__init__(
            api_key=token,
            max_retries=max_retries,
            requests_per_minute=5000,  # GitHub rate limit (hourly)
        )

        self._cache = TicketCache(ttl_seconds=cache_ttl_seconds)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    @property
    def source(self) -> TicketSource:
        """Return the ticket source."""
        return TicketSource.GITHUB

    def _request(
        self, method: str, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        """Make a request to the GitHub API.

        Args:
            method: HTTP method
            endpoint: API endpoint (relative to base)
            params: Query parameters

        Returns:
            Response data

        Raises:
            requests.HTTPError: If request fails
        """

        def _do_request() -> dict[str, Any] | list[Any]:
            url = f"{self.API_BASE}{endpoint}"
            response = self._session.request(method, url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()

        return self._execute_with_retry(_do_request)

    def _parse_priority_from_labels(
        self, labels: list[dict[str, Any]]
    ) -> TicketPriority:
        """Extract priority from GitHub labels.

        Args:
            labels: List of label objects

        Returns:
            Inferred priority
        """
        priority_patterns = {
            TicketPriority.URGENT: r"(urgent|critical|p0|priority[:\s]*0)",
            TicketPriority.HIGH: r"(high|important|p1|priority[:\s]*1)",
            TicketPriority.MEDIUM: r"(medium|normal|p2|priority[:\s]*2)",
            TicketPriority.LOW: r"(low|minor|p3|priority[:\s]*3)",
        }

        for label in labels:
            label_name = label.get("name", "").lower()
            for priority, pattern in priority_patterns.items():
                if re.search(pattern, label_name, re.IGNORECASE):
                    return priority

        return TicketPriority.NONE

    def _parse_issue(self, data: dict[str, Any], owner: str, repo: str) -> TicketEntity:
        """Parse a GitHub issue into a TicketEntity.

        Args:
            data: Raw issue data from API
            owner: Repository owner
            repo: Repository name

        Returns:
            Parsed TicketEntity
        """
        labels_data = data.get("labels", [])
        labels = tuple(
            label.get("name", "") for label in labels_data if label.get("name")
        )

        created_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(
                data["created_at"].replace("Z", "+00:00")
            )

        updated_at = None
        if data.get("updated_at"):
            updated_at = datetime.fromisoformat(
                data["updated_at"].replace("Z", "+00:00")
            )

        assignee = None
        if data.get("assignee"):
            assignee = data["assignee"].get("login")

        milestone = None
        if data.get("milestone"):
            milestone = data["milestone"].get("title")

        issue_number = data.get("number", 0)
        identifier = f"{owner}/{repo}#{issue_number}"

        return TicketEntity(
            id=str(data.get("id", "")),
            source=TicketSource.GITHUB,
            identifier=identifier,
            title=data.get("title", ""),
            description=data.get("body", "") or "",
            status=normalize_github_status(data.get("state", "open")),
            priority=self._parse_priority_from_labels(labels_data),
            labels=labels,
            assignee=assignee,
            url=data.get("html_url", ""),
            created_at=created_at,
            updated_at=updated_at,
            project=f"{owner}/{repo}",
            milestone=milestone,
        )

    def _parse_comment(self, data: dict[str, Any]) -> TicketComment:
        """Parse a GitHub comment.

        Args:
            data: Raw comment data from API

        Returns:
            Parsed TicketComment
        """
        created_at = datetime.fromisoformat(
            data.get("created_at", "").replace("Z", "+00:00")
        )
        updated_at = None
        if data.get("updated_at"):
            updated_at = datetime.fromisoformat(
                data["updated_at"].replace("Z", "+00:00")
            )

        author = "Unknown"
        if data.get("user"):
            author = data["user"].get("login", "Unknown")

        return TicketComment(
            id=str(data.get("id", "")),
            author=author,
            body=data.get("body", ""),
            created_at=created_at,
            updated_at=updated_at,
        )

    def search_tickets(
        self,
        query: str | None = None,
        status: list[TicketStatus] | None = None,
        labels: list[str] | None = None,
        project: str | None = None,
        limit: int = 20,
    ) -> list[TicketEntity]:
        """Search for GitHub issues.

        Args:
            query: Text search query
            status: Filter by status
            labels: Filter by labels
            project: Filter by repo (owner/repo format)
            limit: Maximum results

        Returns:
            List of matching tickets
        """
        # Check cache first
        status_values = [s.value for s in status] if status else None
        cached = self._cache.get_search_results(
            query=query,
            status=status_values,
            labels=labels,
            source="github",
            project=project,
            limit=limit,
        )
        if cached is not None:
            return cached

        # Build search query
        search_parts = []

        if query:
            search_parts.append(query)

        # Add type filter
        search_parts.append("type:issue")

        # Add status filter
        if status:
            if TicketStatus.OPEN in status and TicketStatus.DONE not in status:
                search_parts.append("state:open")
            elif TicketStatus.DONE in status and TicketStatus.OPEN not in status:
                search_parts.append("state:closed")
            # If both or neither, don't filter by state

        # Add label filter
        if labels:
            for label in labels:
                search_parts.append(f'label:"{label}"')

        # Add repo filter
        if project and "/" in project:
            search_parts.append(f"repo:{project}")

        search_query = " ".join(search_parts)

        # Execute search
        params = {
            "q": search_query,
            "per_page": min(limit, 100),
            "sort": "updated",
            "order": "desc",
        }

        data = self._request("GET", "/search/issues", params)
        items = data.get("items", []) if isinstance(data, dict) else []

        # Parse results
        results = []
        for item in items:
            # Extract owner/repo from URL
            repo_url = item.get("repository_url", "")
            parts = repo_url.split("/")
            if len(parts) >= 2:
                owner = parts[-2]
                repo = parts[-1]
                results.append(self._parse_issue(item, owner, repo))

        # Limit results
        results = results[:limit]

        # Cache results
        self._cache.set_search_results(
            results=results,
            query=query,
            status=status_values,
            labels=labels,
            source="github",
            project=project,
            limit=limit,
        )

        return results

    def get_ticket(
        self,
        ticket_id: str,
        include_comments: bool = True,
        include_prs: bool = True,
    ) -> TicketEntity | None:
        """Get full GitHub issue details.

        Args:
            ticket_id: Issue identifier (e.g., "owner/repo#123" or issue ID)
            include_comments: Whether to include comments
            include_prs: Whether to include linked PRs

        Returns:
            Full ticket details or None if not found
        """
        # Check cache first
        cached = self._cache.get_ticket(ticket_id, "github")
        if cached is not None:
            return cached

        # Parse identifier
        parsed = parse_github_identifier(ticket_id)
        if not parsed:
            # Try to find by issue ID (less common)
            return None

        owner, repo, issue_number = parsed

        # Get issue
        try:
            data = self._request("GET", f"/repos/{owner}/{repo}/issues/{issue_number}")
        except requests.HTTPError as e:
            if "404" in str(e):
                return None
            raise

        if not isinstance(data, dict):
            return None

        # Parse base ticket
        ticket = self._parse_issue(data, owner, repo)

        # Get comments if requested
        comments: tuple[TicketComment, ...] = ()
        if include_comments:
            try:
                comments_data = self._request(
                    "GET",
                    f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
                    {"per_page": 100},
                )
                if isinstance(comments_data, list):
                    comments = tuple(self._parse_comment(c) for c in comments_data)
            except requests.HTTPError:
                pass  # Ignore comment fetch errors

        # Find linked PRs from issue body and timeline
        linked_prs: tuple[str, ...] = ()
        if include_prs:
            pr_urls = self._extract_pr_links(ticket.description, owner, repo)
            linked_prs = tuple(pr_urls)

        # Create full ticket with comments and PRs
        full_ticket = TicketEntity(
            id=ticket.id,
            source=ticket.source,
            identifier=ticket.identifier,
            title=ticket.title,
            description=ticket.description,
            status=ticket.status,
            priority=ticket.priority,
            labels=ticket.labels,
            assignee=ticket.assignee,
            url=ticket.url,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            comments=comments,
            linked_prs=linked_prs,
            project=ticket.project,
            milestone=ticket.milestone,
        )

        # Cache the result
        self._cache.set_ticket(full_ticket)

        return full_ticket

    def _extract_pr_links(self, text: str, owner: str, repo: str) -> list[str]:
        """Extract PR links from issue text.

        Args:
            text: Issue body text
            owner: Repository owner
            repo: Repository name

        Returns:
            List of PR URLs
        """
        pr_urls = []

        # Match full GitHub PR URLs
        url_pattern = r"https://github\.com/[\w\-]+/[\w\-]+/pull/\d+"
        pr_urls.extend(re.findall(url_pattern, text))

        # Match #123 style references (same repo)
        ref_pattern = r"#(\d+)"
        for match in re.finditer(ref_pattern, text):
            pr_num = match.group(1)
            pr_urls.append(f"https://github.com/{owner}/{repo}/pull/{pr_num}")

        return list(set(pr_urls))  # Deduplicate

    def list_projects(self) -> list[dict[str, str]]:
        """List accessible GitHub repositories.

        Returns:
            List of repos with id, name, and full_name
        """
        data = self._request("GET", "/user/repos", {"per_page": 100, "sort": "updated"})

        if not isinstance(data, list):
            return []

        return [
            {
                "id": str(repo.get("id", "")),
                "name": repo.get("name", ""),
                "full_name": repo.get("full_name", ""),
            }
            for repo in data
        ]

    def get_repo_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        limit: int = 30,
    ) -> list[TicketEntity]:
        """Get issues from a specific repository.

        Args:
            owner: Repository owner
            repo: Repository name
            state: Issue state filter (open, closed, all)
            limit: Maximum results

        Returns:
            List of issues
        """
        params = {
            "state": state,
            "per_page": min(limit, 100),
            "sort": "updated",
            "direction": "desc",
        }

        data = self._request("GET", f"/repos/{owner}/{repo}/issues", params)

        if not isinstance(data, list):
            return []

        # Filter out pull requests (they also appear in issues endpoint)
        issues = [item for item in data if "pull_request" not in item]

        return [self._parse_issue(issue, owner, repo) for issue in issues[:limit]]

    def invalidate_cache(self) -> int:
        """Invalidate all cached GitHub data.

        Returns:
            Number of entries invalidated
        """
        return self._cache.invalidate(source="github")
