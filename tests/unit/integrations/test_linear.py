"""Tests for Linear client (Milestone 8.3)."""

import os
from unittest.mock import patch

import pytest

from claude_indexer.integrations.models import TicketPriority, TicketStatus


class TestLinearClientBasics:
    """Test basic LinearClient functionality."""

    def test_import_succeeds(self):
        """Test that LinearClient can be imported."""
        from claude_indexer.integrations.linear import LinearClient

        assert LinearClient is not None

    def test_init_requires_api_key(self):
        """Test that initialization requires an API key."""
        from claude_indexer.integrations.linear import LinearClient

        # Clear environment variable if set
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="LINEAR_API_KEY"):
                LinearClient()

    def test_init_with_env_var(self):
        """Test initialization with environment variable."""
        from claude_indexer.integrations.linear import LinearClient

        with patch.dict(os.environ, {"LINEAR_API_KEY": "test-key"}):
            client = LinearClient()
            assert client.api_key == "test-key"

    def test_init_with_api_key_param(self):
        """Test initialization with explicit api_key parameter."""
        from claude_indexer.integrations.linear import LinearClient

        with patch.dict(os.environ, {}, clear=True):
            client = LinearClient(api_key="my-token")
            assert client.api_key == "my-token"

    def test_graphql_endpoint(self):
        """Test GraphQL endpoint is correct."""
        from claude_indexer.integrations.linear import LinearClient

        assert LinearClient.GRAPHQL_ENDPOINT == "https://api.linear.app/graphql"

    def test_source_property(self):
        """Test source property returns LINEAR."""
        from claude_indexer.integrations.linear import LinearClient
        from claude_indexer.integrations.models import TicketSource

        with patch.dict(os.environ, {"LINEAR_API_KEY": "test-key"}):
            client = LinearClient()
            assert client.source == TicketSource.LINEAR


class TestLinearStatusNormalization:
    """Test Linear status normalization (moved from models tests for clarity)."""

    def test_backlog_is_open(self):
        """Test backlog state normalizes to open."""
        from claude_indexer.integrations.models import normalize_linear_status

        assert normalize_linear_status("Backlog") == TicketStatus.OPEN

    def test_todo_is_open(self):
        """Test todo state normalizes to open."""
        from claude_indexer.integrations.models import normalize_linear_status

        assert normalize_linear_status("Todo") == TicketStatus.OPEN

    def test_in_progress(self):
        """Test in progress state normalization."""
        from claude_indexer.integrations.models import normalize_linear_status

        assert normalize_linear_status("In Progress") == TicketStatus.IN_PROGRESS

    def test_done_is_done(self):
        """Test done state normalizes correctly."""
        from claude_indexer.integrations.models import normalize_linear_status

        assert normalize_linear_status("Done") == TicketStatus.DONE

    def test_canceled_is_cancelled(self):
        """Test canceled state normalization."""
        from claude_indexer.integrations.models import normalize_linear_status

        assert normalize_linear_status("Canceled") == TicketStatus.CANCELLED


class TestLinearPriorityNormalization:
    """Test Linear priority normalization."""

    def test_priority_0_is_none(self):
        """Test priority 0 (no priority) normalizes correctly."""
        from claude_indexer.integrations.models import normalize_linear_priority

        assert normalize_linear_priority(0) == TicketPriority.NONE

    def test_priority_1_is_urgent(self):
        """Test priority 1 (urgent) normalizes correctly."""
        from claude_indexer.integrations.models import normalize_linear_priority

        assert normalize_linear_priority(1) == TicketPriority.URGENT

    def test_priority_2_is_high(self):
        """Test priority 2 (high) normalizes correctly."""
        from claude_indexer.integrations.models import normalize_linear_priority

        assert normalize_linear_priority(2) == TicketPriority.HIGH

    def test_priority_3_is_medium(self):
        """Test priority 3 (medium) normalizes correctly."""
        from claude_indexer.integrations.models import normalize_linear_priority

        assert normalize_linear_priority(3) == TicketPriority.MEDIUM

    def test_priority_4_is_low(self):
        """Test priority 4 (low) normalizes correctly."""
        from claude_indexer.integrations.models import normalize_linear_priority

        assert normalize_linear_priority(4) == TicketPriority.LOW

    def test_priority_none_defaults_to_none(self):
        """Test None priority defaults to NONE."""
        from claude_indexer.integrations.models import normalize_linear_priority

        assert normalize_linear_priority(None) == TicketPriority.NONE
