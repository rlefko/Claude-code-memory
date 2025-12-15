"""Tests for PerformancePatternRule.

Tests that the rule correctly detects performance anti-patterns
in task descriptions.
"""

import pytest

from claude_indexer.rules.base import Severity
from claude_indexer.ui.plan.guardrails.base import (
    PlanValidationContext,
    RevisionType,
)
from claude_indexer.ui.plan.guardrails.config import PlanGuardrailConfig
from claude_indexer.ui.plan.guardrails.rules.performance_pattern import (
    PerformancePatternRule,
)
from claude_indexer.ui.plan.task import ImplementationPlan, Task, TaskGroup


@pytest.fixture
def rule():
    """Create rule instance."""
    return PerformancePatternRule()


@pytest.fixture
def config():
    """Create test config."""
    return PlanGuardrailConfig(enabled=True, check_performance=True)


def make_task(
    task_id: str = "TASK-0001",
    title: str = "Task title",
    description: str = "Task description",
) -> Task:
    """Helper to create a task."""
    return Task(
        id=task_id,
        title=title,
        description=description,
        scope="components",
        priority=1,
        estimated_effort="medium",
        impact=0.8,
        acceptance_criteria=[],
        evidence_links=[],
        related_critique_ids=[],
        dependencies=[],
        tags=[],
    )


def make_plan(tasks: list[Task]) -> ImplementationPlan:
    """Helper to create a plan with tasks."""
    return ImplementationPlan(
        groups=[
            TaskGroup(
                scope="components",
                description="Component updates",
                tasks=tasks,
            )
        ],
        quick_wins=[],
        summary="Test plan",
    )


class TestRuleProperties:
    """Test rule properties."""

    def test_rule_id(self, rule):
        """Test rule ID."""
        assert rule.rule_id == "PLAN.PERFORMANCE_PATTERN"

    def test_name(self, rule):
        """Test rule name."""
        assert rule.name == "Performance Pattern Detection"

    def test_category(self, rule):
        """Test rule category."""
        assert rule.category == "performance"

    def test_severity(self, rule):
        """Test default severity."""
        assert rule.default_severity == Severity.LOW

    def test_is_fast(self, rule):
        """Test is_fast property."""
        assert rule.is_fast is True


class TestN1QueryDetection:
    """Test detection of N+1 query patterns."""

    @pytest.mark.parametrize(
        "title,description",
        [
            ("Process users", "For each user, query the database for their orders"),
            ("Load data", "Loop through records and fetch from API"),
            ("Iterate items", "Iterate over items and make individual requests"),
        ],
    )
    def test_detects_n1_patterns(self, rule, config, title, description):
        """N+1 query patterns should be detected."""
        task = make_task(title=title, description=description)
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) >= 1
        assert any(
            "N+1" in f.evidence[0].data.get("pattern_name", "") for f in findings
        )


class TestMissingCacheDetection:
    """Test detection of missing cache patterns."""

    @pytest.mark.parametrize(
        "title,description",
        [
            ("Fetch data", "Fetch data with no cache for each request"),
            ("Load user", "Always fetch user data from API"),
            ("Get config", "Expensive operation called every request"),
        ],
    )
    def test_detects_cache_patterns(self, rule, config, title, description):
        """Missing cache patterns should be detected."""
        task = make_task(title=title, description=description)
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) >= 1
        assert any(
            "Cache" in f.evidence[0].data.get("pattern_name", "") for f in findings
        )


class TestBlockingOperationDetection:
    """Test detection of blocking operation patterns."""

    @pytest.mark.parametrize(
        "title,description",
        [
            ("Call API", "Make synchronous external API call"),
            ("Fetch data", "Blocking HTTP request to service"),
            ("External call", "Call without timeout to external service"),
        ],
    )
    def test_detects_blocking_patterns(self, rule, config, title, description):
        """Blocking operation patterns should be detected."""
        task = make_task(title=title, description=description)
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) >= 1
        assert any(
            "Blocking" in f.evidence[0].data.get("pattern_name", "") for f in findings
        )


