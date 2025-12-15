"""Unit tests for the auto-revision engine.

Tests cover:
- Data class functionality (AppliedRevision, RevisedPlan)
- Conflict detection
- Circular dependency prevention
- Revision application for all RevisionTypes
- Engine iteration logic
- Audit trail formatting
"""

import pytest

from claude_indexer.rules.base import Severity
from claude_indexer.ui.plan.guardrails.auto_revision import (
    AppliedRevision,
    AutoRevisionEngine,
    RevisedPlan,
    create_auto_revision_engine,
)
from claude_indexer.ui.plan.guardrails.base import (
    PlanRevision,
    PlanValidationFinding,
    RevisionType,
)
from claude_indexer.ui.plan.guardrails.config import PlanGuardrailConfig
from claude_indexer.ui.plan.task import ImplementationPlan, Task, TaskGroup

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def config() -> PlanGuardrailConfig:
    """Default configuration for tests."""
    return PlanGuardrailConfig(
        enabled=True,
        auto_revise=True,
        max_revisions_per_plan=10,
        revision_confidence_threshold=0.7,
    )


@pytest.fixture
def config_disabled() -> PlanGuardrailConfig:
    """Configuration with auto-revise disabled."""
    return PlanGuardrailConfig(
        enabled=True,
        auto_revise=False,
    )


@pytest.fixture
def engine(config: PlanGuardrailConfig) -> AutoRevisionEngine:
    """Default engine for tests."""
    return AutoRevisionEngine(config=config)


def make_task(
    task_id: str = "TASK-001",
    title: str = "Test Task",
    description: str = "Test description",
    scope: str = "components",
    priority: int = 2,
    dependencies: list[str] | None = None,
    tags: list[str] | None = None,
) -> Task:
    """Helper to create a test task."""
    return Task(
        id=task_id,
        title=title,
        description=description,
        scope=scope,
        priority=priority,
        estimated_effort="medium",
        impact=0.7,
        acceptance_criteria=["Test criterion"],
        dependencies=dependencies or [],
        tags=tags or [],
    )


def make_plan(tasks: list[Task], scope: str = "components") -> ImplementationPlan:
    """Helper to create a test plan with tasks in a single group."""
    return ImplementationPlan(
        groups=[TaskGroup(scope=scope, description="Test group", tasks=tasks)],
        quick_wins=[],
        summary="Test plan",
    )


def make_finding(
    rule_id: str = "PLAN.TEST_RULE",
    severity: Severity = Severity.MEDIUM,
    summary: str = "Test finding",
    affected_tasks: list[str] | None = None,
    can_auto_revise: bool = True,
    confidence: float = 0.9,
    suggested_revision: PlanRevision | None = None,
) -> PlanValidationFinding:
    """Helper to create a test finding."""
    return PlanValidationFinding(
        rule_id=rule_id,
        severity=severity,
        summary=summary,
        affected_tasks=affected_tasks or [],
        can_auto_revise=can_auto_revise,
        confidence=confidence,
        suggested_revision=suggested_revision,
    )


def make_add_task_revision(
    new_task: Task,
    rationale: str = "Adding test task",
) -> PlanRevision:
    """Helper to create an ADD_TASK revision."""
    return PlanRevision(
        revision_type=RevisionType.ADD_TASK,
        rationale=rationale,
        new_task=new_task,
    )


def make_modify_task_revision(
    target_task_id: str,
    modifications: dict,
    rationale: str = "Modifying task",
) -> PlanRevision:
    """Helper to create a MODIFY_TASK revision."""
    return PlanRevision(
        revision_type=RevisionType.MODIFY_TASK,
        rationale=rationale,
        target_task_id=target_task_id,
        modifications=modifications,
    )


def make_remove_task_revision(
    target_task_id: str,
    rationale: str = "Removing task",
) -> PlanRevision:
    """Helper to create a REMOVE_TASK revision."""
    return PlanRevision(
        revision_type=RevisionType.REMOVE_TASK,
        rationale=rationale,
        target_task_id=target_task_id,
    )


def make_add_dependency_revision(
    from_id: str,
    to_id: str,
    rationale: str = "Adding dependency",
) -> PlanRevision:
    """Helper to create an ADD_DEPENDENCY revision."""
    return PlanRevision(
        revision_type=RevisionType.ADD_DEPENDENCY,
        rationale=rationale,
        dependency_additions=[(from_id, to_id)],
    )


