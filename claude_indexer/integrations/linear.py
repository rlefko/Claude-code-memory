"""Linear issue tracker integration.

This module provides a client for the Linear GraphQL API,
enabling search and retrieval of issues.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import requests

from .base import IntegrationClient
from .cache import TicketCache
from .models import (
    TicketComment,
    TicketEntity,
    TicketSource,
    TicketStatus,
    normalize_linear_priority,
    normalize_linear_status,
)


class LinearClient(IntegrationClient):
    """Client for Linear GraphQL API.

    Provides search and retrieval of Linear issues with
    rate limiting, retry logic, and caching.
    """

    GRAPHQL_ENDPOINT = "https://api.linear.app/graphql"

    # GraphQL query for searching issues
    SEARCH_QUERY = """
    query SearchIssues(
      $query: String,
      $teamIds: [String!],
      $limit: Int,
      $includeArchived: Boolean
    ) {
      issues(
        filter: {
          or: [
            { title: { containsIgnoreCase: $query } }
            { description: { containsIgnoreCase: $query } }
          ]
          team: { id: { in: $teamIds } }
        }
        first: $limit
        includeArchived: $includeArchived
      ) {
        nodes {
          id
          identifier
          title
          description
          state {
            name
            type
          }
          priority
          labels {
            nodes {
              name
            }
          }
          assignee {
            name
          }
          url
          createdAt
          updatedAt
          project {
            name
          }
          team {
            name
          }
        }
      }
    }
    """

    # GraphQL query for getting a single issue with comments
    GET_ISSUE_QUERY = """
    query GetIssue($id: String!) {
      issue(id: $id) {
        id
        identifier
        title
        description
        state {
          name
          type
        }
        priority
        labels {
          nodes {
            name
          }
        }
        assignee {
          name
        }
        url
        createdAt
        updatedAt
        project {
          name
        }
        team {
          name
        }
        comments {
          nodes {
            id
            body
            user {
              name
            }
            createdAt
            updatedAt
          }
        }
        attachments {
          nodes {
            url
            title
          }
        }
      }
    }
    """

    # GraphQL query for listing teams
    LIST_TEAMS_QUERY = """
    query ListTeams {
      teams {
        nodes {
          id
          name
          key
        }
      }
    }
    """

    def __init__(
        self,
        api_key: str | None = None,
        cache_ttl_seconds: float = 300.0,
        max_retries: int = 3,
    ):
        """Initialize Linear client.

        Args:
            api_key: Linear API key (defaults to LINEAR_API_KEY env var)
            cache_ttl_seconds: Cache TTL in seconds
            max_retries: Maximum retry attempts
        """
        api_key = api_key or os.environ.get("LINEAR_API_KEY", "")
        if not api_key:
            raise ValueError(
                "Linear API key required. Set LINEAR_API_KEY environment variable "
                "or pass api_key parameter."
            )

        super().__init__(
            api_key=api_key,
            max_retries=max_retries,
            requests_per_minute=60,  # Linear rate limit
        )

        self._cache = TicketCache(ttl_seconds=cache_ttl_seconds)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": api_key,
                "Content-Type": "application/json",
            }
        )

    @property
    def source(self) -> TicketSource:
        """Return the ticket source."""
        return TicketSource.LINEAR

    def _execute_graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """Execute a GraphQL query against the Linear API.

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            Response data

        Raises:
            requests.HTTPError: If request fails
        """

        def _do_request() -> dict[str, Any]:
            response = self._session.post(
                self.GRAPHQL_ENDPOINT,
                json={"query": query, "variables": variables},
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()

            if "errors" in result:
                error_msg = result["errors"][0].get("message", "Unknown GraphQL error")
                raise requests.HTTPError(f"GraphQL error: {error_msg}")

            return result.get("data", {})

        return self._execute_with_retry(_do_request)

    def _parse_issue(self, node: dict[str, Any]) -> TicketEntity:
        """Parse a Linear issue node into a TicketEntity.

        Args:
            node: Raw issue data from GraphQL

        Returns:
            Parsed TicketEntity
        """
        state = node.get("state", {})
        labels_data = node.get("labels", {}).get("nodes", [])
        labels = tuple(
            label.get("name", "") for label in labels_data if label.get("name")
        )

        created_at = None
        if node.get("createdAt"):
            created_at = datetime.fromisoformat(
                node["createdAt"].replace("Z", "+00:00")
            )

        updated_at = None
        if node.get("updatedAt"):
            updated_at = datetime.fromisoformat(
                node["updatedAt"].replace("Z", "+00:00")
            )

        assignee = None
        if node.get("assignee"):
            assignee = node["assignee"].get("name")

        project = None
        if node.get("project"):
            project = node["project"].get("name")

        team = None
        if node.get("team"):
            team = node["team"].get("name")

        return TicketEntity(
            id=node.get("id", ""),
            source=TicketSource.LINEAR,
            identifier=node.get("identifier", ""),
            title=node.get("title", ""),
            description=node.get("description", "") or "",
            status=normalize_linear_status(state.get("name", ""), state.get("type")),
            priority=normalize_linear_priority(node.get("priority")),
            labels=labels,
            assignee=assignee,
            url=node.get("url", ""),
            created_at=created_at,
            updated_at=updated_at,
            project=project,
            team=team,
        )

    def _parse_comment(self, node: dict[str, Any]) -> TicketComment:
        """Parse a Linear comment node.

        Args:
            node: Raw comment data from GraphQL

        Returns:
            Parsed TicketComment
        """
        created_at = datetime.fromisoformat(
            node.get("createdAt", "").replace("Z", "+00:00")
        )
        updated_at = None
        if node.get("updatedAt"):
            updated_at = datetime.fromisoformat(
                node["updatedAt"].replace("Z", "+00:00")
            )

        author = "Unknown"
        if node.get("user"):
            author = node["user"].get("name", "Unknown")

        return TicketComment(
            id=node.get("id", ""),
            author=author,
            body=node.get("body", ""),
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
        """Search for Linear issues.

        Args:
            query: Text search query
            status: Filter by status (not directly supported, filtered post-query)
            labels: Filter by labels (not directly supported, filtered post-query)
            project: Filter by project
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
            source="linear",
            project=project,
            limit=limit,
        )
        if cached is not None:
            return cached

        # Build variables
        variables: dict[str, Any] = {
            "limit": min(limit * 2, 100),  # Fetch extra for post-filtering
            "includeArchived": False,
        }

        if query:
            variables["query"] = query

        # Execute query
        data = self._execute_graphql(self.SEARCH_QUERY, variables)
        issues_data = data.get("issues", {}).get("nodes", [])

        # Parse results
        results = [self._parse_issue(node) for node in issues_data]

        # Apply filters
        if status:
            results = [t for t in results if t.status in status]
        if labels:
            label_set = set(labels)
            results = [t for t in results if label_set.intersection(t.labels)]
        if project:
            results = [t for t in results if t.project == project]

        # Limit results
        results = results[:limit]

        # Cache results
        self._cache.set_search_results(
            results=results,
            query=query,
            status=status_values,
            labels=labels,
            source="linear",
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
        """Get full Linear issue details.

        Args:
            ticket_id: Linear issue ID or identifier (e.g., "AVO-123")
            include_comments: Whether to include comments
            include_prs: Whether to include linked PRs (via attachments)

        Returns:
            Full ticket details or None if not found
        """
        # Check cache first
        cached = self._cache.get_ticket(ticket_id, "linear")
        if cached is not None:
            return cached

        # Execute query
        try:
            data = self._execute_graphql(self.GET_ISSUE_QUERY, {"id": ticket_id})
        except requests.HTTPError as e:
            if "404" in str(e) or "not found" in str(e).lower():
                return None
            raise

        issue_data = data.get("issue")
        if not issue_data:
            return None

        # Parse base ticket
        ticket = self._parse_issue(issue_data)

        # Parse comments if requested
        comments: tuple[TicketComment, ...] = ()
        if include_comments:
            comments_data = issue_data.get("comments", {}).get("nodes", [])
            comments = tuple(self._parse_comment(c) for c in comments_data)

        # Extract PR links from attachments if requested
        linked_prs: tuple[str, ...] = ()
        if include_prs:
            attachments = issue_data.get("attachments", {}).get("nodes", [])
            pr_urls = [
                att.get("url", "")
                for att in attachments
                if att.get("url", "").startswith("https://github.com")
                and "/pull/" in att.get("url", "")
            ]
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
            team=ticket.team,
        )

        # Cache the result
        self._cache.set_ticket(full_ticket)

        return full_ticket

    def list_projects(self) -> list[dict[str, str]]:
        """List available Linear teams (as projects).

        Returns:
            List of teams with id, name, and key
        """
        data = self._execute_graphql(self.LIST_TEAMS_QUERY, {})
        teams = data.get("teams", {}).get("nodes", [])

        return [
            {
                "id": team.get("id", ""),
                "name": team.get("name", ""),
                "key": team.get("key", ""),
            }
            for team in teams
        ]

    def invalidate_cache(self) -> int:
        """Invalidate all cached Linear data.

        Returns:
            Number of entries invalidated
        """
        return self._cache.invalidate(source="linear")