class TestUnboundedDataDetection:
    """Test detection of unbounded data patterns."""

    @pytest.mark.parametrize(
        "title,description",
        [
            ("Load records", "Load all records from database"),
            ("Fetch data", "Get entire data set without limit"),
            ("Export users", "Fetch all users without pagination"),
        ],
    )
    def test_detects_unbounded_patterns(self, rule, config, title, description):
        """Unbounded data patterns should be detected."""
        task = make_task(title=title, description=description)
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) >= 1
        assert any(
            "Unbounded" in f.evidence[0].data.get("pattern_name", "") for f in findings
        )


class TestMemoryIntensiveDetection:
    """Test detection of memory intensive patterns."""

    @pytest.mark.parametrize(
        "title,description",
        [
            ("Process data", "Build large array in memory"),
            ("Accumulate results", "Accumulate all results before processing"),
            ("Cache data", "Memory intensive operation for caching"),
        ],
    )
    def test_detects_memory_patterns(self, rule, config, title, description):
        """Memory intensive patterns should be detected."""
        task = make_task(title=title, description=description)
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) >= 1
        assert any(
            "Memory" in f.evidence[0].data.get("pattern_name", "") for f in findings
        )


class TestComplexAlgorithmDetection:
    """Test detection of complex algorithm patterns."""

    @pytest.mark.parametrize(
        "title,description",
        [
            ("Search items", "Use nested loop to find matches"),
            ("Find duplicates", "O(n^2) comparison algorithm"),
            ("Match patterns", "Brute force search through all combinations"),
        ],
    )
    def test_detects_complexity_patterns(self, rule, config, title, description):
        """Complex algorithm patterns should be detected."""
        task = make_task(title=title, description=description)
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) >= 1
        assert any(
            "Complex" in f.evidence[0].data.get("pattern_name", "")
            or "Algorithm" in f.evidence[0].data.get("pattern_name", "")
            for f in findings
        )


class TestNoFalsePositives:
    """Test that good patterns don't trigger findings."""

    @pytest.mark.parametrize(
        "title,description",
        [
            ("Add feature", "Implement user authentication"),
            ("Create component", "Build a button component"),
            ("Update config", "Change application settings"),
            ("Fix bug", "Repair login issue"),
            ("Refactor code", "Improve code structure"),
        ],
    )
    def test_clean_tasks_pass(self, rule, config, title, description):
        """Clean tasks should not trigger findings."""
        task = make_task(title=title, description=description)
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) == 0


class TestAutoRevision:
    """Test auto-revision suggestion."""

    def test_suggests_task_modification(self, rule, config):
        """Should suggest modifying task with performance note."""
        task = make_task(
            task_id="TASK-0001",
            title="Load data",
            description="For each user query the database",
        )
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)
        assert len(findings) >= 1

        revision = rule.suggest_revision(findings[0], context)

        assert revision is not None
        assert revision.revision_type == RevisionType.MODIFY_TASK
        assert revision.target_task_id == "TASK-0001"
        assert "description" in revision.modifications
        assert "Performance Note" in revision.modifications["description"]
        assert "acceptance_criteria" in revision.modifications

    def test_revision_returns_none_for_invalid_task(self, rule, config):
        """Revision returns None for invalid task ID."""
        task = make_task(
            task_id="TASK-0001",
            title="Load data",
            description="For each user query DB",
        )
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)
        if findings:
            findings[0].affected_tasks = ["NONEXISTENT"]
            revision = rule.suggest_revision(findings[0], context)
            assert revision is None


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_plan(self, rule, config):
        """Empty plan should have no findings."""
        plan = make_plan([])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) == 0

    def test_multiple_patterns_in_one_task(self, rule, config):
        """Task with multiple anti-patterns should have multiple findings."""
        task = make_task(
            task_id="TASK-0001",
            title="Process all data",
            description=(
                "For each record, query database (N+1), "
                "load all data into memory (unbounded), "
                "use nested loop (O(n^2))"
            ),
        )
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        # Should detect multiple patterns
        assert len(findings) >= 2

    def test_confidence_values(self, rule, config):
        """Findings should have expected confidence values."""
        task = make_task(
            task_id="TASK-0001",
            title="Process data",
            description="Nested loop algorithm",
        )
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        if findings:
            # Confidence should be between 0.6 and 0.8 based on pattern
            assert all(0.6 <= f.confidence <= 0.85 for f in findings)