# ============================================================================
# AppliedRevision Tests
# ============================================================================


class TestAppliedRevision:
    """Tests for the AppliedRevision dataclass."""

    def test_create_applied_revision(self):
        """Test creating an AppliedRevision."""
        revision = make_add_task_revision(make_task("TASK-NEW"))
        finding = make_finding()

        applied = AppliedRevision(
            revision=revision,
            finding=finding,
            success=True,
        )

        assert applied.success is True
        assert applied.error is None
        assert applied.revision == revision
        assert applied.finding == finding
        assert applied.applied_at is not None

    def test_applied_revision_with_error(self):
        """Test AppliedRevision with an error."""
        revision = make_add_task_revision(make_task("TASK-NEW"))
        finding = make_finding()

        applied = AppliedRevision(
            revision=revision,
            finding=finding,
            success=False,
            error="Task already exists",
        )

        assert applied.success is False
        assert applied.error == "Task already exists"

    def test_applied_revision_to_dict(self):
        """Test serialization to dict."""
        revision = make_add_task_revision(make_task("TASK-NEW"))
        finding = make_finding()

        applied = AppliedRevision(
            revision=revision,
            finding=finding,
            success=True,
        )

        data = applied.to_dict()

        assert data["success"] is True
        assert data["error"] is None
        assert "revision" in data
        assert "finding" in data
        assert "applied_at" in data

    def test_applied_revision_from_dict(self):
        """Test deserialization from dict."""
        revision = make_add_task_revision(make_task("TASK-NEW"))
        finding = make_finding()

        original = AppliedRevision(
            revision=revision,
            finding=finding,
            success=True,
        )

        data = original.to_dict()
        restored = AppliedRevision.from_dict(data)

        assert restored.success == original.success
        assert restored.revision.revision_type == original.revision.revision_type
        assert restored.finding.rule_id == original.finding.rule_id


# ============================================================================
# RevisedPlan Tests
# ============================================================================


class TestRevisedPlan:
    """Tests for the RevisedPlan dataclass."""

    def test_revised_plan_no_changes(self):
        """Test RevisedPlan with no revisions."""
        plan = make_plan([make_task()])

        result = RevisedPlan(
            original_plan=plan,
            revised_plan=plan,
            revisions_applied=[],
            revisions_skipped=[],
            iterations_used=1,
            total_time_ms=10.0,
        )

        assert result.was_revised is False
        assert result.revision_count == 0
        assert result.skipped_count == 0

    def test_revised_plan_with_changes(self):
        """Test RevisedPlan with applied revisions."""
        plan = make_plan([make_task()])
        revision = make_add_task_revision(make_task("TASK-NEW"))
        finding = make_finding()

        applied = AppliedRevision(
            revision=revision,
            finding=finding,
            success=True,
        )

        result = RevisedPlan(
            original_plan=plan,
            revised_plan=plan,
            revisions_applied=[applied],
            revisions_skipped=[],
            iterations_used=1,
            total_time_ms=15.0,
        )

        assert result.was_revised is True
        assert result.revision_count == 1
        assert result.skipped_count == 0

    def test_revised_plan_with_skipped(self):
        """Test RevisedPlan with skipped revisions."""
        plan = make_plan([make_task()])
        revision = make_add_task_revision(make_task("TASK-NEW"))

        result = RevisedPlan(
            original_plan=plan,
            revised_plan=plan,
            revisions_applied=[],
            revisions_skipped=[(revision, "Conflict detected")],
            iterations_used=1,
            total_time_ms=5.0,
        )

        assert result.was_revised is False
        assert result.revision_count == 0
        assert result.skipped_count == 1

    def test_format_audit_trail_no_revisions(self):
        """Test audit trail with no revisions."""
        plan = make_plan([make_task()])

        result = RevisedPlan(
            original_plan=plan,
            revised_plan=plan,
        )

        trail = result.format_audit_trail()

        assert "Plan Revisions Applied" in trail
        assert "No revisions were needed" in trail

    def test_format_audit_trail_with_add_task(self):
        """Test audit trail with ADD_TASK revision."""
        plan = make_plan([make_task()])
        new_task = make_task("TASK-NEW", title="New Test Task")
        revision = make_add_task_revision(new_task)
        finding = make_finding(rule_id="PLAN.TEST_REQUIREMENT")

        applied = AppliedRevision(
            revision=revision,
            finding=finding,
            success=True,
        )

        result = RevisedPlan(
            original_plan=plan,
            revised_plan=plan,
            revisions_applied=[applied],
            iterations_used=1,
            total_time_ms=20.0,
        )

        trail = result.format_audit_trail()

        assert "Add Task" in trail
        assert "PLAN.TEST_REQUIREMENT" in trail
        assert "TASK-NEW" in trail
        assert "New Test Task" in trail
        assert "Applied 1 revision" in trail

    def test_format_audit_trail_with_modify_task(self):
        """Test audit trail with MODIFY_TASK revision."""
        plan = make_plan([make_task()])
        revision = make_modify_task_revision(
            "TASK-001",
            {"description": "Updated description"},
        )
        finding = make_finding()

        applied = AppliedRevision(
            revision=revision,
            finding=finding,
            success=True,
        )

        result = RevisedPlan(
            original_plan=plan,
            revised_plan=plan,
            revisions_applied=[applied],
            iterations_used=1,
            total_time_ms=15.0,
        )

        trail = result.format_audit_trail()

        assert "Modify Task" in trail
        assert "TASK-001" in trail
        assert "description" in trail

    def test_format_audit_trail_with_skipped(self):
        """Test audit trail includes skipped revisions."""
        plan = make_plan([make_task()])
        revision = make_add_task_revision(make_task("TASK-001"))

        result = RevisedPlan(
            original_plan=plan,
            revised_plan=plan,
            revisions_applied=[],
            revisions_skipped=[(revision, "Task ID already exists")],
            iterations_used=1,
            total_time_ms=5.0,
        )

        trail = result.format_audit_trail()

        assert "Skipped Revisions" in trail
        assert "add_task" in trail
        assert "Task ID already exists" in trail

    def test_to_dict(self):
        """Test RevisedPlan serialization."""
        plan = make_plan([make_task()])

        result = RevisedPlan(
            original_plan=plan,
            revised_plan=plan,
            iterations_used=2,
            total_time_ms=25.0,
        )

        data = result.to_dict()

        assert "original_plan" in data
        assert "revised_plan" in data
        assert data["iterations_used"] == 2
        assert data["total_time_ms"] == 25.0
        assert data["was_revised"] is False


