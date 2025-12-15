"""Unit tests for plan validation formatters.

Tests thoroughness levels and formatting consistency.
Milestone 13.4.4: Iterate on findings format
Milestone 13.4.5: Add configuration for thoroughness level
"""

import time

import pytest

from claude_indexer.rules.base import Evidence, Severity
from claude_indexer.ui.plan.formatters import (
    CATEGORY_NAMES,
    SEVERITY_ICONS,
    ThoroughnessLevel,
    format_plan_findings_for_claude,
    format_plan_findings_for_display,
)
from claude_indexer.ui.plan.guardrails.base import PlanValidationFinding


class TestThoroughnessLevel:
    """Tests for ThoroughnessLevel enum."""

    def test_enum_values(self):
        """Verify all expected values exist."""
        assert ThoroughnessLevel.MINIMAL.value == "minimal"
        assert ThoroughnessLevel.STANDARD.value == "standard"
        assert ThoroughnessLevel.THOROUGH.value == "thorough"
        assert ThoroughnessLevel.EXHAUSTIVE.value == "exhaustive"

    def test_enum_from_string(self):
        """Verify enum can be created from string."""
        assert ThoroughnessLevel("minimal") == ThoroughnessLevel.MINIMAL
        assert ThoroughnessLevel("standard") == ThoroughnessLevel.STANDARD
        assert ThoroughnessLevel("thorough") == ThoroughnessLevel.THOROUGH
        assert ThoroughnessLevel("exhaustive") == ThoroughnessLevel.EXHAUSTIVE

    def test_invalid_value_raises(self):
        """Invalid values should raise ValueError."""
        with pytest.raises(ValueError):
            ThoroughnessLevel("invalid")


class TestSeverityIcons:
    """Tests for severity icon mappings."""

    def test_all_severities_have_icons(self):
        """All severity levels should have icons."""
        assert Severity.CRITICAL in SEVERITY_ICONS
        assert Severity.HIGH in SEVERITY_ICONS
        assert Severity.MEDIUM in SEVERITY_ICONS
        assert Severity.LOW in SEVERITY_ICONS

    def test_icons_are_strings(self):
        """All icons should be non-empty strings."""
        for _severity, icon in SEVERITY_ICONS.items():
            assert isinstance(icon, str)
            assert len(icon) > 0


class TestCategoryNames:
    """Tests for category name mappings."""

    def test_expected_categories_exist(self):
        """Expected categories should have display names."""
        assert "coverage" in CATEGORY_NAMES
        assert "consistency" in CATEGORY_NAMES
        assert "architecture" in CATEGORY_NAMES
        assert "performance" in CATEGORY_NAMES


