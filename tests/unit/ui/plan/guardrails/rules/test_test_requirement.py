"""Tests for TestRequirementRule.

Tests that the rule correctly detects feature tasks without
corresponding test coverage.
"""

import pytest

from claude_indexer.rules.base import Severity
from claude_indexer.ui.plan.guardrails.base import (
    PlanValidationContext,
    RevisionType,
)
from claude_indexer.ui.plan.guardrails.config import PlanGuardrailConfig
from claude_indexer.ui.plan.guardrails.rules.test_requirement import (
    TestRequirementRule,
)
from claude_indexer.ui.plan.task import ImplementationPlan, Task, TaskGroup


@pytest.fixture
def rule():
    """Create rule instance."""
    return TestRequirementRule()


@pytest.fixture
def config():
    """Create test config."""
    return PlanGuardrailConfig(enabled=True, check_coverage=True)


def make_task(
    task_id: str = "TASK-0001",
    title: str = "Task title",
    description: str = "Task description",
    tags: list[str] | None = None,
    dependencies: list[str] | None = None,
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
        dependencies=dependencies or [],
        tags=tags or [],
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
        assert rule.rule_id == "PLAN.TEST_REQUIREMENT"

    def test_name(self, rule):
        """Test rule name."""
        assert rule.name == "Test Requirement Detection"

    def test_category(self, rule):
        """Test rule category."""
        assert rule.category == "coverage"

    def test_severity(self, rule):
        """Test default severity."""
        assert rule.default_severity == Severity.MEDIUM

    def test_is_fast(self, rule):
        """Test is_fast property."""
        assert rule.is_fast is True


class TestFeatureTaskDetection:
    """Test detection of feature tasks."""

    @pytest.mark.parametrize(
        "title,description",
        [
            ("Implement user authentication", "Add login flow"),
            ("Create new component", "Build a button component"),
            ("Add validation logic", "Input validation for forms"),
            ("Build API endpoint", "REST endpoint for users"),
            ("Develop caching layer", "Add Redis caching"),
            ("Introduce new feature", "A new feature for users"),
        ],
    )
    def test_detects_feature_tasks(self, rule, config, title, description):
        """Feature tasks should be detected."""
        task = make_task(title=title, description=description)
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) == 1
        assert findings[0].rule_id == "PLAN.TEST_REQUIREMENT"
        assert task.id in findings[0].affected_tasks

    @pytest.mark.parametrize(
        "title,description",
        [
            ("Fix typo in readme", "Correct spelling"),
            ("Update comment in code", "Fix documentation"),
            ("Rename variable", "Better naming"),
            ("Move file to new location", "Reorganize"),
            ("Delete unused comment", "Cleanup"),
            ("Fix whitespace", "Format code"),
        ],
    )
    def test_ignores_trivial_tasks(self, rule, config, title, description):
        """Trivial tasks should not trigger findings."""
        task = make_task(title=title, description=description)
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) == 0


class TestTestTaskDetection:
    """Test detection of test-related tasks."""

    @pytest.mark.parametrize(
        "title,description,tags",
        [
            ("Add unit tests", "Test the auth module", []),
            ("Write pytest tests", "Coverage for API", []),
            ("Create integration test", "E2E testing", []),
            ("Add jest specs", "Component tests", []),
            ("Improve test coverage", "More tests", ["testing"]),
            ("Add spec files", "Vitest tests", []),
        ],
    )
    def test_recognizes_test_tasks(self, rule, title, description, tags):
        """Test tasks should be recognized."""
        task = make_task(title=title, description=description, tags=tags)
        assert rule._is_test_task(task) is True

    def test_recognizes_test_task_by_tag(self, rule):
        """Test tasks with test tags should be recognized."""
        task = make_task(title="Some task", description="Something", tags=["test"])
        assert rule._is_test_task(task) is True


class TestTestCoverage:
    """Test detection of test coverage."""

    def test_feature_with_test_dependency_passes(self, rule, config):
        """Feature task with test task depending on it passes."""
        feature_task = make_task(
            task_id="TASK-0001",
            title="Implement feature X",
            description="Build feature",
        )
        test_task = make_task(
            task_id="TASK-0002",
            title="Add tests for feature X",
            description="Test the feature",
            dependencies=["TASK-0001"],
        )
        plan = make_plan([feature_task, test_task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) == 0

    def test_feature_without_test_fails(self, rule, config):
        """Feature task without test task fails."""
        feature_task = make_task(
            task_id="TASK-0001",
            title="Implement feature X",
            description="Build feature",
        )
        plan = make_plan([feature_task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) == 1
        assert "TASK-0001" in findings[0].affected_tasks

    def test_multiple_features_multiple_findings(self, rule, config):
        """Multiple features without tests create multiple findings."""
        task1 = make_task(
            task_id="TASK-0001",
            title="Implement feature A",
            description="Build A",
        )
        task2 = make_task(
            task_id="TASK-0002",
            title="Create component B",
            description="Build B",
        )
        plan = make_plan([task1, task2])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) == 2


class TestAutoRevision:
    """Test auto-revision suggestion."""

    def test_suggests_test_task(self, rule, config):
        """Should suggest adding a test task."""
        feature_task = make_task(
            task_id="TASK-0001",
            title="Implement auth",
            description="Add authentication",
        )
        plan = make_plan([feature_task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)
        assert len(findings) == 1

        revision = rule.suggest_revision(findings[0], context)

        assert revision is not None
        assert revision.revision_type == RevisionType.ADD_TASK
        assert revision.new_task is not None
        assert "test" in revision.new_task.title.lower()
        assert feature_task.id in revision.new_task.dependencies

    def test_revision_returns_none_for_invalid_task(self, rule, config):
        """Revision returns None for invalid task ID."""
        feature_task = make_task(task_id="TASK-0001", title="Implement X")
        plan = make_plan([feature_task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)
        # Modify finding to have invalid task ID
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

    def test_test_task_not_flagged(self, rule, config):
        """Test task itself should not be flagged."""
        test_task = make_task(
            task_id="TASK-0001",
            title="Add unit tests",
            description="Write tests for auth",
        )
        plan = make_plan([test_task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) == 0

    def test_confidence_value(self, rule, config):
        """Findings should have expected confidence."""
        task = make_task(title="Implement feature", description="New feature")
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) == 1
        assert findings[0].confidence == 0.9