# ============================================================================
# Conflict Detection Tests
# ============================================================================


class TestConflictDetection:
    """Tests for conflict detection in AutoRevisionEngine."""

    def test_add_task_duplicate_id_conflict(self, engine: AutoRevisionEngine):
        """Test detecting duplicate task ID on ADD_TASK."""
        plan = make_plan([make_task("TASK-001")])
        revision = make_add_task_revision(make_task("TASK-001"))

        conflict = engine._check_conflicts(plan, revision)

        assert conflict is not None
        assert "already exists" in conflict

    def test_add_task_no_conflict(self, engine: AutoRevisionEngine):
        """Test ADD_TASK with unique ID passes."""
        plan = make_plan([make_task("TASK-001")])
        revision = make_add_task_revision(make_task("TASK-002"))

        conflict = engine._check_conflicts(plan, revision)

        assert conflict is None

    def test_add_task_missing_new_task(self, engine: AutoRevisionEngine):
        """Test ADD_TASK without new_task fails."""
        plan = make_plan([make_task()])
        revision = PlanRevision(
            revision_type=RevisionType.ADD_TASK,
            rationale="Test",
            new_task=None,
        )

        conflict = engine._check_conflicts(plan, revision)

        assert conflict is not None
        assert "missing new_task" in conflict

    def test_modify_task_missing_target(self, engine: AutoRevisionEngine):
        """Test MODIFY_TASK with non-existent target."""
        plan = make_plan([make_task("TASK-001")])
        revision = make_modify_task_revision("TASK-999", {"description": "New"})

        conflict = engine._check_conflicts(plan, revision)

        assert conflict is not None
        assert "does not exist" in conflict

    def test_modify_task_valid_target(self, engine: AutoRevisionEngine):
        """Test MODIFY_TASK with valid target passes."""
        plan = make_plan([make_task("TASK-001")])
        revision = make_modify_task_revision("TASK-001", {"description": "New"})

        conflict = engine._check_conflicts(plan, revision)

        assert conflict is None

    def test_modify_task_missing_target_id(self, engine: AutoRevisionEngine):
        """Test MODIFY_TASK without target_task_id fails."""
        plan = make_plan([make_task()])
        revision = PlanRevision(
            revision_type=RevisionType.MODIFY_TASK,
            rationale="Test",
            target_task_id=None,
        )

        conflict = engine._check_conflicts(plan, revision)

        assert conflict is not None
        assert "missing target_task_id" in conflict

    def test_remove_task_missing_target(self, engine: AutoRevisionEngine):
        """Test REMOVE_TASK with non-existent target."""
        plan = make_plan([make_task("TASK-001")])
        revision = make_remove_task_revision("TASK-999")

        conflict = engine._check_conflicts(plan, revision)

        assert conflict is not None
        assert "does not exist" in conflict

    def test_remove_task_valid_target(self, engine: AutoRevisionEngine):
        """Test REMOVE_TASK with valid target passes."""
        plan = make_plan([make_task("TASK-001")])
        revision = make_remove_task_revision("TASK-001")

        conflict = engine._check_conflicts(plan, revision)

        assert conflict is None

    def test_add_dependency_self_reference(self, engine: AutoRevisionEngine):
        """Test ADD_DEPENDENCY with self-reference fails."""
        plan = make_plan([make_task("TASK-001")])
        revision = make_add_dependency_revision("TASK-001", "TASK-001")

        conflict = engine._check_conflicts(plan, revision)

        assert conflict is not None
        assert "Self-dependency" in conflict

    def test_add_dependency_missing_source(self, engine: AutoRevisionEngine):
        """Test ADD_DEPENDENCY with missing source task."""
        plan = make_plan([make_task("TASK-001")])
        revision = make_add_dependency_revision("TASK-999", "TASK-001")

        conflict = engine._check_conflicts(plan, revision)

        assert conflict is not None
        assert "Source task" in conflict
        assert "does not exist" in conflict

    def test_add_dependency_missing_target(self, engine: AutoRevisionEngine):
        """Test ADD_DEPENDENCY with missing target task."""
        plan = make_plan([make_task("TASK-001")])
        revision = make_add_dependency_revision("TASK-001", "TASK-999")

        conflict = engine._check_conflicts(plan, revision)

        assert conflict is not None
        assert "Target task" in conflict
        assert "does not exist" in conflict

    def test_reorder_missing_target(self, engine: AutoRevisionEngine):
        """Test REORDER_TASKS with missing target."""
        plan = make_plan([make_task("TASK-001")])
        revision = PlanRevision(
            revision_type=RevisionType.REORDER_TASKS,
            rationale="Reorder",
            target_task_id="TASK-999",
            modifications={"priority": 1},
        )

        conflict = engine._check_conflicts(plan, revision)

        assert conflict is not None
        assert "does not exist" in conflict