class TestFormatForDisplay:
    """Tests for format_plan_findings_for_display."""

    @pytest.fixture
    def sample_findings(self) -> list[PlanValidationFinding]:
        """Create sample findings for testing."""
        return [
            PlanValidationFinding(
                rule_id="PLAN.TEST_REQUIREMENT",
                severity=Severity.MEDIUM,
                summary="Feature task without test dependency",
                affected_tasks=["task-1"],
                suggestion="Add unit test task",
                can_auto_revise=True,
                confidence=0.9,
                evidence=[
                    Evidence(
                        description="Task creates new function without tests",
                        line_number=10,
                    )
                ],
            ),
            PlanValidationFinding(
                rule_id="PLAN.DUPLICATE_DETECTION",
                severity=Severity.HIGH,
                summary="Similar code exists in AuthService",
                affected_tasks=["task-2"],
                suggestion="Consider extending existing code",
                evidence=[
                    Evidence(
                        description="Function login() already exists",
                        line_number=25,
                    )
                ],
            ),
        ]

    def test_empty_findings_returns_pass_message(self):
        """Empty findings should show pass message."""
        result = format_plan_findings_for_display([])
        assert "All quality checks passed" in result

    def test_minimal_excludes_suggestions(self, sample_findings):
        """MINIMAL should exclude suggestions."""
        result = format_plan_findings_for_display(
            sample_findings, thoroughness=ThoroughnessLevel.MINIMAL
        )
        assert "Suggestion:" not in result

    def test_minimal_excludes_evidence(self, sample_findings):
        """MINIMAL should exclude evidence."""
        result = format_plan_findings_for_display(
            sample_findings, thoroughness=ThoroughnessLevel.MINIMAL
        )
        assert "Evidence:" not in result

    def test_standard_includes_suggestions(self, sample_findings):
        """STANDARD should include suggestions."""
        result = format_plan_findings_for_display(
            sample_findings, thoroughness=ThoroughnessLevel.STANDARD
        )
        assert "Suggestion:" in result

    def test_standard_excludes_evidence(self, sample_findings):
        """STANDARD should exclude evidence."""
        result = format_plan_findings_for_display(
            sample_findings, thoroughness=ThoroughnessLevel.STANDARD
        )
        assert "Evidence:" not in result

    def test_thorough_includes_evidence(self, sample_findings):
        """THOROUGH should include evidence."""
        result = format_plan_findings_for_display(
            sample_findings, thoroughness=ThoroughnessLevel.THOROUGH
        )
        assert "Evidence:" in result

    def test_exhaustive_includes_confidence(self, sample_findings):
        """EXHAUSTIVE should include confidence."""
        result = format_plan_findings_for_display(
            sample_findings, thoroughness=ThoroughnessLevel.EXHAUSTIVE
        )
        assert "Confidence:" in result or "90%" in result

    def test_exhaustive_includes_auto_revision_note(self, sample_findings):
        """EXHAUSTIVE should note auto-revision availability."""
        result = format_plan_findings_for_display(
            sample_findings, thoroughness=ThoroughnessLevel.EXHAUSTIVE
        )
        assert "Auto-revision available" in result

    def test_groups_by_severity_when_enabled(self, sample_findings):
        """Should group by severity when flag is True."""
        result = format_plan_findings_for_display(
            sample_findings, group_by_severity=True
        )
        # HIGH should appear before MEDIUM in output
        high_pos = result.find("[HIGH]")
        medium_pos = result.find("[MEDIUM]")
        assert high_pos < medium_pos

    def test_no_grouping_preserves_order(self, sample_findings):
        """Without grouping, should preserve original order."""
        result = format_plan_findings_for_display(
            sample_findings, group_by_severity=False
        )
        # MEDIUM (first finding) should appear before HIGH (second finding)
        medium_pos = result.find("PLAN.TEST_REQUIREMENT")
        high_pos = result.find("PLAN.DUPLICATE_DETECTION")
        assert medium_pos < high_pos

    def test_includes_summary_header(self, sample_findings):
        """Output should include summary header."""
        result = format_plan_findings_for_display(sample_findings)
        assert "Plan Validation:" in result
        assert "1 high" in result.lower() or "HIGH" in result
        assert "1 medium" in result.lower() or "MEDIUM" in result

    def test_includes_affected_tasks(self, sample_findings):
        """Output should include affected task IDs."""
        result = format_plan_findings_for_display(sample_findings)
        assert "task-1" in result or "Affects:" in result

    def test_truncates_many_affected_tasks(self):
        """Many affected tasks should be truncated."""
        finding = PlanValidationFinding(
            rule_id="PLAN.TEST",
            severity=Severity.MEDIUM,
            summary="Test finding",
            affected_tasks=["task-1", "task-2", "task-3", "task-4", "task-5"],
        )
        result = format_plan_findings_for_display([finding])
        assert "+2 more" in result or "task-5" not in result


