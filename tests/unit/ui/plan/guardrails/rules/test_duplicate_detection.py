"""Tests for DuplicateDetectionRule.

Tests that the rule correctly detects tasks that may duplicate
existing code via semantic memory search.
"""

from unittest.mock import Mock

import pytest

from claude_indexer.rules.base import Severity
from claude_indexer.ui.plan.guardrails.base import (
    PlanValidationContext,
    RevisionType,
)
from claude_indexer.ui.plan.guardrails.config import PlanGuardrailConfig, RuleConfig
from claude_indexer.ui.plan.guardrails.rules.duplicate_detection import (
    DuplicateDetectionRule,
)
from claude_indexer.ui.plan.task import ImplementationPlan, Task, TaskGroup


@pytest.fixture
def rule():
    """Create rule instance."""
    return DuplicateDetectionRule()


@pytest.fixture
def config():
    """Create test config."""
    return PlanGuardrailConfig(enabled=True, check_consistency=True)


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


def make_mock_client_with_results(results: list[dict]):
    """Create mock memory client with search results."""
    mock_result_objects = []
    for r in results:
        mock_obj = Mock()
        mock_obj.score = r.get("score", 0.5)
        mock_obj.payload = {
            "name": r.get("name", "function"),
            "entity_type": r.get("type", "function"),
            "file_path": r.get("file_path", "src/file.py"),
            "content": r.get("content", "def func(): pass"),
        }
        mock_result_objects.append(mock_obj)

    mock_client = Mock()
    mock_client.search.return_value = mock_result_objects
    return mock_client


class TestRuleProperties:
    """Test rule properties."""

    def test_rule_id(self, rule):
        """Test rule ID."""
        assert rule.rule_id == "PLAN.DUPLICATE_DETECTION"

    def test_name(self, rule):
        """Test rule name."""
        assert rule.name == "Duplicate Code Detection"

    def test_category(self, rule):
        """Test rule category."""
        assert rule.category == "consistency"

    def test_severity(self, rule):
        """Test default severity."""
        assert rule.default_severity == Severity.HIGH

    def test_is_fast(self, rule):
        """Test is_fast property (should be False for memory search)."""
        assert rule.is_fast is False


class TestCreationTaskDetection:
    """Test detection of creation tasks."""

    @pytest.mark.parametrize(
        "title,description",
        [
            ("Implement auth service", "Create authentication logic"),
            ("Create new component", "Build a button"),
            ("Add validation module", "Input validation"),
            ("Build API client", "HTTP client for API"),
            ("Write logger utility", "Logging helper"),
            ("Develop caching layer", "Add caching"),
        ],
    )
    def test_detects_creation_tasks(self, rule, title, description):
        """Creation tasks should be detected."""
        task = make_task(title=title, description=description)
        assert rule._is_creation_task(task) is True

    @pytest.mark.parametrize(
        "title,description",
        [
            ("Fix bug in auth", "Repair login issue"),
            ("Update config", "Change settings"),
            ("Refactor code", "Improve structure"),
        ],
    )
    def test_ignores_non_creation_tasks(self, rule, title, description):
        """Non-creation tasks should not be flagged."""
        task = make_task(title=title, description=description)
        assert rule._is_creation_task(task) is False


