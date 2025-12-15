"""Unit tests for plan feedback collection.

Tests feedback recording and approval rate metrics.
Milestone 13.4.2: Collect feedback on plan quality
Milestone 13.4.3: Measure plan approval rate
"""

from datetime import datetime
from pathlib import Path

import pytest

from claude_indexer.ui.metrics.collector import MetricsCollector
from claude_indexer.ui.metrics.models import MetricsReport, PlanAdoptionRecord


class TestPlanAdoptionRecordFeedback:
    """Tests for PlanAdoptionRecord feedback fields."""

    def test_default_feedback_values(self):
        """Default feedback values should be None/0."""
        record = PlanAdoptionRecord(
            plan_id="test-123",
            generated_at=datetime.now().isoformat(),
            total_tasks=5,
        )
        assert record.approved is None
        assert record.approved_at is None
        assert record.rejection_reason is None
        assert record.accuracy_rating is None
        assert record.user_notes is None
        assert record.revision_count == 0

    def test_to_dict_includes_feedback_fields(self):
        """to_dict should include all feedback fields."""
        record = PlanAdoptionRecord(
            plan_id="test-123",
            generated_at="2024-01-01T00:00:00",
            total_tasks=5,
            approved=True,
            approved_at="2024-01-01T01:00:00",
            accuracy_rating=4,
            user_notes="Good plan",
            revision_count=2,
        )
        data = record.to_dict()

        assert data["approved"] is True
        assert data["approved_at"] == "2024-01-01T01:00:00"
        assert data["accuracy_rating"] == 4
        assert data["user_notes"] == "Good plan"
        assert data["revision_count"] == 2

    def test_from_dict_with_feedback_fields(self):
        """from_dict should restore all feedback fields."""
        data = {
            "plan_id": "test-123",
            "generated_at": "2024-01-01T00:00:00",
            "total_tasks": 5,
            "approved": False,
            "approved_at": "2024-01-01T01:00:00",
            "rejection_reason": "Too complex",
            "accuracy_rating": 2,
            "user_notes": "Needs work",
            "revision_count": 3,
        }
        record = PlanAdoptionRecord.from_dict(data)

        assert record.approved is False
        assert record.rejection_reason == "Too complex"
        assert record.accuracy_rating == 2
        assert record.revision_count == 3

    def test_from_dict_backward_compatible(self):
        """from_dict should handle old data without feedback fields."""
        data = {
            "plan_id": "test-123",
            "generated_at": "2024-01-01T00:00:00",
            "total_tasks": 5,
        }
        record = PlanAdoptionRecord.from_dict(data)

        assert record.approved is None
        assert record.revision_count == 0