# ============================================================================
# Circular Dependency Tests
# ============================================================================


class TestCircularDependencyDetection:
    """Tests for circular dependency detection."""

    def test_simple_cycle_detection(self, engine: AutoRevisionEngine):
        """Test detecting A -> B -> A cycle."""
        task_a = make_task("TASK-A", dependencies=["TASK-B"])
        task_b = make_task("TASK-B")
        plan = make_plan([task_a, task_b])

        # Adding B -> A would create: A -> B -> A
        would_cycle = engine._would_create_cycle(plan, "TASK-B", "TASK-A")

        assert would_cycle is True

    def test_complex_cycle_detection(self, engine: AutoRevisionEngine):
        """Test detecting A -> B -> C -> A cycle."""
        task_a = make_task("TASK-A", dependencies=["TASK-B"])
        task_b = make_task("TASK-B", dependencies=["TASK-C"])
        task_c = make_task("TASK-C")
        plan = make_plan([task_a, task_b, task_c])

        # Adding C -> A would create: A -> B -> C -> A
        would_cycle = engine._would_create_cycle(plan, "TASK-C", "TASK-A")

        assert would_cycle is True

    def test_no_cycle_valid_dependency(self, engine: AutoRevisionEngine):
        """Test valid dependency doesn't trigger cycle detection."""
        task_a = make_task("TASK-A")
        task_b = make_task("TASK-B")
        plan = make_plan([task_a, task_b])

        # A -> B is valid (no existing dependencies)
        would_cycle = engine._would_create_cycle(plan, "TASK-A", "TASK-B")

        assert would_cycle is False

    def test_no_cycle_with_existing_deps(self, engine: AutoRevisionEngine):
        """Test valid dependency with existing deps doesn't trigger cycle."""
        task_a = make_task("TASK-A", dependencies=["TASK-B"])
        task_b = make_task("TASK-B")
        task_c = make_task("TASK-C")
        plan = make_plan([task_a, task_b, task_c])

        # C -> B is valid (doesn't create cycle with A -> B)
        would_cycle = engine._would_create_cycle(plan, "TASK-C", "TASK-B")

        assert would_cycle is False

    def test_add_dependency_cycle_conflict(self, engine: AutoRevisionEngine):
        """Test ADD_DEPENDENCY with cycle is rejected."""
        task_a = make_task("TASK-A", dependencies=["TASK-B"])
        task_b = make_task("TASK-B")
        plan = make_plan([task_a, task_b])

        revision = make_add_dependency_revision("TASK-B", "TASK-A")

        conflict = engine._check_conflicts(plan, revision)

        assert conflict is not None
        assert "circular dependency" in conflict

    def test_get_dependency_graph(self, engine: AutoRevisionEngine):
        """Test building dependency graph from plan."""
        task_a = make_task("TASK-A", dependencies=["TASK-B", "TASK-C"])
        task_b = make_task("TASK-B", dependencies=["TASK-C"])
        task_c = make_task("TASK-C")
        plan = make_plan([task_a, task_b, task_c])

        graph = engine._get_task_dependency_graph(plan)

        assert "TASK-A" in graph
        assert "TASK-B" in graph
        assert "TASK-C" in graph
        assert "TASK-B" in graph["TASK-A"]
        assert "TASK-C" in graph["TASK-A"]
        assert "TASK-C" in graph["TASK-B"]
        assert len(graph["TASK-C"]) == 0