class TestDuplicateDetection:
    """Test duplicate detection via memory search."""

    def test_no_findings_without_memory_client(self, rule, config):
        """No findings when memory client is not available."""
        task = make_task(title="Implement auth", description="Create auth")
        plan = make_plan([task])
        context = PlanValidationContext(plan=plan, config=config)

        findings = rule.validate(context)

        assert len(findings) == 0

    def test_detects_duplicate_above_threshold(self, rule, config):
        """Detects duplicate when similarity is above threshold."""
        task = make_task(
            task_id="TASK-0001",
            title="Implement authentication",
            description="Create login functionality",
        )
        plan = make_plan([task])

        mock_client = make_mock_client_with_results(
            [
                {
                    "score": 0.85,
                    "name": "AuthService.login",
                    "type": "function",
                    "file_path": "src/auth.py",
                }
            ]
        )

        context = PlanValidationContext(
            plan=plan,
            config=config,
            memory_client=mock_client,
            collection_name="test-collection",
        )

        findings = rule.validate(context)

        assert len(findings) == 1
        assert "TASK-0001" in findings[0].affected_tasks
        assert "AuthService.login" in findings[0].summary
        assert len(findings[0].evidence) > 0

    def test_no_findings_below_threshold(self, rule, config):
        """No findings when similarity is below threshold."""
        task = make_task(title="Implement auth", description="Create auth")
        plan = make_plan([task])

        mock_client = make_mock_client_with_results(
            [{"score": 0.5, "name": "unrelated_function"}]
        )

        context = PlanValidationContext(
            plan=plan,
            config=config,
            memory_client=mock_client,
            collection_name="test-collection",
        )

        findings = rule.validate(context)

        assert len(findings) == 0

    def test_custom_threshold_from_config(self, rule):
        """Custom threshold from config is used."""
        task = make_task(title="Create helper", description="Build utility")
        plan = make_plan([task])

        # Set custom threshold
        config = PlanGuardrailConfig(
            enabled=True, rules={"PLAN.DUPLICATE_DETECTION": RuleConfig(threshold=0.5)}
        )

        mock_client = make_mock_client_with_results(
            [{"score": 0.55, "name": "existing_helper"}]
        )

        context = PlanValidationContext(
            plan=plan,
            config=config,
            memory_client=mock_client,
            collection_name="test-collection",
        )

        findings = rule.validate(context)

        # Should detect because 0.55 > 0.5 (custom threshold)
        assert len(findings) == 1

    def test_confidence_based_on_similarity(self, rule, config):
        """Finding confidence should be based on similarity score."""
        task = make_task(title="Create auth", description="Auth logic")
        plan = make_plan([task])

        mock_client = make_mock_client_with_results(
            [{"score": 0.80, "name": "existing_auth"}]
        )

        context = PlanValidationContext(
            plan=plan,
            config=config,
            memory_client=mock_client,
            collection_name="test-collection",
        )

        findings = rule.validate(context)

        assert len(findings) == 1
        # Confidence should be min(0.95, score)
        assert findings[0].confidence == 0.80


class TestAutoRevision:
    """Test auto-revision suggestion."""

    def test_suggests_task_modification(self, rule, config):
        """Should suggest modifying task to reference existing code."""
        task = make_task(
            task_id="TASK-0001",
            title="Create validator",
            description="Input validation logic",
        )
        plan = make_plan([task])

        mock_client = make_mock_client_with_results(
            [
                {
                    "score": 0.75,
                    "name": "validate_input",
                    "file_path": "src/validators.py",
                }
            ]
        )

        context = PlanValidationContext(
            plan=plan,
            config=config,
            memory_client=mock_client,
            collection_name="test-collection",
        )

        findings = rule.validate(context)
        assert len(findings) == 1

        revision = rule.suggest_revision(findings[0], context)

        assert revision is not None
        assert revision.revision_type == RevisionType.MODIFY_TASK
        assert revision.target_task_id == "TASK-0001"
        assert "description" in revision.modifications
        assert "acceptance_criteria" in revision.modifications

    def test_revision_returns_none_for_invalid_task(self, rule, config):
        """Revision returns None for invalid task ID."""
        task = make_task(task_id="TASK-0001", title="Create X")
        plan = make_plan([task])

        mock_client = make_mock_client_with_results(
            [{"score": 0.8, "name": "existing"}]
        )

        context = PlanValidationContext(
            plan=plan,
            config=config,
            memory_client=mock_client,
            collection_name="test-collection",
        )

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

    def test_multiple_duplicates_detected(self, rule, config):
        """Multiple duplicate matches should be in evidence."""
        task = make_task(title="Create auth", description="Auth logic")
        plan = make_plan([task])

        mock_client = make_mock_client_with_results(
            [
                {"score": 0.85, "name": "auth_v1"},
                {"score": 0.80, "name": "auth_v2"},
                {"score": 0.75, "name": "auth_v3"},
                {"score": 0.72, "name": "auth_v4"},
            ]
        )

        context = PlanValidationContext(
            plan=plan,
            config=config,
            memory_client=mock_client,
            collection_name="test-collection",
        )

        findings = rule.validate(context)

        assert len(findings) == 1
        # Should have top 3 matches in evidence
        assert len(findings[0].evidence) == 3

    def test_memory_search_exception_handled(self, rule, config):
        """Memory search exceptions should be handled gracefully."""
        task = make_task(title="Create auth", description="Auth logic")
        plan = make_plan([task])

        mock_client = Mock()
        mock_client.search.side_effect = Exception("Search failed")

        context = PlanValidationContext(
            plan=plan,
            config=config,
            memory_client=mock_client,
            collection_name="test-collection",
        )

        # Should not raise, returns empty findings
        findings = rule.validate(context)

        assert len(findings) == 0
