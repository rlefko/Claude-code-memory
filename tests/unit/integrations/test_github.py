"""Tests for GitHub Issues client (Milestone 8.3)."""

import os
from unittest.mock import patch

import pytest

from claude_indexer.integrations.models import TicketPriority, TicketStatus


class TestGitHubClientBasics:
    """Test basic GitHubIssuesClient functionality."""

    def test_import_succeeds(self):
        """Test that GitHubIssuesClient can be imported."""
        from claude_indexer.integrations.github import GitHubIssuesClient

        assert GitHubIssuesClient is not None

    def test_init_requires_token(self):
        """Test that initialization requires a token."""
        from claude_indexer.integrations.github import GitHubIssuesClient

        # Clear environment variable if set
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="GitHub token required"):
                GitHubIssuesClient()

    def test_init_with_env_var(self):
        """Test initialization with environment variable."""
        from claude_indexer.integrations.github import GitHubIssuesClient

        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test-key"}):
            client = GitHubIssuesClient()
            assert client.api_key == "ghp_test-key"

    def test_init_with_token_param(self):
        """Test initialization with explicit token parameter."""
        from claude_indexer.integrations.github import GitHubIssuesClient

        with patch.dict(os.environ, {}, clear=True):
            client = GitHubIssuesClient(token="ghp_my-token")
            assert client.api_key == "ghp_my-token"

    def test_api_base_url(self):
        """Test API base URL is correct."""
        from claude_indexer.integrations.github import GitHubIssuesClient

        assert GitHubIssuesClient.API_BASE == "https://api.github.com"

    def test_source_property(self):
        """Test source property returns GITHUB."""
        from claude_indexer.integrations.github import GitHubIssuesClient
        from claude_indexer.integrations.models import TicketSource

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}):
            client = GitHubIssuesClient()
            assert client.source == TicketSource.GITHUB


class TestGitHubStatusNormalization:
    """Test GitHub status normalization."""

    def test_open_is_open(self):
        """Test open state normalizes to open."""
        from claude_indexer.integrations.models import normalize_github_status

        assert normalize_github_status("open") == TicketStatus.OPEN

    def test_closed_is_done(self):
        """Test closed state normalizes to done."""
        from claude_indexer.integrations.models import normalize_github_status

        assert normalize_github_status("closed") == TicketStatus.DONE


class TestGitHubPriorityInference:
    """Test GitHub priority inference from labels."""

    def test_p0_is_urgent(self):
        """Test P0 label infers urgent priority."""
        from claude_indexer.integrations.models import infer_github_priority

        assert infer_github_priority(["P0"]) == TicketPriority.URGENT

    def test_critical_is_urgent(self):
        """Test critical label infers urgent priority."""
        from claude_indexer.integrations.models import infer_github_priority

        assert infer_github_priority(["critical"]) == TicketPriority.URGENT

    def test_p1_is_high(self):
        """Test P1 label infers high priority."""
        from claude_indexer.integrations.models import infer_github_priority

        assert infer_github_priority(["P1"]) == TicketPriority.HIGH

    def test_high_is_high(self):
        """Test high-priority label infers high priority."""
        from claude_indexer.integrations.models import infer_github_priority

        assert infer_github_priority(["high-priority"]) == TicketPriority.HIGH

    def test_p2_is_medium(self):
        """Test P2 label infers medium priority."""
        from claude_indexer.integrations.models import infer_github_priority

        assert infer_github_priority(["P2"]) == TicketPriority.MEDIUM

    def test_p3_is_low(self):
        """Test P3 label infers low priority."""
        from claude_indexer.integrations.models import infer_github_priority

        assert infer_github_priority(["P3"]) == TicketPriority.LOW

    def test_no_priority_labels_is_none(self):
        """Test no priority labels results in NONE."""
        from claude_indexer.integrations.models import infer_github_priority

        assert infer_github_priority(["bug", "enhancement"]) == TicketPriority.NONE

    def test_empty_labels_is_none(self):
        """Test empty labels results in NONE."""
        from claude_indexer.integrations.models import infer_github_priority

        assert infer_github_priority([]) == TicketPriority.NONE


class TestGitHubIdentifierParsing:
    """Test GitHub identifier parsing."""

    def test_parse_valid_identifier(self):
        """Test parsing valid owner/repo#number format."""
        from claude_indexer.integrations.models import parse_github_identifier

        result = parse_github_identifier("owner/repo#123")
        assert result == ("owner", "repo", 123)

    def test_parse_identifier_with_org(self):
        """Test parsing identifier with organization."""
        from claude_indexer.integrations.models import parse_github_identifier

        result = parse_github_identifier("my-org/my-repo#456")
        assert result == ("my-org", "my-repo", 456)

    def test_parse_invalid_identifier_no_hash(self):
        """Test parsing invalid identifier without hash returns None."""
        from claude_indexer.integrations.models import parse_github_identifier

        result = parse_github_identifier("owner/repo123")
        assert result is None

    def test_parse_invalid_identifier_no_slash(self):
        """Test parsing identifier without slash returns None for repo."""
        from claude_indexer.integrations.models import parse_github_identifier

        result = parse_github_identifier("#123")
        assert result is None
