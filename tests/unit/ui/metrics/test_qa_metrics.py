"""Tests for Plan QA metrics tracking (Milestone 12.2.3).

Tests the QA-specific fields in MetricSnapshot and the
record_qa_verification() / get_qa_metrics_summary() methods
in MetricsCollector.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from claude_indexer.hooks.plan_qa import PlanQAResult, PlanQAVerifier
from claude_indexer.ui.metrics.collector import MetricsCollector
from claude_indexer.ui.metrics.models import MetricSnapshot


class TestMetricSnapshotQAFields:
    """Tests for QA fields in MetricSnapshot."""

    def test_qa_fields_default_values(self):
        """Test QA fields have correct defaults."""
        snapshot = MetricSnapshot(
            timestamp=datetime.now().isoformat(),
            tier=2,
        )
        assert snapshot.qa_checks_passed == 0
        assert snapshot.qa_issues_found == 0
        assert snapshot.qa_missing_tests == 0
        assert snapshot.qa_missing_docs == 0
        assert snapshot.qa_potential_duplicates == 0
        assert snapshot.qa_architecture_warnings == 0
        assert snapshot.qa_verification_time_ms == 0.0

    def test_qa_fields_custom_values(self):
        """Test QA fields with custom values."""
        snapshot = MetricSnapshot(
            timestamp=datetime.now().isoformat(),
            tier=2,
            qa_checks_passed=3,
            qa_issues_found=5,
            qa_missing_tests=2,
            qa_missing_docs=1,
            qa_potential_duplicates=1,
            qa_architecture_warnings=1,
            qa_verification_time_ms=25.5,
        )
        assert snapshot.qa_checks_passed == 3
        assert snapshot.qa_issues_found == 5
        assert snapshot.qa_missing_tests == 2
        assert snapshot.qa_missing_docs == 1
        assert snapshot.qa_potential_duplicates == 1
        assert snapshot.qa_architecture_warnings == 1
        assert snapshot.qa_verification_time_ms == 25.5

    def test_qa_fields_to_dict(self):
        """Test QA fields are included in to_dict()."""
        snapshot = MetricSnapshot(
            timestamp=datetime.now().isoformat(),
            tier=2,
            qa_checks_passed=4,
            qa_issues_found=0,
            qa_missing_tests=0,
            qa_missing_docs=0,
            qa_potential_duplicates=0,
            qa_architecture_warnings=0,
            qa_verification_time_ms=10.5,
        )
        data = snapshot.to_dict()
        assert "qa_checks_passed" in data
        assert "qa_issues_found" in data
        assert "qa_missing_tests" in data
        assert "qa_missing_docs" in data
        assert "qa_potential_duplicates" in data
        assert "qa_architecture_warnings" in data
        assert "qa_verification_time_ms" in data
        assert data["qa_checks_passed"] == 4
        assert data["qa_verification_time_ms"] == 10.5

    def test_qa_fields_from_dict(self):
        """Test QA fields are loaded from dict."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "tier": 2,
            "qa_checks_passed": 2,
            "qa_issues_found": 3,
            "qa_missing_tests": 1,
            "qa_missing_docs": 1,
            "qa_potential_duplicates": 1,
            "qa_architecture_warnings": 0,
            "qa_verification_time_ms": 15.0,
        }
        snapshot = MetricSnapshot.from_dict(data)
        assert snapshot.qa_checks_passed == 2
        assert snapshot.qa_issues_found == 3
        assert snapshot.qa_missing_tests == 1
        assert snapshot.qa_missing_docs == 1
        assert snapshot.qa_potential_duplicates == 1
        assert snapshot.qa_architecture_warnings == 0
        assert snapshot.qa_verification_time_ms == 15.0

    def test_qa_fields_backward_compatibility(self):
        """Test loading old snapshots without QA fields."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "tier": 1,
            # No QA fields - simulating old data
        }
        snapshot = MetricSnapshot.from_dict(data)
        # Should use defaults
        assert snapshot.qa_checks_passed == 0
        assert snapshot.qa_issues_found == 0
        assert snapshot.qa_missing_tests == 0
        assert snapshot.qa_missing_docs == 0
        assert snapshot.qa_potential_duplicates == 0
        assert snapshot.qa_architecture_warnings == 0
        assert snapshot.qa_verification_time_ms == 0.0


class TestRecordQAVerification:
    """Tests for MetricsCollector.record_qa_verification()."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_record_qa_verification_basic(self, temp_project: Path):
        """Test basic QA verification recording."""
        collector = MetricsCollector(temp_project)

        qa_result = PlanQAResult(
            is_valid=True,
            missing_tests=[],
            missing_docs=[],
            potential_duplicates=[],
            architecture_warnings=[],
            verification_time_ms=20.0,
        )

        success = collector.record_qa_verification(qa_result)
        assert success is True

        # Verify snapshot was created
        report = collector.load()
        assert len(report.snapshots) == 1
        snapshot = report.snapshots[0]
        assert snapshot.qa_checks_passed == 4
        assert snapshot.qa_issues_found == 0
        assert snapshot.qa_verification_time_ms == 20.0

    def test_record_qa_verification_with_issues(self, temp_project: Path):
        """Test recording QA verification with issues."""
        collector = MetricsCollector(temp_project)

        qa_result = PlanQAResult(
            is_valid=False,
            missing_tests=["Task A needs tests", "Task B needs tests"],
            missing_docs=["API docs missing"],
            potential_duplicates=["Might duplicate existing AuthService"],
            architecture_warnings=[],
            verification_time_ms=35.0,
        )

        success = collector.record_qa_verification(qa_result)
        assert success is True

        report = collector.load()
        snapshot = report.snapshots[0]
        assert snapshot.qa_checks_passed == 1  # Only architecture passed
        assert snapshot.qa_issues_found == 4  # 2 + 1 + 1 + 0
        assert snapshot.qa_missing_tests == 2
        assert snapshot.qa_missing_docs == 1
        assert snapshot.qa_potential_duplicates == 1
        assert snapshot.qa_architecture_warnings == 0

    def test_record_qa_verification_all_issues(self, temp_project: Path):
        """Test recording QA verification with all issue types."""
        collector = MetricsCollector(temp_project)

        qa_result = PlanQAResult(
            is_valid=False,
            missing_tests=["No tests"],
            missing_docs=["No docs"],
            potential_duplicates=["Duplicate"],
            architecture_warnings=["N+1 query detected"],
            verification_time_ms=50.0,
        )

        collector.record_qa_verification(qa_result)

        report = collector.load()
        snapshot = report.snapshots[0]
        assert snapshot.qa_checks_passed == 0  # All checks failed
        assert snapshot.qa_issues_found == 4

    def test_record_qa_verification_tier(self, temp_project: Path):
        """Test QA verification is recorded as tier 2."""
        collector = MetricsCollector(temp_project)

        qa_result = PlanQAResult(verification_time_ms=10.0)
        collector.record_qa_verification(qa_result)

        report = collector.load()
        assert report.snapshots[0].tier == 2


