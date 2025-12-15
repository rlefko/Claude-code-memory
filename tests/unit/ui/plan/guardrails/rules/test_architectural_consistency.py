"""Tests for ArchitecturalConsistencyRule.

Tests that the rule correctly detects architectural pattern violations
in file paths and task descriptions.
"""

import pytest

from claude_indexer.rules.base import Severity
from claude_indexer.ui.plan.guardrails.base import (
    PlanValidationContext,
    RevisionType,
)
from claude_indexer.ui.plan.guardrails.config import PlanGuardrailConfig
from claude_indexer.ui.plan.guardrails.rules.architectural_consistency import (
    ArchitecturalConsistencyRule,
)
from claude_indexer.ui.plan.task import ImplementationPlan, Task, TaskGroup


@pytest.fixture
def rule():
    """Create rule instance."""
    return ArchitecturalConsistencyRule()


@pytest.fixture
def config():
    """Create test config."""
    return PlanGuardrailConfig(enabled=True, check_architecture=True)


def make_task(
    task_id: str = "TASK-0001",
    title: str = "Task title",
    description: str = "Task description",
    evidence_links: list[str] | None = None,
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
        evidence_links=evidence_links or [],
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
        assert rule.rule_id == "PLAN.ARCHITECTURAL_CONSISTENCY"

    def test_name(self, rule):
        """Test rule name."""
        assert rule.name == "Architectural Consistency Check"

    def test_category(self, rule):
        """Test rule category."""
        assert rule.category == "architecture"

    def test_severity(self, rule):
        """Test default severity."""
        assert rule.default_severity == Severity.MEDIUM

    def test_is_fast(self, rule):
        """Test is_fast property."""
        assert rule.is_fast is True


class TestFileTypeDetection:
    """Test detection of file types from task content."""

    @pytest.mark.parametrize(
        "title,description,expected_type",
        [
            ("Add unit tests", "Test the module", "tests"),
            ("Create component", "React component", "components"),
            ("Add utility function", "Helper for processing", "utils"),
            ("Update config", "Configuration changes", "config"),
            ("Add API endpoint", "REST controller", "api"),
            ("Create data model", "Entity schema", "models"),
            ("Add service layer", "Business logic service", "services"),
        ],
    )
    def test_detects_file_types(self, rule, title, description, expected_type):
        """File types should be detected from task content."""
        task = make_task(title=title, description=description)
        detected = rule._detect_file_type(task)
        assert detected == expected_type

    def test_returns_none_for_unknown_type(self, rule):
        """Returns None when file type cannot be determined."""
        task = make_task(title="Do something", description="Unspecified task")
        detected = rule._detect_file_type(task)
        assert detected is None


class TestPathPatternMatching:
    """Test file path pattern matching."""

    @pytest.mark.parametrize(
        "file_path,file_type",
        [
            ("tests/unit/test_auth.py", "tests"),
            ("__tests__/auth.test.js", "tests"),
            ("src/auth.test.ts", "tests"),
            ("auth_test.py", "tests"),
            ("auth.spec.js", "tests"),
            ("src/components/Button.tsx", "components"),
            ("components/Modal.vue", "components"),
            ("src/utils/helpers.py", "utils"),
            ("lib/helpers.ts", "utils"),
            ("config/settings.py", "config"),
            ("app.config.js", "config"),
            ("api/routes/users.py", "api"),
            ("app/api/auth/route.ts", "api"),
            ("models/user.py", "models"),
            ("services/auth_service.py", "services"),
        ],
    )
    def test_correct_paths_match(self, rule, file_path, file_type):
        """Correct paths should match patterns."""
        assert rule._path_matches_pattern(file_path, file_type) is True

    @pytest.mark.parametrize(
        "file_path,file_type",
        [
            ("src/auth.py", "tests"),  # Not a test file
            ("utils/helpers.py", "components"),  # Not a component
            ("api/routes.py", "models"),  # Not a model
        ],
    )
    def test_incorrect_paths_dont_match(self, rule, file_path, file_type):
        """Incorrect paths should not match patterns."""
        assert rule._path_matches_pattern(file_path, file_type) is False


class TestArchitecturalViolations:
    """Test detection of architectural violations."""

    def test_detects_test_file_in_wrong_location(self, rule, config):
        """Test file in wrong location should be flagged."""
        task = make_task(
            task_id="TASK-0001",
            title="Add unit test",
            description="Test for auth module",
            evidence_links=["src/test_auth.py:10"],  # Wrong location
        )
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) >= 1
        assert any("tests" in str(f.evidence) for f in findings)

    def test_correct_location_passes(self, rule, config):
        """Files in correct locations should not be flagged."""
        task = make_task(
            task_id="TASK-0001",
            title="Add unit test",
            description="Test for auth module",
            evidence_links=["tests/test_auth.py:10"],  # Correct location
        )
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        # Should have no file path violations
        file_path_findings = [
            f for f in findings if f.evidence and "file_path" in str(f.evidence[0].data)
        ]
        assert len(file_path_findings) == 0

    def test_multiple_violations_multiple_findings(self, rule, config):
        """Multiple violations should create multiple findings."""
        task = make_task(
            task_id="TASK-0001",
            title="Add unit test",
            description="Test module",
            evidence_links=[
                "src/test_auth.py:10",  # Wrong
                "lib/test_users.py:20",  # Wrong
            ],
        )
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        # Should have multiple findings for file path violations
        assert len(findings) >= 2


