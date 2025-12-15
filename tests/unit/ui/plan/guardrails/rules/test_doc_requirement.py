"""Tests for DocRequirementRule.

Tests that the rule correctly detects user-facing tasks without
corresponding documentation coverage.
"""

import pytest

from claude_indexer.rules.base import Severity
from claude_indexer.ui.plan.guardrails.base import (
    PlanValidationContext,
    RevisionType,
)
from claude_indexer.ui.plan.guardrails.config import PlanGuardrailConfig
from claude_indexer.ui.plan.guardrails.rules.doc_requirement import (
    DocRequirementRule,
)
from claude_indexer.ui.plan.task import ImplementationPlan, Task, TaskGroup


@pytest.fixture
def rule():
    """Create rule instance."""
    return DocRequirementRule()


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
        assert rule.rule_id == "PLAN.DOC_REQUIREMENT"

    def test_name(self, rule):
        """Test rule name."""
        assert rule.name == "Documentation Requirement Detection"

    def test_category(self, rule):
        """Test rule category."""
        assert rule.category == "coverage"

    def test_severity(self, rule):
        """Test default severity."""
        assert rule.default_severity == Severity.LOW

    def test_is_fast(self, rule):
        """Test is_fast property."""
        assert rule.is_fast is True


class TestUserFacingTaskDetection:
    """Test detection of user-facing tasks."""

    @pytest.mark.parametrize(
        "title,description",
        [
            ("Add new API endpoint", "Create REST endpoint for users"),
            ("Update user interface", "Improve dashboard UI"),
            ("Add CLI command", "New command-line option"),
            ("Create config option", "Add new configuration setting"),
            ("Modify frontend component", "Change visible behavior"),
            ("Add external API", "Expose new API to users"),
        ],
    )
    def test_detects_user_facing_tasks(self, rule, config, title, description):
        """User-facing tasks should be detected."""
        task = make_task(title=title, description=description)
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) == 1
        assert findings[0].rule_id == "PLAN.DOC_REQUIREMENT"
        assert task.id in findings[0].affected_tasks

    @pytest.mark.parametrize(
        "title,description",
        [
            ("Refactor internal code", "Improve code quality"),
            ("Fix database query", "Optimize query performance"),
            ("Update dependencies", "Bump package versions"),
            ("Internal cleanup", "Remove dead code"),
        ],
    )
    def test_ignores_internal_tasks(self, rule, config, title, description):
        """Internal tasks should not trigger findings."""
        task = make_task(title=title, description=description)
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) == 0


class TestDocTaskDetection:
    """Test detection of documentation tasks."""

    @pytest.mark.parametrize(
        "title,description,tags",
        [
            ("Update README", "Document new feature", []),
            ("Add API documentation", "Document endpoints", []),
            ("Update docs", "Fix documentation", []),
            ("Add guide", "Tutorial for feature", []),
            ("Write changelog", "Release notes", []),
            ("Update help text", "CLI help", ["docs"]),
        ],
    )
    def test_recognizes_doc_tasks(self, rule, title, description, tags):
        """Doc tasks should be recognized."""
        task = make_task(title=title, description=description, tags=tags)
        assert rule._is_doc_task(task) is True

    def test_recognizes_doc_task_by_tag(self, rule):
        """Doc tasks with doc tags should be recognized."""
        task = make_task(title="Some task", description="Something", tags=["docs"])
        assert rule._is_doc_task(task) is True


class TestDocCoverage:
    """Test detection of documentation coverage."""

    def test_user_facing_with_doc_dependency_passes(self, rule, config):
        """User-facing task with doc task depending on it passes."""
        user_task = make_task(
            task_id="TASK-0001",
            title="Add new API endpoint",
            description="Create REST endpoint",
        )
        doc_task = make_task(
            task_id="TASK-0002",
            title="Update API documentation",
            description="Document the new endpoint",
            dependencies=["TASK-0001"],
        )
        plan = make_plan([user_task, doc_task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) == 0

    def test_user_facing_without_doc_fails(self, rule, config):
        """User-facing task without doc task fails."""
        user_task = make_task(
            task_id="TASK-0001",
            title="Add new API endpoint",
            description="Create REST endpoint",
        )
        plan = make_plan([user_task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) == 1
        assert "TASK-0001" in findings[0].affected_tasks


class TestAutoRevision:
    """Test auto-revision suggestion."""

    def test_suggests_doc_task(self, rule, config):
        """Should suggest adding a documentation task."""
        user_task = make_task(
            task_id="TASK-0001",
            title="Add CLI option",
            description="New command-line flag",
        )
        plan = make_plan([user_task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)
        assert len(findings) == 1

        revision = rule.suggest_revision(findings[0], context)

        assert revision is not None
        assert revision.revision_type == RevisionType.ADD_TASK
        assert revision.new_task is not None
        assert "doc" in revision.new_task.title.lower()
        assert user_task.id in revision.new_task.dependencies

    def test_revision_returns_none_for_invalid_task(self, rule, config):
        """Revision returns None for invalid task ID."""
        user_task = make_task(task_id="TASK-0001", title="Add API")
        plan = make_plan([user_task])
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

    def test_doc_task_not_flagged(self, rule, config):
        """Doc task itself should not be flagged."""
        doc_task = make_task(
            task_id="TASK-0001",
            title="Update documentation",
            description="Fix docs",
        )
        plan = make_plan([doc_task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) == 0

    def test_confidence_value(self, rule, config):
        """Findings should have expected confidence."""
        task = make_task(title="Add user interface", description="New UI")
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) == 1
        assert findings[0].confidence == 0.8