class TestFormatForClaude:
    """Tests for format_plan_findings_for_claude."""

    @pytest.fixture
    def blocking_finding(self) -> PlanValidationFinding:
        """Create a blocking (HIGH severity) finding."""
        return PlanValidationFinding(
            rule_id="PLAN.DUPLICATE_DETECTION",
            severity=Severity.HIGH,
            summary="Duplicate code detected",
            suggestion="Extend existing code",
        )

    @pytest.fixture
    def non_blocking_finding(self) -> PlanValidationFinding:
        """Create a non-blocking (LOW severity) finding."""
        return PlanValidationFinding(
            rule_id="PLAN.PERFORMANCE_PATTERN",
            severity=Severity.LOW,
            summary="Consider caching",
        )

    def test_empty_returns_empty_string(self):
        """Empty findings should return empty string."""
        result = format_plan_findings_for_claude([])
        assert result == ""

    def test_blocking_header_for_high_severity(self, blocking_finding):
        """Should show BLOCKED header for HIGH severity."""
        result = format_plan_findings_for_claude([blocking_finding])
        assert "BLOCKED" in result

    def test_warning_header_for_low_severity(self, non_blocking_finding):
        """Should show WARNINGS header for non-blocking severity."""
        result = format_plan_findings_for_claude([non_blocking_finding])
        assert "WARNINGS" in result

    def test_includes_summary_count(self, blocking_finding):
        """Should include summary count at end."""
        result = format_plan_findings_for_claude([blocking_finding])
        assert "Found 1 issue(s)" in result

    def test_includes_severity_in_output(self, blocking_finding):
        """Should include severity level."""
        result = format_plan_findings_for_claude([blocking_finding])
        assert "HIGH" in result

    def test_includes_rule_id(self, blocking_finding):
        """Should include rule ID."""
        result = format_plan_findings_for_claude([blocking_finding])
        assert "PLAN.DUPLICATE_DETECTION" in result

    def test_includes_suggestion(self, blocking_finding):
        """Should include suggestion."""
        result = format_plan_findings_for_claude([blocking_finding])
        assert "Suggestion:" in result

    def test_sorts_by_severity(self):
        """Should sort findings by severity (critical first)."""
        findings = [
            PlanValidationFinding(
                rule_id="LOW_RULE",
                severity=Severity.LOW,
                summary="Low severity",
            ),
            PlanValidationFinding(
                rule_id="CRITICAL_RULE",
                severity=Severity.CRITICAL,
                summary="Critical severity",
            ),
        ]
        result = format_plan_findings_for_claude(findings)
        critical_pos = result.find("CRITICAL_RULE")
        low_pos = result.find("LOW_RULE")
        assert critical_pos < low_pos

    def test_thorough_includes_evidence(self):
        """THOROUGH should include evidence in output."""
        finding = PlanValidationFinding(
            rule_id="PLAN.TEST",
            severity=Severity.MEDIUM,
            summary="Test",
            evidence=[Evidence(description="Evidence detail")],
        )
        result = format_plan_findings_for_claude(
            [finding], thoroughness=ThoroughnessLevel.THOROUGH
        )
        assert "Evidence:" in result

    def test_exhaustive_includes_auto_revision_note(self):
        """EXHAUSTIVE should note auto-revision availability."""
        finding = PlanValidationFinding(
            rule_id="PLAN.TEST",
            severity=Severity.MEDIUM,
            summary="Test",
            can_auto_revise=True,
        )
        result = format_plan_findings_for_claude(
            [finding], thoroughness=ThoroughnessLevel.EXHAUSTIVE
        )
        assert "Auto-revision" in result


class TestPerformance:
    """Performance tests for formatters."""

    def test_display_formatting_under_10ms(self):
        """Formatting 100 findings should complete in <10ms."""
        findings = [
            PlanValidationFinding(
                rule_id=f"PLAN.TEST_{i}",
                severity=Severity.MEDIUM,
                summary=f"Test finding {i} with some content",
                affected_tasks=[f"task-{i}"],
                suggestion=f"Suggestion for finding {i}",
                evidence=[
                    Evidence(description=f"Evidence {i}"),
                    Evidence(description=f"Evidence {i}b"),
                ],
            )
            for i in range(100)
        ]

        start = time.perf_counter()
        format_plan_findings_for_display(
            findings, thoroughness=ThoroughnessLevel.EXHAUSTIVE
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 10, f"Formatting took {elapsed_ms:.2f}ms, expected <10ms"

    def test_claude_formatting_under_10ms(self):
        """Formatting 100 findings for Claude should complete in <10ms."""
        findings = [
            PlanValidationFinding(
                rule_id=f"PLAN.TEST_{i}",
                severity=Severity.MEDIUM,
                summary=f"Test finding {i}",
            )
            for i in range(100)
        ]

        start = time.perf_counter()
        format_plan_findings_for_claude(
            findings, thoroughness=ThoroughnessLevel.EXHAUSTIVE
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 10, f"Formatting took {elapsed_ms:.2f}ms, expected <10ms"