class TestGetQAMetricsSummary:
    """Tests for MetricsCollector.get_qa_metrics_summary()."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_get_qa_metrics_summary_empty(self, temp_project: Path):
        """Test QA metrics summary with no data."""
        collector = MetricsCollector(temp_project)

        summary = collector.get_qa_metrics_summary()
        assert summary["total_verifications"] == 0
        assert summary["pass_rate"] == 0.0
        assert summary["average_issues"] == 0.0
        assert summary["issue_breakdown"]["missing_tests"] == 0

    def test_get_qa_metrics_summary_all_passed(self, temp_project: Path):
        """Test QA metrics summary with all passed verifications."""
        collector = MetricsCollector(temp_project)

        # Add 3 passing verifications
        for _ in range(3):
            qa_result = PlanQAResult(is_valid=True, verification_time_ms=15.0)
            collector.record_qa_verification(qa_result)

        summary = collector.get_qa_metrics_summary()
        assert summary["total_verifications"] == 3
        assert summary["pass_rate"] == 1.0
        assert summary["average_issues"] == 0.0

    def test_get_qa_metrics_summary_mixed(self, temp_project: Path):
        """Test QA metrics summary with mixed results."""
        collector = MetricsCollector(temp_project)

        # Add 1 passing verification
        qa_result_pass = PlanQAResult(is_valid=True, verification_time_ms=10.0)
        collector.record_qa_verification(qa_result_pass)

        # Add 1 failing verification with issues
        qa_result_fail = PlanQAResult(
            is_valid=False,
            missing_tests=["Need tests"],
            missing_docs=["Need docs"],
            verification_time_ms=20.0,
        )
        collector.record_qa_verification(qa_result_fail)

        summary = collector.get_qa_metrics_summary()
        assert summary["total_verifications"] == 2
        assert summary["pass_rate"] == 0.5
        assert summary["average_issues"] == 1.0  # (0 + 2) / 2
        assert summary["issue_breakdown"]["missing_tests"] == 1
        assert summary["issue_breakdown"]["missing_docs"] == 1

    def test_get_qa_metrics_summary_issue_breakdown(self, temp_project: Path):
        """Test QA metrics issue breakdown aggregation."""
        collector = MetricsCollector(temp_project)

        # Multiple verifications with various issues
        qa_result_1 = PlanQAResult(
            missing_tests=["A", "B"],
            potential_duplicates=["D"],
            verification_time_ms=10.0,
        )
        qa_result_2 = PlanQAResult(
            missing_tests=["C"],
            missing_docs=["X"],
            architecture_warnings=["Y"],
            verification_time_ms=20.0,
        )
        collector.record_qa_verification(qa_result_1)
        collector.record_qa_verification(qa_result_2)

        summary = collector.get_qa_metrics_summary()
        assert summary["issue_breakdown"]["missing_tests"] == 3  # A, B, C
        assert summary["issue_breakdown"]["missing_docs"] == 1  # X
        assert summary["issue_breakdown"]["potential_duplicates"] == 1  # D
        assert summary["issue_breakdown"]["architecture_warnings"] == 1  # Y

    def test_get_qa_metrics_summary_average_time(self, temp_project: Path):
        """Test average verification time calculation."""
        collector = MetricsCollector(temp_project)

        qa_result_1 = PlanQAResult(verification_time_ms=10.0)
        qa_result_2 = PlanQAResult(verification_time_ms=30.0)
        collector.record_qa_verification(qa_result_1)
        collector.record_qa_verification(qa_result_2)

        summary = collector.get_qa_metrics_summary()
        assert summary["average_verification_time_ms"] == 20.0


class TestPlanQAVerifierMetricsIntegration:
    """Tests for PlanQAVerifier integration with MetricsCollector."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_verifier_without_metrics(self):
        """Test verifier works without metrics collector."""
        verifier = PlanQAVerifier()
        result = verifier.verify_plan("1. Create a new function")
        assert result is not None
        assert isinstance(result, PlanQAResult)

    def test_verifier_with_metrics(self, temp_project: Path):
        """Test verifier records metrics when configured."""
        collector = MetricsCollector(temp_project)
        verifier = PlanQAVerifier(metrics_collector=collector)

        # Verify a plan
        result = verifier.verify_plan("1. Create AuthService class")
        assert result is not None

        # Check metrics were recorded
        report = collector.load()
        assert len(report.snapshots) == 1
        snapshot = report.snapshots[0]
        assert snapshot.qa_verification_time_ms > 0

    def test_verifier_records_issues(self, temp_project: Path):
        """Test verifier records issue counts correctly."""
        collector = MetricsCollector(temp_project)
        verifier = PlanQAVerifier(metrics_collector=collector)

        # Plan with code changes but no tests - should have missing_tests issue
        plan_text = """
        1. Create new AuthService class
        2. Add login endpoint
        """
        result = verifier.verify_plan(plan_text)
        assert len(result.missing_tests) > 0

        # Check metrics reflect the issues
        report = collector.load()
        snapshot = report.snapshots[0]
        assert snapshot.qa_missing_tests > 0

    def test_verifier_with_plan_id(self, temp_project: Path):
        """Test verifier accepts plan_id parameter."""
        collector = MetricsCollector(temp_project)
        verifier = PlanQAVerifier(metrics_collector=collector)

        # Should not raise
        result = verifier.verify_plan("1. Simple task", plan_id="test-plan-123")
        assert result is not None
