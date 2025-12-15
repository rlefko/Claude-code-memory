"""Tests for ticket integration models (Milestone 8.3)."""

from datetime import datetime

import pytest

from claude_indexer.integrations.models import (
    TicketComment,
    TicketEntity,
    TicketPriority,
    TicketSource,
    TicketStatus,
    infer_github_priority,
    normalize_github_status,
    normalize_linear_priority,
    normalize_linear_status,
)


class TestTicketEnums:
    """Test ticket enumeration types."""

    def test_ticket_source_values(self):
        """Test TicketSource enum has expected values."""
        assert TicketSource.LINEAR.value == "linear"
        assert TicketSource.GITHUB.value == "github"

    def test_ticket_status_values(self):
        """Test TicketStatus enum has expected values."""
        assert TicketStatus.OPEN.value == "open"
        assert TicketStatus.IN_PROGRESS.value == "in_progress"
        assert TicketStatus.DONE.value == "done"
        assert TicketStatus.CANCELLED.value == "cancelled"

    def test_ticket_priority_values(self):
        """Test TicketPriority enum has expected values."""
        assert TicketPriority.URGENT.value == "urgent"
        assert TicketPriority.HIGH.value == "high"
        assert TicketPriority.MEDIUM.value == "medium"
        assert TicketPriority.LOW.value == "low"
        assert TicketPriority.NONE.value == "none"


class TestTicketComment:
    """Test TicketComment dataclass."""

    def test_basic_comment(self):
        """Test creating a basic comment."""
        created = datetime(2024, 1, 15, 10, 30, 0)
        comment = TicketComment(
            id="comment-1",
            author="user@example.com",
            body="This is a test comment",
            created_at=created,
        )
        assert comment.id == "comment-1"
        assert comment.author == "user@example.com"
        assert comment.body == "This is a test comment"
        assert comment.created_at == created
        assert comment.updated_at is None

    def test_comment_with_updated_at(self):
        """Test comment with updated_at field."""
        created = datetime(2024, 1, 15, 10, 30, 0)
        updated = datetime(2024, 1, 15, 11, 0, 0)
        comment = TicketComment(
            id="comment-2",
            author="user@example.com",
            body="Updated comment",
            created_at=created,
            updated_at=updated,
        )
        assert comment.updated_at == updated

    def test_comment_to_dict(self):
        """Test converting comment to dictionary."""
        created = datetime(2024, 1, 15, 10, 30, 0)
        comment = TicketComment(
            id="comment-1",
            author="user@example.com",
            body="Test",
            created_at=created,
        )
        d = comment.to_dict()
        assert d["id"] == "comment-1"
        assert d["author"] == "user@example.com"
        assert d["body"] == "Test"
        assert "2024-01-15" in d["created_at"]


class TestTicketEntity:
    """Test TicketEntity dataclass."""

    @pytest.fixture
    def sample_ticket(self) -> TicketEntity:
        """Create a sample ticket for testing."""
        return TicketEntity(
            id="ticket-123",
            source=TicketSource.LINEAR,
            identifier="AVO-123",
            title="Fix authentication bug",
            description="Users cannot login with SSO",
            status=TicketStatus.OPEN,
            priority=TicketPriority.HIGH,
            labels=("bug", "auth"),
            url="https://linear.app/team/issue/AVO-123",
        )

    def test_ticket_creation(self, sample_ticket):
        """Test basic ticket creation."""
        assert sample_ticket.id == "ticket-123"
        assert sample_ticket.source == TicketSource.LINEAR
        assert sample_ticket.identifier == "AVO-123"
        assert sample_ticket.title == "Fix authentication bug"
        assert sample_ticket.status == TicketStatus.OPEN
        assert sample_ticket.priority == TicketPriority.HIGH
        assert sample_ticket.labels == ("bug", "auth")

    def test_ticket_with_comments(self):
        """Test ticket with comments."""
        created = datetime(2024, 1, 15, 10, 30, 0)
        comment = TicketComment(
            id="c1",
            author="dev@example.com",
            body="Looking into this",
            created_at=created,
        )
        ticket = TicketEntity(
            id="ticket-123",
            source=TicketSource.GITHUB,
            identifier="owner/repo#456",
            title="Add feature",
            description="Feature description",
            status=TicketStatus.IN_PROGRESS,
            priority=TicketPriority.MEDIUM,
            labels=("enhancement",),
            url="https://github.com/owner/repo/issues/456",
            comments=(comment,),
        )
        assert len(ticket.comments) == 1
        assert ticket.comments[0].author == "dev@example.com"

    def test_ticket_with_linked_prs(self):
        """Test ticket with linked PRs."""
        ticket = TicketEntity(
            id="ticket-123",
            source=TicketSource.GITHUB,
            identifier="owner/repo#456",
            title="Bug fix",
            description="Fix the bug",
            status=TicketStatus.DONE,
            priority=TicketPriority.LOW,
            labels=(),
            url="https://github.com/owner/repo/issues/456",
            linked_prs=("owner/repo#457", "owner/repo#458"),
        )
        assert ticket.linked_prs == ("owner/repo#457", "owner/repo#458")

    def test_to_search_result(self, sample_ticket):
        """Test converting ticket to search result format."""
        result = sample_ticket.to_search_result(score=0.95)
        assert result["type"] == "ticket"
        assert result["score"] == 0.95
        assert result["data"]["id"] == "ticket-123"
        assert result["data"]["identifier"] == "AVO-123"
        assert result["data"]["source"] == "linear"
        assert result["data"]["title"] == "Fix authentication bug"
        assert result["data"]["status"] == "open"
        assert result["data"]["priority"] == "high"
        assert result["data"]["labels"] == ["bug", "auth"]
        assert "content_preview" in result["data"]

    def test_to_dict(self, sample_ticket):
        """Test converting ticket to full dictionary."""
        d = sample_ticket.to_dict()
        assert d["id"] == "ticket-123"
        assert d["source"] == "linear"
        assert d["identifier"] == "AVO-123"
        assert d["title"] == "Fix authentication bug"
        assert d["description"] == "Users cannot login with SSO"
        assert d["status"] == "open"
        assert d["priority"] == "high"
        assert d["labels"] == ["bug", "auth"]
        assert d["comments"] == []
        assert d["linked_prs"] == []

    def test_to_vector_content(self, sample_ticket):
        """Test generating vector content for embedding."""
        content = sample_ticket.to_vector_content()
        assert "AVO-123" in content
        assert "Fix authentication bug" in content
        assert "Users cannot login with SSO" in content
        assert "bug" in content
        assert "auth" in content

    def test_content_preview_truncation(self):
        """Test that content preview is truncated properly."""
        long_description = "A" * 500
        ticket = TicketEntity(
            id="ticket-123",
            source=TicketSource.LINEAR,
            identifier="AVO-123",
            title="Test",
            description=long_description,
            status=TicketStatus.OPEN,
            priority=TicketPriority.MEDIUM,
            labels=(),
            url="https://example.com",
        )
        result = ticket.to_search_result()
        preview = result["data"]["content_preview"]
        assert len(preview) <= 203  # 200 + "..."
        assert preview.endswith("...")