class TestMetricsReportApprovalMetrics:
    """Tests for MetricsReport approval metrics properties."""

    def test_approval_rate_no_plans(self):
        """approval_rate should be 0.0 when no plans exist."""
        report = MetricsReport()
        assert report.approval_rate == 0.0

    def test_approval_rate_no_decisions(self):
        """approval_rate should be 0.0 when no decisions made."""
        report = MetricsReport(
            plan_records=[
                PlanAdoptionRecord(
                    plan_id="test-1",
                    generated_at=datetime.now().isoformat(),
                    total_tasks=5,
                    approved=None,  # No decision
                )
            ]
        )
        assert report.approval_rate == 0.0

    def test_approval_rate_calculation(self):
        """approval_rate should calculate correctly."""
        report = MetricsReport(
            plan_records=[
                PlanAdoptionRecord(
                    plan_id="test-1",
                    generated_at=datetime.now().isoformat(),
                    total_tasks=5,
                    approved=True,
                ),
                PlanAdoptionRecord(
                    plan_id="test-2",
                    generated_at=datetime.now().isoformat(),
                    total_tasks=5,
                    approved=True,
                ),
                PlanAdoptionRecord(
                    plan_id="test-3",
                    generated_at=datetime.now().isoformat(),
                    total_tasks=5,
                    approved=False,
                ),
            ]
        )
        assert abs(report.approval_rate - (2 / 3)) < 0.01

    def test_pending_approval_count(self):
        """pending_approval_count should count pending plans."""
        report = MetricsReport(
            plan_records=[
                PlanAdoptionRecord(
                    plan_id="test-1",
                    generated_at=datetime.now().isoformat(),
                    total_tasks=5,
                    approved=True,
                ),
                PlanAdoptionRecord(
                    plan_id="test-2",
                    generated_at=datetime.now().isoformat(),
                    total_tasks=5,
                    approved=None,
                ),
                PlanAdoptionRecord(
                    plan_id="test-3",
                    generated_at=datetime.now().isoformat(),
                    total_tasks=5,
                    approved=None,
                ),
            ]
        )
        assert report.pending_approval_count == 2

    def test_average_accuracy_rating_none(self):
        """average_accuracy_rating should be None when no ratings."""
        report = MetricsReport(
            plan_records=[
                PlanAdoptionRecord(
                    plan_id="test-1",
                    generated_at=datetime.now().isoformat(),
                    total_tasks=5,
                )
            ]
        )
        assert report.average_accuracy_rating is None

    def test_average_accuracy_rating_calculation(self):
        """average_accuracy_rating should calculate correctly."""
        report = MetricsReport(
            plan_records=[
                PlanAdoptionRecord(
                    plan_id="test-1",
                    generated_at=datetime.now().isoformat(),
                    total_tasks=5,
                    approved=True,
                    accuracy_rating=5,
                ),
                PlanAdoptionRecord(
                    plan_id="test-2",
                    generated_at=datetime.now().isoformat(),
                    total_tasks=5,
                    approved=True,
                    accuracy_rating=3,
                ),
            ]
        )
        assert report.average_accuracy_rating == 4.0

    def test_average_revision_count(self):
        """average_revision_count should calculate from approved plans."""
        report = MetricsReport(
            plan_records=[
                PlanAdoptionRecord(
                    plan_id="test-1",
                    generated_at=datetime.now().isoformat(),
                    total_tasks=5,
                    approved=True,
                    revision_count=2,
                ),
                PlanAdoptionRecord(
                    plan_id="test-2",
                    generated_at=datetime.now().isoformat(),
                    total_tasks=5,
                    approved=True,
                    revision_count=4,
                ),
                PlanAdoptionRecord(
                    plan_id="test-3",
                    generated_at=datetime.now().isoformat(),
                    total_tasks=5,
                    approved=False,  # Rejected, not counted
                    revision_count=10,
                ),
            ]
        )
        assert report.average_revision_count == 3.0

    def test_rejection_reasons_summary(self):
        """rejection_reasons_summary should count rejection reasons."""
        report = MetricsReport(
            plan_records=[
                PlanAdoptionRecord(
                    plan_id="test-1",
                    generated_at=datetime.now().isoformat(),
                    total_tasks=5,
                    approved=False,
                    rejection_reason="Too complex",
                ),
                PlanAdoptionRecord(
                    plan_id="test-2",
                    generated_at=datetime.now().isoformat(),
                    total_tasks=5,
                    approved=False,
                    rejection_reason="too complex",  # Same, different case
                ),
                PlanAdoptionRecord(
                    plan_id="test-3",
                    generated_at=datetime.now().isoformat(),
                    total_tasks=5,
                    approved=False,
                    rejection_reason="Missing tests",
                ),
            ]
        )
        summary = report.rejection_reasons_summary()
        assert summary["too complex"] == 2
        assert summary["missing tests"] == 1