class TestMultipleResponsibilities:
    """Test detection of tasks with multiple responsibilities."""

    def test_detects_multiple_concerns(self, rule, config):
        """Tasks touching many areas should be flagged."""
        task = make_task(
            task_id="TASK-0001",
            title="Create component with test, API, and model",
            description=(
                "Build a new component, write tests, "
                "add API endpoint, and create data model"
            ),
        )
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        # Should flag multiple responsibilities
        multi_resp_findings = [
            f
            for f in findings
            if "multiple" in f.summary.lower() or "multiple" in str(f.evidence)
        ]
        assert len(multi_resp_findings) >= 1

    def test_focused_task_passes(self, rule, config):
        """Focused tasks should not be flagged for multiple concerns."""
        task = make_task(
            task_id="TASK-0001",
            title="Add user component",
            description="Create a React component for user profile",
        )
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        # Should not flag for multiple responsibilities
        multi_resp_findings = [f for f in findings if "multiple" in f.summary.lower()]
        assert len(multi_resp_findings) == 0


class TestAutoRevision:
    """Test auto-revision suggestion."""

    def test_suggests_task_modification(self, rule, config):
        """Should suggest modifying task with architectural warning."""
        task = make_task(
            task_id="TASK-0001",
            title="Add unit test",
            description="Test module",
            evidence_links=["src/test_auth.py:10"],
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
        assert "Architectural Note" in revision.modifications["description"]

    def test_revision_returns_none_for_invalid_task(self, rule, config):
        """Revision returns None for invalid task ID."""
        task = make_task(
            task_id="TASK-0001",
            title="Add test",
            evidence_links=["src/test.py"],
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

    def test_task_without_evidence_links(self, rule, config):
        """Tasks without evidence links should not cause errors."""
        task = make_task(
            task_id="TASK-0001",
            title="Add component",
            description="Create component",
            evidence_links=[],
        )
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        # Should not raise
        findings = rule.validate(context)
        # May or may not have findings, but should not error
        assert isinstance(findings, list)

    def test_confidence_value(self, rule, config):
        """Findings should have expected confidence."""
        task = make_task(
            task_id="TASK-0001",
            title="Add test",
            description="Unit test",
            evidence_links=["src/test.py"],
        )
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        if findings:
            # File path findings should have 0.85 confidence
            # Description findings should have 0.75 confidence
            assert all(f.confidence in [0.75, 0.85] for f in findings)
