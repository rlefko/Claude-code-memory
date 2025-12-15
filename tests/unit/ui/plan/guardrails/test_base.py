"""Tests for plan validation guardrails base module.

Tests the core data structures: RevisionType, PlanRevision,
PlanValidationFinding, PlanValidationContext, and PlanValidationRule.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from claude_indexer.rules.base import Evidence, Severity
from claude_indexer.ui.plan.guardrails.base import (
    PlanRevision,
    PlanValidationContext,
    PlanValidationFinding,
    PlanValidationRule,
    RevisionType,
)
from claude_indexer.ui.plan.guardrails.config import PlanGuardrailConfig
from claude_indexer.ui.plan.task import ImplementationPlan, Task, TaskGroup


# Test fixtures
@pytest.fixture
def sample_task() -> Task:
    """Create a sample task for testing."""
    return Task(
        id="TASK-TST-0001",
        title="Implement user authentication",
        description="Add authentication flow",
        scope="components",
        priority=1,
        estimated_effort="medium",
        impact=0.8,
        acceptance_criteria=["Tests pass", "Code review complete"],
        evidence_links=["src/auth.py:50"],
        related_critique_ids=[],
        dependencies=[],
        tags=["security"],
    )


@pytest.fixture
def sample_plan(sample_task: Task) -> ImplementationPlan:
    """Create a sample implementation plan."""
    return ImplementationPlan(
        groups=[
            TaskGroup(
                scope="components",
                description="Component updates",
                tasks=[sample_task],
            )
        ],
        quick_wins=[],
        summary="Test implementation plan",
    )


@pytest.fixture
def sample_config() -> PlanGuardrailConfig:
    """Create a sample guardrail config."""
    return PlanGuardrailConfig(
        enabled=True,
        check_coverage=True,
        check_consistency=True,
    )


class TestRevisionType:
    """Tests for RevisionType enum."""

    def test_enum_values(self):
        """Test all enum values are correct."""
        assert RevisionType.ADD_TASK.value == "add_task"
        assert RevisionType.MODIFY_TASK.value == "modify_task"
        assert RevisionType.REMOVE_TASK.value == "remove_task"
        assert RevisionType.ADD_DEPENDENCY.value == "add_dependency"
        assert RevisionType.REORDER_TASKS.value == "reorder_tasks"

    def test_enum_from_value(self):
        """Test creating enum from value."""
        assert RevisionType("add_task") == RevisionType.ADD_TASK
        assert RevisionType("modify_task") == RevisionType.MODIFY_TASK


class TestPlanRevision:
    """Tests for PlanRevision dataclass."""

    def test_basic_creation(self):
        """Test creating a basic revision."""
        revision = PlanRevision(
            revision_type=RevisionType.ADD_TASK,
            rationale="Missing test task",
        )
        assert revision.revision_type == RevisionType.ADD_TASK
        assert revision.rationale == "Missing test task"
        assert revision.target_task_id is None
        assert revision.new_task is None
        assert revision.modifications == {}
        assert revision.dependency_additions == []

    def test_modify_task_revision(self):
        """Test creating a modification revision."""
        revision = PlanRevision(
            revision_type=RevisionType.MODIFY_TASK,
            rationale="Add acceptance criteria",
            target_task_id="TASK-0001",
            modifications={"acceptance_criteria": ["Test coverage >80%"]},
        )
        assert revision.target_task_id == "TASK-0001"
        assert "acceptance_criteria" in revision.modifications

    def test_add_dependency_revision(self):
        """Test creating a dependency revision."""
        revision = PlanRevision(
            revision_type=RevisionType.ADD_DEPENDENCY,
            rationale="Task B depends on Task A",
            dependency_additions=[("TASK-B", "TASK-A")],
        )
        assert len(revision.dependency_additions) == 1
        assert revision.dependency_additions[0] == ("TASK-B", "TASK-A")

    def test_to_dict_basic(self):
        """Test serializing revision to dict."""
        revision = PlanRevision(
            revision_type=RevisionType.MODIFY_TASK,
            rationale="Test reason",
            target_task_id="TASK-0001",
        )
        data = revision.to_dict()
        assert data["revision_type"] == "modify_task"
        assert data["rationale"] == "Test reason"
        assert data["target_task_id"] == "TASK-0001"

    def test_to_dict_with_task(self, sample_task: Task):
        """Test serializing revision with new task."""
        revision = PlanRevision(
            revision_type=RevisionType.ADD_TASK,
            rationale="Add test task",
            new_task=sample_task,
        )
        data = revision.to_dict()
        assert "new_task" in data
        assert data["new_task"]["id"] == "TASK-TST-0001"

    def test_from_dict_basic(self):
        """Test deserializing revision from dict."""
        data = {
            "revision_type": "modify_task",
            "rationale": "Test reason",
            "target_task_id": "TASK-0001",
            "modifications": {"priority": 1},
            "dependency_additions": [],
        }
        revision = PlanRevision.from_dict(data)
        assert revision.revision_type == RevisionType.MODIFY_TASK
        assert revision.rationale == "Test reason"
        assert revision.modifications == {"priority": 1}

    def test_from_dict_with_task(self, sample_task: Task):
        """Test deserializing revision with task."""
        data = {
            "revision_type": "add_task",
            "rationale": "Add task",
            "new_task": sample_task.to_dict(),
            "modifications": {},
            "dependency_additions": [],
        }
        revision = PlanRevision.from_dict(data)
        assert revision.new_task is not None
        assert revision.new_task.id == "TASK-TST-0001"

    def test_roundtrip_serialization(self, sample_task: Task):
        """Test that to_dict -> from_dict preserves data."""
        original = PlanRevision(
            revision_type=RevisionType.ADD_TASK,
            rationale="Test roundtrip",
            new_task=sample_task,
            dependency_additions=[("A", "B"), ("C", "D")],
        )
        data = original.to_dict()
        restored = PlanRevision.from_dict(data)
        assert restored.revision_type == original.revision_type
        assert restored.rationale == original.rationale
        assert restored.new_task is not None
        assert restored.new_task.id == sample_task.id


class TestPlanValidationFinding:
    """Tests for PlanValidationFinding dataclass."""

    def test_basic_creation(self):
        """Test creating a basic finding."""
        finding = PlanValidationFinding(
            rule_id="PLAN.TEST_REQUIREMENT",
            severity=Severity.MEDIUM,
            summary="Feature lacks test task",
        )
        assert finding.rule_id == "PLAN.TEST_REQUIREMENT"
        assert finding.severity == Severity.MEDIUM
        assert finding.affected_tasks == []
        assert finding.can_auto_revise is False
        assert finding.confidence == 1.0

    def test_full_finding_with_evidence(self):
        """Test creating finding with all fields."""
        evidence = Evidence(
            description="Task has no test dependency",
            line_number=None,
            code_snippet=None,
            data={"task_id": "TASK-0001"},
        )
        revision = PlanRevision(
            revision_type=RevisionType.ADD_TASK,
            rationale="Add test task",
        )
        finding = PlanValidationFinding(
            rule_id="PLAN.TEST_REQUIREMENT",
            severity=Severity.HIGH,
            summary="Feature lacks test task",
            affected_tasks=["TASK-0001"],
            suggestion="Add a test task after TASK-0001",
            can_auto_revise=True,
            confidence=0.9,
            evidence=[evidence],
            suggested_revision=revision,
        )
        assert len(finding.evidence) == 1
        assert finding.suggested_revision is not None
        assert finding.can_auto_revise is True

    def test_to_dict(self):
        """Test serializing finding to dict."""
        finding = PlanValidationFinding(
            rule_id="PLAN.DUPLICATE_DETECTION",
            severity=Severity.HIGH,
            summary="Potential duplicate code",
            affected_tasks=["TASK-0002"],
            confidence=0.75,
        )
        data = finding.to_dict()
        assert data["rule_id"] == "PLAN.DUPLICATE_DETECTION"
        assert data["severity"] == "high"
        assert data["confidence"] == 0.75
        assert "created_at" in data

    def test_from_dict(self):
        """Test deserializing finding from dict."""
        data = {
            "rule_id": "PLAN.TEST_REQUIREMENT",
            "severity": "medium",
            "summary": "Test finding",
            "affected_tasks": ["TASK-0001"],
            "can_auto_revise": False,
            "confidence": 0.8,
            "evidence": [],
        }
        finding = PlanValidationFinding.from_dict(data)
        assert finding.rule_id == "PLAN.TEST_REQUIREMENT"
        assert finding.severity == Severity.MEDIUM
        assert finding.confidence == 0.8

    def test_roundtrip_with_revision(self):
        """Test roundtrip serialization with revision."""
        revision = PlanRevision(
            revision_type=RevisionType.MODIFY_TASK,
            rationale="Add note",
            target_task_id="TASK-0001",
            modifications={"description": "Updated"},
        )
        original = PlanValidationFinding(
            rule_id="PLAN.DUPLICATE_DETECTION",
            severity=Severity.HIGH,
            summary="Duplicate detected",
            affected_tasks=["TASK-0001"],
            can_auto_revise=True,
            suggested_revision=revision,
        )
        data = original.to_dict()
        restored = PlanValidationFinding.from_dict(data)
        assert restored.suggested_revision is not None
        assert restored.suggested_revision.target_task_id == "TASK-0001"


class TestPlanValidationContext:
    """Tests for PlanValidationContext dataclass."""

    def test_basic_creation(
        self, sample_plan: ImplementationPlan, sample_config: PlanGuardrailConfig
    ):
        """Test creating a basic context."""
        context = PlanValidationContext(
            plan=sample_plan,
            config=sample_config,
        )
        assert context.plan == sample_plan
        assert context.config == sample_config
        assert context.project_path == Path.cwd()
        assert context.memory_client is None
        assert context.collection_name is None
        assert context.source_requirements == ""

    def test_get_task_by_id(
        self,
        sample_plan: ImplementationPlan,
        sample_config: PlanGuardrailConfig,
        sample_task: Task,
    ):
        """Test getting task by ID."""
        context = PlanValidationContext(plan=sample_plan, config=sample_config)

        # Found task
        task = context.get_task_by_id("TASK-TST-0001")
        assert task is not None
        assert task.id == "TASK-TST-0001"

        # Not found
        task = context.get_task_by_id("NONEXISTENT")
        assert task is None

    def test_search_memory_no_client(
        self, sample_plan: ImplementationPlan, sample_config: PlanGuardrailConfig
    ):
        """Test search_memory returns empty when no client."""
        context = PlanValidationContext(plan=sample_plan, config=sample_config)
        results = context.search_memory("test query")
        assert results == []

    def test_search_memory_with_mock_client(
        self, sample_plan: ImplementationPlan, sample_config: PlanGuardrailConfig
    ):
        """Test search_memory with mocked client."""
        mock_result = Mock()
        mock_result.score = 0.9
        mock_result.payload = {
            "name": "test_function",
            "entity_type": "function",
            "file_path": "test.py",
            "content": "def test(): pass",
        }

        mock_client = Mock()
        mock_client.search.return_value = [mock_result]

        context = PlanValidationContext(
            plan=sample_plan,
            config=sample_config,
            memory_client=mock_client,
            collection_name="test-collection",
        )
        results = context.search_memory("test query", limit=5)

        assert len(results) == 1
        assert results[0]["score"] == 0.9
        assert results[0]["name"] == "test_function"
        mock_client.search.assert_called_once()

    def test_search_memory_handles_exception(
        self, sample_plan: ImplementationPlan, sample_config: PlanGuardrailConfig
    ):
        """Test search_memory handles exceptions gracefully."""
        mock_client = Mock()
        mock_client.search.side_effect = Exception("Connection failed")

        context = PlanValidationContext(
            plan=sample_plan,
            config=sample_config,
            memory_client=mock_client,
            collection_name="test-collection",
        )
        results = context.search_memory("test query")
        assert results == []


class TestPlanValidationRule:
    """Tests for PlanValidationRule abstract base class."""

    def test_concrete_rule_implementation(
        self, sample_plan: ImplementationPlan, sample_config: PlanGuardrailConfig
    ):
        """Test implementing a concrete rule."""

        class TestRule(PlanValidationRule):
            @property
            def rule_id(self) -> str:
                return "PLAN.TEST_RULE"

            @property
            def name(self) -> str:
                return "Test Rule"

            @property
            def category(self) -> str:
                return "coverage"

            @property
            def default_severity(self) -> Severity:
                return Severity.MEDIUM

            def validate(
                self, context: PlanValidationContext
            ) -> list[PlanValidationFinding]:
                return [
                    self._create_finding(
                        summary="Test finding",
                        affected_tasks=["TASK-0001"],
                        confidence=0.9,
                    )
                ]

            def suggest_revision(
                self,
                finding: PlanValidationFinding,
                context: PlanValidationContext,
            ) -> PlanRevision | None:
                return PlanRevision(
                    revision_type=RevisionType.MODIFY_TASK,
                    rationale="Test revision",
                    target_task_id=finding.affected_tasks[0],
                )

        rule = TestRule()
        assert rule.rule_id == "PLAN.TEST_RULE"
        assert rule.category == "coverage"
        assert rule.default_severity == Severity.MEDIUM
        assert rule.is_fast is True
        assert "PLAN.TEST_RULE" in rule.description

        context = PlanValidationContext(plan=sample_plan, config=sample_config)
        findings = rule.validate(context)
        assert len(findings) == 1
        assert findings[0].rule_id == "PLAN.TEST_RULE"
        assert findings[0].confidence == 0.9

        revision = rule.suggest_revision(findings[0], context)
        assert revision is not None
        assert revision.revision_type == RevisionType.MODIFY_TASK

    def test_create_finding_helper(
        self, sample_plan: ImplementationPlan, sample_config: PlanGuardrailConfig
    ):
        """Test _create_finding helper method."""

        class MinimalRule(PlanValidationRule):
            @property
            def rule_id(self) -> str:
                return "PLAN.MINIMAL"

            @property
            def name(self) -> str:
                return "Minimal Rule"

            @property
            def category(self) -> str:
                return "consistency"

            @property
            def default_severity(self) -> Severity:
                return Severity.LOW

            def validate(
                self, context: PlanValidationContext
            ) -> list[PlanValidationFinding]:
                return []

            def suggest_revision(
                self,
                finding: PlanValidationFinding,
                context: PlanValidationContext,
            ) -> PlanRevision | None:
                return None

        rule = MinimalRule()
        finding = rule._create_finding(
            summary="Test summary",
            affected_tasks=["TASK-1", "TASK-2"],
            suggestion="Fix it",
            can_auto_revise=True,
        )
        assert finding.rule_id == "PLAN.MINIMAL"
        assert finding.severity == Severity.LOW
        assert len(finding.affected_tasks) == 2
        assert finding.suggestion == "Fix it"

    def test_rule_repr(self):
        """Test rule string representation."""

        class TestRule(PlanValidationRule):
            @property
            def rule_id(self) -> str:
                return "PLAN.REPR_TEST"

            @property
            def name(self) -> str:
                return "Repr Test"

            @property
            def category(self) -> str:
                return "coverage"

            @property
            def default_severity(self) -> Severity:
                return Severity.MEDIUM

            def validate(
                self, context: PlanValidationContext
            ) -> list[PlanValidationFinding]:
                return []

            def suggest_revision(
                self, finding: PlanValidationFinding, context: PlanValidationContext
            ) -> PlanRevision | None:
                return None

        rule = TestRule()
        assert "TestRule" in repr(rule)
        assert "PLAN.REPR_TEST" in repr(rule)


class TestSeverityFromConfig:
    """Tests for severity override from config."""

    def test_default_severity_used(self):
        """Test default severity is used when no config."""

        class TestRule(PlanValidationRule):
            @property
            def rule_id(self) -> str:
                return "PLAN.SEVERITY_TEST"

            @property
            def name(self) -> str:
                return "Severity Test"

            @property
            def category(self) -> str:
                return "coverage"

            @property
            def default_severity(self) -> Severity:
                return Severity.LOW

            def validate(
                self, context: PlanValidationContext
            ) -> list[PlanValidationFinding]:
                return []

            def suggest_revision(
                self, finding: PlanValidationFinding, context: PlanValidationContext
            ) -> PlanRevision | None:
                return None

        rule = TestRule()
        severity = rule.get_severity(None)
        assert severity == Severity.LOW

    def test_severity_override_from_config(self):
        """Test severity override from rule config."""
        from claude_indexer.ui.plan.guardrails.config import RuleConfig

        class TestRule(PlanValidationRule):
            @property
            def rule_id(self) -> str:
                return "PLAN.SEVERITY_TEST"

            @property
            def name(self) -> str:
                return "Severity Test"

            @property
            def category(self) -> str:
                return "coverage"

            @property
            def default_severity(self) -> Severity:
                return Severity.LOW

            def validate(
                self, context: PlanValidationContext
            ) -> list[PlanValidationFinding]:
                return []

            def suggest_revision(
                self, finding: PlanValidationFinding, context: PlanValidationContext
            ) -> PlanRevision | None:
                return None

        rule = TestRule()
        config = RuleConfig(severity="HIGH")
        severity = rule.get_severity(config)
        assert severity == Severity.HIGH