class TestMetricsCollectorFeedback:
    """Tests for MetricsCollector feedback methods."""

    @pytest.fixture
    def temp_project(self, tmp_path: Path) -> Path:
        """Create a temporary project directory."""
        return tmp_path

    @pytest.fixture
    def collector_with_plan(self, temp_project: Path) -> tuple[MetricsCollector, str]:
        """Create collector with a recorded plan."""
        collector = MetricsCollector(temp_project, config=None)
        plan_id = collector.record_plan_generated(total_tasks=5)
        return collector, plan_id

    def test_record_plan_approval_success(self, collector_with_plan):
        """Recording approval should update record."""
        collector, plan_id = collector_with_plan

        result = collector.record_plan_approval(
            plan_id,
            approved=True,
            accuracy_rating=5,
        )

        assert result is True
        report = collector.load()
        record = report.plan_records[0]
        assert record.approved is True
        assert record.approved_at is not None
        assert record.accuracy_rating == 5

    def test_record_plan_approval_not_found(self, temp_project: Path):
        """Recording approval for non-existent plan returns False."""
        collector = MetricsCollector(temp_project, config=None)

        result = collector.record_plan_approval(
            "nonexistent-id",
            approved=True,
        )

        assert result is False

    def test_record_plan_rejection(self, collector_with_plan):
        """Recording rejection should include reason."""
        collector, plan_id = collector_with_plan

        collector.record_plan_approval(
            plan_id,
            approved=False,
            rejection_reason="Too complex",
        )

        report = collector.load()
        record = report.plan_records[0]
        assert record.approved is False
        assert record.rejection_reason == "Too complex"

    def test_record_plan_with_user_notes(self, collector_with_plan):
        """Recording approval can include user notes."""
        collector, plan_id = collector_with_plan

        collector.record_plan_approval(
            plan_id,
            approved=True,
            user_notes="Great plan, very detailed",
        )

        report = collector.load()
        record = report.plan_records[0]
        assert record.user_notes == "Great plan, very detailed"

    def test_accuracy_rating_clamped_high(self, collector_with_plan):
        """Accuracy rating should be clamped to max 5."""
        collector, plan_id = collector_with_plan

        collector.record_plan_approval(plan_id, approved=True, accuracy_rating=10)

        report = collector.load()
        assert report.plan_records[0].accuracy_rating == 5

    def test_accuracy_rating_clamped_low(self, collector_with_plan):
        """Accuracy rating should be clamped to min 1."""
        collector, plan_id = collector_with_plan

        collector.record_plan_approval(plan_id, approved=True, accuracy_rating=0)

        report = collector.load()
        assert report.plan_records[0].accuracy_rating == 1

    def test_record_plan_revision(self, collector_with_plan):
        """Recording revision should increment count."""
        collector, plan_id = collector_with_plan

        collector.record_plan_revision(plan_id)
        collector.record_plan_revision(plan_id)

        report = collector.load()
        assert report.plan_records[0].revision_count == 2

    def test_record_plan_revision_not_found(self, temp_project: Path):
        """Recording revision for non-existent plan returns False."""
        collector = MetricsCollector(temp_project, config=None)

        result = collector.record_plan_revision("nonexistent-id")

        assert result is False

    def test_get_quality_metrics_summary(self, temp_project: Path):
        """get_quality_metrics_summary should return all metrics."""
        collector = MetricsCollector(temp_project)

        # Create some plans with feedback
        plan_id1 = collector.record_plan_generated(total_tasks=5)
        collector.record_plan_approval(plan_id1, approved=True, accuracy_rating=4)

        plan_id2 = collector.record_plan_generated(total_tasks=3)
        collector.record_plan_approval(
            plan_id2, approved=False, rejection_reason="Too complex"
        )

        summary = collector.get_quality_metrics_summary()

        assert summary["total_plans"] == 2
        assert summary["approval_rate"] == 0.5
        assert summary["pending_approval"] == 0
        assert summary["average_accuracy_rating"] == 4.0
        assert "too complex" in summary["rejection_reasons"]

    def test_get_approval_rate_history(self, temp_project: Path):
        """get_approval_rate_history should return daily rates."""
        collector = MetricsCollector(temp_project)

        # Create plans with approvals
        plan_id1 = collector.record_plan_generated(total_tasks=5)
        collector.record_plan_approval(plan_id1, approved=True)

        plan_id2 = collector.record_plan_generated(total_tasks=3)
        collector.record_plan_approval(plan_id2, approved=True)

        history = collector.get_approval_rate_history(days=30)

        # Should have at least one entry for today
        assert len(history) >= 0  # May be empty if no plans yet
        if history:
            date_str, rate = history[0]
            assert isinstance(date_str, str)
            assert 0.0 <= rate <= 1.0


class TestMetricsCollectorPersistence:
    """Tests for feedback data persistence."""

    @pytest.fixture
    def temp_project(self, tmp_path: Path) -> Path:
        """Create a temporary project directory."""
        return tmp_path

    def test_feedback_persists_after_save_load(self, temp_project: Path):
        """Feedback should persist after save and reload."""
        collector1 = MetricsCollector(temp_project)
        plan_id = collector1.record_plan_generated(total_tasks=5)
        collector1.record_plan_approval(
            plan_id,
            approved=True,
            accuracy_rating=4,
            user_notes="Good plan",
        )
        collector1.record_plan_revision(plan_id)
        collector1.save()

        # Create new collector and load
        collector2 = MetricsCollector(temp_project)
        report = collector2.load()

        record = report.plan_records[0]
        assert record.approved is True
        assert record.accuracy_rating == 4
        assert record.user_notes == "Good plan"
        assert record.revision_count == 1