class TestStatusNormalization:
    """Test status normalization functions."""

    def test_normalize_linear_status_todo(self):
        """Test Linear 'Todo' status normalization."""
        assert normalize_linear_status("Todo") == TicketStatus.OPEN
        assert normalize_linear_status("Backlog") == TicketStatus.OPEN
        assert normalize_linear_status("Triage") == TicketStatus.OPEN

    def test_normalize_linear_status_in_progress(self):
        """Test Linear in-progress status normalization."""
        assert normalize_linear_status("In Progress") == TicketStatus.IN_PROGRESS
        assert normalize_linear_status("In Review") == TicketStatus.IN_PROGRESS

    def test_normalize_linear_status_done(self):
        """Test Linear done status normalization."""
        assert normalize_linear_status("Done") == TicketStatus.DONE
        assert normalize_linear_status("Completed") == TicketStatus.DONE

    def test_normalize_linear_status_cancelled(self):
        """Test Linear cancelled status normalization."""
        assert normalize_linear_status("Canceled") == TicketStatus.CANCELLED
        assert normalize_linear_status("Cancelled") == TicketStatus.CANCELLED
        assert normalize_linear_status("Duplicate") == TicketStatus.CANCELLED

    def test_normalize_linear_status_unknown(self):
        """Test Linear unknown status defaults to open."""
        assert normalize_linear_status("SomeCustomStatus") == TicketStatus.OPEN

    def test_normalize_github_status(self):
        """Test GitHub status normalization."""
        assert normalize_github_status("open") == TicketStatus.OPEN
        assert normalize_github_status("closed") == TicketStatus.DONE


class TestPriorityNormalization:
    """Test priority normalization functions."""

    def test_normalize_linear_priority(self):
        """Test Linear priority normalization (0=none, 1=urgent, 4=low)."""
        assert normalize_linear_priority(0) == TicketPriority.NONE
        assert normalize_linear_priority(1) == TicketPriority.URGENT
        assert normalize_linear_priority(2) == TicketPriority.HIGH
        assert normalize_linear_priority(3) == TicketPriority.MEDIUM
        assert normalize_linear_priority(4) == TicketPriority.LOW

    def test_normalize_linear_priority_invalid(self):
        """Test Linear priority normalization with invalid values."""
        assert normalize_linear_priority(5) == TicketPriority.NONE
        assert normalize_linear_priority(-1) == TicketPriority.NONE

    def test_infer_github_priority_from_labels(self):
        """Test inferring GitHub priority from labels."""
        assert infer_github_priority(["P0", "bug"]) == TicketPriority.URGENT
        assert infer_github_priority(["priority: critical"]) == TicketPriority.URGENT
        assert infer_github_priority(["P1", "enhancement"]) == TicketPriority.HIGH
        assert infer_github_priority(["priority: high"]) == TicketPriority.HIGH
        assert infer_github_priority(["P2"]) == TicketPriority.MEDIUM
        assert infer_github_priority(["P3"]) == TicketPriority.LOW
        assert infer_github_priority(["bug", "enhancement"]) == TicketPriority.NONE