# ============================================================================
# Revision Application Tests
# ============================================================================


class TestRevisionApplication:
    """Tests for applying revisions to plans."""

    def test_apply_add_task(self, engine: AutoRevisionEngine):
        """Test ADD_TASK creates new task in correct group."""
        plan = make_plan([make_task("TASK-001")])
        new_task = make_task("TASK-002", title="New Task")
        revision = make_add_task_revision(new_task)

        new_plan, error = engine._apply_revision(plan, revision)

        assert error is None
        assert len(new_plan.all_tasks) == 2
        task_ids = {t.id for t in new_plan.all_tasks}
        assert "TASK-002" in task_ids

    def test_apply_add_task_new_scope(self, engine: AutoRevisionEngine):
        """Test ADD_TASK creates new group if scope doesn't exist."""
        plan = make_plan([make_task("TASK-001", scope="components")])
        new_task = make_task("TASK-002", scope="tokens")
        revision = make_add_task_revision(new_task)

        new_plan, error = engine._apply_revision(plan, revision)

        assert error is None
        assert len(new_plan.groups) == 2
        scopes = {g.scope for g in new_plan.groups}
        assert "tokens" in scopes

    def test_apply_modify_task_description(self, engine: AutoRevisionEngine):
        """Test MODIFY_TASK updates description."""
        plan = make_plan([make_task("TASK-001", description="Original")])
        revision = make_modify_task_revision(
            "TASK-001",
            {"description": "Updated description"},
        )

        new_plan, error = engine._apply_revision(plan, revision)

        assert error is None
        task = new_plan.all_tasks[0]
        assert task.description == "Updated description"

    def test_apply_modify_task_multiple_fields(self, engine: AutoRevisionEngine):
        """Test MODIFY_TASK updates multiple fields."""
        plan = make_plan([make_task("TASK-001")])
        revision = make_modify_task_revision(
            "TASK-001",
            {
                "title": "New Title",
                "priority": 1,
                "estimated_effort": "high",
            },
        )

        new_plan, error = engine._apply_revision(plan, revision)

        assert error is None
        task = new_plan.all_tasks[0]
        assert task.title == "New Title"
        assert task.priority == 1
        assert task.estimated_effort == "high"

    def test_apply_remove_task(self, engine: AutoRevisionEngine):
        """Test REMOVE_TASK removes task from plan."""
        plan = make_plan(
            [
                make_task("TASK-001"),
                make_task("TASK-002"),
            ]
        )
        revision = make_remove_task_revision("TASK-001")

        new_plan, error = engine._apply_revision(plan, revision)

        assert error is None
        assert len(new_plan.all_tasks) == 1
        assert new_plan.all_tasks[0].id == "TASK-002"

    def test_apply_add_dependency(self, engine: AutoRevisionEngine):
        """Test ADD_DEPENDENCY adds to task dependencies."""
        plan = make_plan(
            [
                make_task("TASK-001"),
                make_task("TASK-002"),
            ]
        )
        revision = make_add_dependency_revision("TASK-001", "TASK-002")

        new_plan, error = engine._apply_revision(plan, revision)

        assert error is None
        task = next(t for t in new_plan.all_tasks if t.id == "TASK-001")
        assert "TASK-002" in task.dependencies

    def test_apply_add_dependency_no_duplicate(self, engine: AutoRevisionEngine):
        """Test ADD_DEPENDENCY doesn't add duplicate."""
        plan = make_plan(
            [
                make_task("TASK-001", dependencies=["TASK-002"]),
                make_task("TASK-002"),
            ]
        )
        revision = make_add_dependency_revision("TASK-001", "TASK-002")

        new_plan, error = engine._apply_revision(plan, revision)

        assert error is None
        task = next(t for t in new_plan.all_tasks if t.id == "TASK-001")
        # Should still only have one dependency
        assert task.dependencies.count("TASK-002") == 1

    def test_apply_reorder_tasks(self, engine: AutoRevisionEngine):
        """Test REORDER_TASKS updates priority."""
        plan = make_plan([make_task("TASK-001", priority=3)])
        revision = PlanRevision(
            revision_type=RevisionType.REORDER_TASKS,
            rationale="Increase priority",
            target_task_id="TASK-001",
            modifications={"priority": 1},
        )

        new_plan, error = engine._apply_revision(plan, revision)

        assert error is None
        task = new_plan.all_tasks[0]
        assert task.priority == 1

    def test_apply_revision_does_not_modify_original(self, engine: AutoRevisionEngine):
        """Test that applying revision doesn't modify original plan."""
        original_task = make_task("TASK-001", description="Original")
        plan = make_plan([original_task])
        revision = make_modify_task_revision(
            "TASK-001",
            {"description": "Modified"},
        )

        new_plan, error = engine._apply_revision(plan, revision)

        assert error is None
        # Original should be unchanged
        assert plan.all_tasks[0].description == "Original"
        # New plan should have the change
        assert new_plan.all_tasks[0].description == "Modified"


# ============================================================================
# Engine Flow Tests
# ============================================================================


class TestEngineFlow:
    """Tests for the main revise_plan() flow."""

    def test_revise_plan_no_findings(self, engine: AutoRevisionEngine):
        """Test with no findings returns unchanged plan."""
        plan = make_plan([make_task()])

        result = engine.revise_plan(plan, [])

        assert result.was_revised is False
        assert result.revision_count == 0
        assert result.iterations_used == 0

    def test_revise_plan_non_revisable_finding(self, engine: AutoRevisionEngine):
        """Test findings without can_auto_revise are skipped."""
        plan = make_plan([make_task()])
        finding = make_finding(can_auto_revise=False)

        result = engine.revise_plan(plan, [finding])

        assert result.was_revised is False

    def test_revise_plan_low_confidence_finding(self, config: PlanGuardrailConfig):
        """Test findings below confidence threshold are skipped."""
        config.revision_confidence_threshold = 0.9
        engine = AutoRevisionEngine(config=config)

        plan = make_plan([make_task()])
        revision = make_add_task_revision(make_task("TASK-NEW"))
        finding = make_finding(
            confidence=0.7,  # Below threshold
            can_auto_revise=True,
            suggested_revision=revision,
        )

        result = engine.revise_plan(plan, [finding])

        assert result.was_revised is False

    def test_revise_plan_applies_revision(self, engine: AutoRevisionEngine):
        """Test valid finding triggers revision."""
        plan = make_plan([make_task("TASK-001")])
        new_task = make_task("TASK-002", title="Test Task")
        revision = make_add_task_revision(new_task)
        finding = make_finding(
            can_auto_revise=True,
            confidence=0.9,
            suggested_revision=revision,
        )

        result = engine.revise_plan(plan, [finding])

        assert result.was_revised is True
        assert result.revision_count == 1
        assert len(result.revised_plan.all_tasks) == 2

    def test_revise_plan_skips_conflicts(self, engine: AutoRevisionEngine):
        """Test conflicting revisions are skipped."""
        plan = make_plan([make_task("TASK-001")])
        # Try to add a task with duplicate ID
        revision = make_add_task_revision(make_task("TASK-001"))
        finding = make_finding(
            can_auto_revise=True,
            suggested_revision=revision,
        )

        result = engine.revise_plan(plan, [finding])

        assert result.was_revised is False
        assert result.skipped_count == 1
        assert "already exists" in result.revisions_skipped[0][1]

    def test_revise_plan_respects_max_revisions(self, config: PlanGuardrailConfig):
        """Test max_revisions_per_plan is respected."""
        config.max_revisions_per_plan = 2
        engine = AutoRevisionEngine(config=config)

        plan = make_plan([make_task("TASK-001")])
        findings = []
        for i in range(5):
            revision = make_add_task_revision(make_task(f"TASK-NEW-{i}"))
            findings.append(
                make_finding(
                    can_auto_revise=True,
                    suggested_revision=revision,
                )
            )

        result = engine.revise_plan(plan, findings)

        assert result.revision_count == 2  # Limited to max

    def test_revise_plan_iteration_limit(self, engine: AutoRevisionEngine):
        """Test iteration limit is enforced."""
        plan = make_plan([make_task("TASK-001")])
        revision = make_add_task_revision(make_task("TASK-002"))
        finding = make_finding(
            can_auto_revise=True,
            suggested_revision=revision,
        )

        result = engine.revise_plan(plan, [finding])

        assert result.iterations_used <= AutoRevisionEngine.MAX_ITERATIONS

    def test_revise_plan_disabled_auto_revise(
        self, config_disabled: PlanGuardrailConfig
    ):
        """Test auto-revise disabled returns unchanged plan."""
        engine = AutoRevisionEngine(config=config_disabled)

        plan = make_plan([make_task()])
        revision = make_add_task_revision(make_task("TASK-NEW"))
        finding = make_finding(
            can_auto_revise=True,
            suggested_revision=revision,
        )

        result = engine.revise_plan(plan, [finding])

        assert result.was_revised is False
        assert result.iterations_used == 0

    def test_revise_plan_sorts_by_severity(self, engine: AutoRevisionEngine):
        """Test higher severity revisions are applied first."""
        plan = make_plan([make_task("TASK-001")])

        # Low severity revision
        low_revision = make_add_task_revision(make_task("TASK-LOW"))
        low_finding = make_finding(
            severity=Severity.LOW,
            can_auto_revise=True,
            suggested_revision=low_revision,
        )

        # High severity revision
        high_revision = make_add_task_revision(make_task("TASK-HIGH"))
        high_finding = make_finding(
            severity=Severity.HIGH,
            can_auto_revise=True,
            suggested_revision=high_revision,
        )

        # Pass low first, but high should be applied first
        result = engine.revise_plan(plan, [low_finding, high_finding])

        assert result.revision_count == 2
        # First applied should be high severity
        assert result.revisions_applied[0].finding.severity == Severity.HIGH

    def test_revise_plan_resolves_dependencies(self, engine: AutoRevisionEngine):
        """Test orphaned dependencies are cleaned up."""
        # Task with dependency on task that will be removed
        task_a = make_task("TASK-A", dependencies=["TASK-B"])
        task_b = make_task("TASK-B")
        plan = make_plan([task_a, task_b])

        # Remove TASK-B
        revision = make_remove_task_revision("TASK-B")
        finding = make_finding(
            can_auto_revise=True,
            suggested_revision=revision,
        )

        result = engine.revise_plan(plan, [finding])

        # TASK-A should no longer have TASK-B in dependencies
        task_a_revised = next(
            t for t in result.revised_plan.all_tasks if t.id == "TASK-A"
        )
        assert "TASK-B" not in task_a_revised.dependencies

    def test_revise_plan_tracks_time(self, engine: AutoRevisionEngine):
        """Test total_time_ms is recorded."""
        plan = make_plan([make_task()])

        result = engine.revise_plan(plan, [])

        assert result.total_time_ms >= 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests with realistic scenarios."""

    def test_add_test_task_scenario(self, engine: AutoRevisionEngine):
        """Test scenario: adding test task for feature."""
        # Feature task without tests
        feature_task = make_task(
            "TASK-FEAT-001",
            title="Implement user authentication",
            description="Add login/logout functionality",
        )
        plan = make_plan([feature_task])

        # Finding from TestRequirementRule
        test_task = make_task(
            "TASK-TST-001",
            title="Add tests for user authentication",
            description="Write tests for login/logout",
            dependencies=["TASK-FEAT-001"],
            tags=["testing"],
        )
        revision = make_add_task_revision(
            test_task,
            rationale="Feature task needs test coverage",
        )
        finding = make_finding(
            rule_id="PLAN.TEST_REQUIREMENT",
            severity=Severity.MEDIUM,
            summary="Feature 'Implement user authentication' needs tests",
            affected_tasks=["TASK-FEAT-001"],
            can_auto_revise=True,
            confidence=0.9,
            suggested_revision=revision,
        )

        result = engine.revise_plan(plan, [finding])

        assert result.was_revised is True
        assert result.revision_count == 1
        assert len(result.revised_plan.all_tasks) == 2

        # Verify test task was added correctly
        test_task_added = next(
            (t for t in result.revised_plan.all_tasks if t.id == "TASK-TST-001"),
            None,
        )
        assert test_task_added is not None
        assert "TASK-FEAT-001" in test_task_added.dependencies
        assert "testing" in test_task_added.tags

    def test_multiple_rules_scenario(self, engine: AutoRevisionEngine):
        """Test scenario: multiple rules finding issues."""
        # API task without tests or docs
        api_task = make_task(
            "TASK-API-001",
            title="Add REST API endpoint",
            description="Create /api/users endpoint",
        )
        plan = make_plan([api_task])

        # Test requirement finding
        test_task = make_task(
            "TASK-TST-001",
            title="Add tests for API endpoint",
            dependencies=["TASK-API-001"],
            tags=["testing"],
        )
        test_revision = make_add_task_revision(test_task)
        test_finding = make_finding(
            rule_id="PLAN.TEST_REQUIREMENT",
            severity=Severity.MEDIUM,
            can_auto_revise=True,
            suggested_revision=test_revision,
        )

        # Doc requirement finding
        doc_task = make_task(
            "TASK-DOC-001",
            title="Document API endpoint",
            dependencies=["TASK-API-001"],
            tags=["documentation"],
        )
        doc_revision = make_add_task_revision(doc_task)
        doc_finding = make_finding(
            rule_id="PLAN.DOC_REQUIREMENT",
            severity=Severity.LOW,
            can_auto_revise=True,
            suggested_revision=doc_revision,
        )

        result = engine.revise_plan(plan, [test_finding, doc_finding])

        assert result.was_revised is True
        assert result.revision_count == 2
        assert len(result.revised_plan.all_tasks) == 3

    def test_duplicate_detection_modify_scenario(self, engine: AutoRevisionEngine):
        """Test scenario: duplicate detection modifies task."""
        task = make_task(
            "TASK-001",
            title="Implement authentication",
            description="Add user auth",
        )
        plan = make_plan([task])

        # Finding suggests modifying description
        new_desc = (
            "Add user auth\n\n"
            "**Note:** Similar to existing AuthService. Review before implementing."
        )
        revision = make_modify_task_revision(
            "TASK-001",
            {
                "description": new_desc,
                "acceptance_criteria": [
                    "Test criterion",
                    "Verify no duplication with existing AuthService",
                ],
            },
        )
        finding = make_finding(
            rule_id="PLAN.DUPLICATE_DETECTION",
            severity=Severity.HIGH,
            summary="Potential duplicate of AuthService",
            can_auto_revise=True,
            suggested_revision=revision,
        )

        result = engine.revise_plan(plan, [finding])

        assert result.was_revised is True
        modified_task = result.revised_plan.all_tasks[0]
        assert "Similar to existing AuthService" in modified_task.description
        assert any("duplication" in c for c in modified_task.acceptance_criteria)


# ============================================================================
# Factory Function Tests
# ============================================================================


class TestFactoryFunction:
    """Tests for the create_auto_revision_engine factory."""

    def test_create_engine_with_config(self, config: PlanGuardrailConfig):
        """Test factory creates engine with config."""
        engine = create_auto_revision_engine(config)

        assert engine is not None
        assert engine.config == config

    def test_create_engine_with_rules(self, config: PlanGuardrailConfig):
        """Test factory creates engine with rules."""
        rules = {"PLAN.TEST": "mock_rule"}
        engine = create_auto_revision_engine(config, rules=rules)

        assert engine.rules == rules
