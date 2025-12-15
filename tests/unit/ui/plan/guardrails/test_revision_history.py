"""Unit tests for revision history management.

Tests cover:
- PlanSnapshot creation and serialization
- RevisionHistoryManager operations (snapshots, rollback, versioning)
- PlanPersistence save/load operations
- ImplementationPlan revision history integration
"""

import tempfile
from pathlib import Path

import pytest

from claude_indexer.rules.base import Severity
from claude_indexer.ui.plan.guardrails.auto_revision import AppliedRevision
from claude_indexer.ui.plan.guardrails.base import (
    PlanRevision,
    PlanValidationFinding,
    RevisionType,
)
from claude_indexer.ui.plan.guardrails.revision_history import (
    PlanPersistence,
    PlanSnapshot,
    RevisionHistoryManager,
)
from claude_indexer.ui.plan.task import ImplementationPlan, Task, TaskGroup

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_task() -> Task:
    """Create a sample task for testing."""
    return Task(
        id="TASK-001",
        title="Test Task",
        description="Test description",
        scope="components",
        priority=2,
        estimated_effort="medium",
        impact=0.7,
        acceptance_criteria=["Test criterion"],
    )


@pytest.fixture
def sample_plan(sample_task: Task) -> ImplementationPlan:
    """Create a sample implementation plan for testing."""
    group = TaskGroup(
        scope="components",
        description="Test group",
        tasks=[sample_task],
    )
    return ImplementationPlan(
        groups=[group],
        quick_wins=[],
        summary="Test plan",
    )


@pytest.fixture
def temp_storage_dir():
    """Create temporary directory for persistence tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_finding() -> PlanValidationFinding:
    """Create a sample validation finding."""
    return PlanValidationFinding(
        rule_id="PLAN.TEST_RULE",
        severity=Severity.MEDIUM,
        summary="Test finding",
        affected_tasks=["TASK-001"],
        confidence=0.9,
    )


@pytest.fixture
def sample_revision() -> PlanRevision:
    """Create a sample plan revision."""
    new_task = Task(
        id="TASK-002",
        title="New Task",
        description="New task description",
        scope="components",
        priority=3,
        estimated_effort="low",
        impact=0.5,
    )
    return PlanRevision(
        revision_type=RevisionType.ADD_TASK,
        rationale="Test revision",
        new_task=new_task,
    )


@pytest.fixture
def sample_applied_revision(
    sample_revision: PlanRevision,
    sample_finding: PlanValidationFinding,
) -> AppliedRevision:
    """Create a sample applied revision."""
    return AppliedRevision(
        revision=sample_revision,
        finding=sample_finding,
        success=True,
    )


# ============================================================================
# PlanSnapshot Tests
# ============================================================================


class TestPlanSnapshot:
    """Tests for PlanSnapshot dataclass."""

    def test_create_snapshot(self, sample_plan: ImplementationPlan):
        """Test snapshot creation with valid data."""
        snapshot = PlanSnapshot(
            version=1,
            snapshot=sample_plan.to_dict(),
            description="Initial snapshot",
        )
        assert snapshot.version == 1
        assert snapshot.description == "Initial snapshot"
        assert snapshot.created_at is not None
        assert snapshot.revision_count_at_snapshot == 0

    def test_snapshot_with_revision_count(self, sample_plan: ImplementationPlan):
        """Test snapshot stores revision count at time of creation."""
        snapshot = PlanSnapshot(
            version=2,
            snapshot=sample_plan.to_dict(),
            description="After revisions",
            revision_count_at_snapshot=5,
        )
        assert snapshot.revision_count_at_snapshot == 5

    def test_snapshot_serialization_roundtrip(self, sample_plan: ImplementationPlan):
        """Test snapshot can be serialized and deserialized."""
        original = PlanSnapshot(
            version=1,
            snapshot=sample_plan.to_dict(),
            description="Test snapshot",
            revision_count_at_snapshot=3,
        )
        data = original.to_dict()
        restored = PlanSnapshot.from_dict(data)

        assert restored.version == original.version
        assert restored.description == original.description
        assert restored.revision_count_at_snapshot == 3
        assert restored.snapshot == original.snapshot

    def test_snapshot_from_dict_defaults(self):
        """Test from_dict handles missing optional fields."""
        data = {
            "version": 1,
            "snapshot": {"summary": "test"},
        }
        snapshot = PlanSnapshot.from_dict(data)

        assert snapshot.version == 1
        assert snapshot.description == ""
        assert snapshot.revision_count_at_snapshot == 0


# ============================================================================
# RevisionHistoryManager Tests
# ============================================================================


class TestRevisionHistoryManager:
    """Tests for RevisionHistoryManager class."""

    def test_create_snapshot(self, sample_plan: ImplementationPlan):
        """Test creating a snapshot of a plan."""
        manager = RevisionHistoryManager()
        snapshot = manager.create_snapshot(sample_plan, "Before revision")

        assert snapshot.version == 1
        assert snapshot.description == "Before revision"
        assert manager.version_count == 1

    def test_multiple_snapshots_increment_version(
        self, sample_plan: ImplementationPlan
    ):
        """Test version numbers auto-increment."""
        manager = RevisionHistoryManager()
        s1 = manager.create_snapshot(sample_plan, "v1")
        s2 = manager.create_snapshot(sample_plan, "v2")
        s3 = manager.create_snapshot(sample_plan, "v3")

        assert s1.version == 1
        assert s2.version == 2
        assert s3.version == 3
        assert manager.version_count == 3

    def test_get_snapshot_existing(self, sample_plan: ImplementationPlan):
        """Test retrieving an existing snapshot by version."""
        manager = RevisionHistoryManager()
        manager.create_snapshot(sample_plan, "v1")
        manager.create_snapshot(sample_plan, "v2")

        snapshot = manager.get_snapshot(1)
        assert snapshot is not None
        assert snapshot.description == "v1"

        snapshot = manager.get_snapshot(2)
        assert snapshot is not None
        assert snapshot.description == "v2"

    def test_get_snapshot_nonexistent(self, sample_plan: ImplementationPlan):
        """Test retrieving nonexistent snapshot returns None."""
        manager = RevisionHistoryManager()
        manager.create_snapshot(sample_plan, "v1")

        assert manager.get_snapshot(99) is None

    def test_get_latest_snapshot(self, sample_plan: ImplementationPlan):
        """Test getting the most recent snapshot."""
        manager = RevisionHistoryManager()
        manager.create_snapshot(sample_plan, "v1")
        manager.create_snapshot(sample_plan, "v2")
        manager.create_snapshot(sample_plan, "v3")

        latest = manager.get_latest_snapshot()
        assert latest is not None
        assert latest.version == 3
        assert latest.description == "v3"

    def test_get_latest_snapshot_empty(self):
        """Test getting latest snapshot when none exist."""
        manager = RevisionHistoryManager()
        assert manager.get_latest_snapshot() is None

    def test_list_versions(self, sample_plan: ImplementationPlan):
        """Test listing all available versions."""
        manager = RevisionHistoryManager()
        manager.create_snapshot(sample_plan, "First")
        manager.create_snapshot(sample_plan, "Second")

        versions = manager.list_versions()
        assert len(versions) == 2
        assert versions[0][0] == 1  # version
        assert versions[0][2] == "First"  # description
        assert versions[1][0] == 2
        assert versions[1][2] == "Second"

    def test_rollback_to_version(self, sample_plan: ImplementationPlan):
        """Test rollback restores plan state."""
        manager = RevisionHistoryManager()

        # Create snapshot
        manager.create_snapshot(sample_plan, "Before changes")

        # Modify plan
        new_task = Task(
            id="TASK-002",
            title="New Task",
            description="Added later",
            scope="components",
            priority=1,
            estimated_effort="low",
            impact=0.5,
        )
        sample_plan.groups[0].tasks.append(new_task)

        assert len(sample_plan.all_tasks) == 2

        # Rollback
        restored = manager.rollback_to_version(sample_plan, version=1)

        assert len(restored.all_tasks) == 1
        assert restored.all_tasks[0].id == "TASK-001"

    def test_rollback_preserves_history_by_default(
        self,
        sample_plan: ImplementationPlan,
        sample_applied_revision: AppliedRevision,
    ):
        """Test rollback keeps full revision history by default."""
        manager = RevisionHistoryManager()
        sample_plan.add_revisions([sample_applied_revision])
        manager.create_snapshot(sample_plan, "Before changes")

        restored = manager.rollback_to_version(
            sample_plan, version=1, preserve_history=True
        )

        assert restored.revision_count == 1

    def test_rollback_truncates_history_when_requested(
        self,
        sample_plan: ImplementationPlan,
        sample_applied_revision: AppliedRevision,
    ):
        """Test rollback can truncate revision history."""
        manager = RevisionHistoryManager()
        manager.create_snapshot(sample_plan, "Before revisions")

        # Add revisions after snapshot
        sample_plan.add_revisions([sample_applied_revision])
        assert sample_plan.revision_count == 1

        # Rollback with truncation
        restored = manager.rollback_to_version(
            sample_plan, version=1, preserve_history=False
        )

        assert restored.revision_count == 0

    def test_rollback_invalid_version_raises(self, sample_plan: ImplementationPlan):
        """Test rollback with invalid version raises ValueError."""
        manager = RevisionHistoryManager()

        with pytest.raises(ValueError, match="Version 99 not found"):
            manager.rollback_to_version(sample_plan, version=99)

    def test_manager_serialization_roundtrip(self, sample_plan: ImplementationPlan):
        """Test manager can be serialized and deserialized."""
        manager = RevisionHistoryManager()
        manager.create_snapshot(sample_plan, "v1")
        manager.create_snapshot(sample_plan, "v2")

        data = manager.to_dict()
        restored = RevisionHistoryManager.from_dict(data)

        assert restored.version_count == 2
        assert restored._next_version == 3
        assert restored.get_snapshot(1).description == "v1"
        assert restored.get_snapshot(2).description == "v2"

    def test_snapshot_excludes_revision_history(
        self,
        sample_plan: ImplementationPlan,
        sample_applied_revision: AppliedRevision,
    ):
        """Test snapshots don't include revision_history to avoid bloat."""
        sample_plan.add_revisions([sample_applied_revision])
        manager = RevisionHistoryManager()
        snapshot = manager.create_snapshot(sample_plan, "With history")

        # Snapshot should not contain revision_history
        assert "revision_history" not in snapshot.snapshot
        assert "revision_count" not in snapshot.snapshot


# ============================================================================
# PlanPersistence Tests
# ============================================================================


class TestPlanPersistence:
    """Tests for PlanPersistence class."""

    def test_init_creates_directory(self, temp_storage_dir: Path):
        """Test persistence creates storage directory."""
        subdir = temp_storage_dir / "plans" / "nested"
        PlanPersistence(subdir)  # Constructor creates directory
        assert subdir.exists()

    def test_save_and_load_plan(
        self, sample_plan: ImplementationPlan, temp_storage_dir: Path
    ):
        """Test saving and loading a plan."""
        persistence = PlanPersistence(temp_storage_dir)

        path = persistence.save_plan(sample_plan, "test-plan")
        assert path.exists()
        assert path.suffix == ".json"

        loaded = persistence.load_plan("test-plan")
        assert loaded is not None
        assert loaded.summary == sample_plan.summary
        assert len(loaded.all_tasks) == 1

    def test_save_plan_with_revision_history(
        self,
        sample_plan: ImplementationPlan,
        sample_applied_revision: AppliedRevision,
        temp_storage_dir: Path,
    ):
        """Test plan with revision history is saved and restored."""
        sample_plan.add_revisions([sample_applied_revision])
        persistence = PlanPersistence(temp_storage_dir)

        persistence.save_plan(sample_plan, "plan-with-history")
        loaded = persistence.load_plan("plan-with-history")

        assert loaded is not None
        assert loaded.revision_count == 1
        assert loaded.revision_history[0].success is True

    def test_load_nonexistent_plan_returns_none(self, temp_storage_dir: Path):
        """Test loading nonexistent plan returns None."""
        persistence = PlanPersistence(temp_storage_dir)

        loaded = persistence.load_plan("nonexistent")
        assert loaded is None

    def test_save_and_load_history_manager(
        self, sample_plan: ImplementationPlan, temp_storage_dir: Path
    ):
        """Test saving and loading history manager."""
        persistence = PlanPersistence(temp_storage_dir)

        manager = RevisionHistoryManager()
        manager.create_snapshot(sample_plan, "v1")
        manager.create_snapshot(sample_plan, "v2")

        persistence.save_history_manager(manager, "test-plan")

        loaded = persistence.load_history_manager("test-plan")
        assert loaded is not None
        assert loaded.version_count == 2
        assert loaded.get_snapshot(1).description == "v1"

    def test_load_nonexistent_history_manager_returns_none(
        self, temp_storage_dir: Path
    ):
        """Test loading nonexistent history manager returns None."""
        persistence = PlanPersistence(temp_storage_dir)

        loaded = persistence.load_history_manager("nonexistent")
        assert loaded is None

    def test_list_plans(self, sample_plan: ImplementationPlan, temp_storage_dir: Path):
        """Test listing all saved plans."""
        persistence = PlanPersistence(temp_storage_dir)

        persistence.save_plan(sample_plan, "plan-a")
        persistence.save_plan(sample_plan, "plan-b")
        persistence.save_plan(sample_plan, "plan-c")

        plans = persistence.list_plans()
        assert len(plans) == 3
        assert "plan-a" in plans
        assert "plan-b" in plans
        assert "plan-c" in plans

    def test_list_plans_empty(self, temp_storage_dir: Path):
        """Test listing plans when none exist."""
        persistence = PlanPersistence(temp_storage_dir)
        plans = persistence.list_plans()
        assert plans == []

    def test_delete_plan(self, sample_plan: ImplementationPlan, temp_storage_dir: Path):
        """Test deleting a plan and its history."""
        persistence = PlanPersistence(temp_storage_dir)

        persistence.save_plan(sample_plan, "to-delete")
        manager = RevisionHistoryManager()
        manager.create_snapshot(sample_plan, "v1")
        persistence.save_history_manager(manager, "to-delete")

        assert persistence.plan_exists("to-delete")

        deleted = persistence.delete_plan("to-delete")
        assert deleted is True
        assert not persistence.plan_exists("to-delete")

    def test_delete_nonexistent_plan(self, temp_storage_dir: Path):
        """Test deleting nonexistent plan returns False."""
        persistence = PlanPersistence(temp_storage_dir)
        deleted = persistence.delete_plan("nonexistent")
        assert deleted is False

    def test_plan_exists(self, sample_plan: ImplementationPlan, temp_storage_dir: Path):
        """Test checking if plan exists."""
        persistence = PlanPersistence(temp_storage_dir)

        assert persistence.plan_exists("missing") is False

        persistence.save_plan(sample_plan, "exists")
        assert persistence.plan_exists("exists") is True

    def test_safe_name_handling(
        self, sample_plan: ImplementationPlan, temp_storage_dir: Path
    ):
        """Test names with special characters are handled safely."""
        persistence = PlanPersistence(temp_storage_dir)

        # Names with slashes should be sanitized
        persistence.save_plan(sample_plan, "path/to/plan")
        assert persistence.plan_exists("path/to/plan")

        loaded = persistence.load_plan("path/to/plan")
        assert loaded is not None


# ============================================================================
# ImplementationPlan Revision History Tests
# ============================================================================


class TestImplementationPlanRevisionHistory:
    """Tests for ImplementationPlan revision history integration."""

    def test_revision_history_default_empty(self):
        """Test new plans have empty revision history."""
        plan = ImplementationPlan()
        assert plan.revision_history == []
        assert plan.revision_count == 0

    def test_add_revisions(
        self,
        sample_plan: ImplementationPlan,
        sample_applied_revision: AppliedRevision,
    ):
        """Test adding revisions to plan history."""
        sample_plan.add_revisions([sample_applied_revision])

        assert sample_plan.revision_count == 1
        assert len(sample_plan.revision_history) == 1
        assert sample_plan.revision_history[0] == sample_applied_revision

    def test_add_multiple_revisions(
        self,
        sample_plan: ImplementationPlan,
        sample_applied_revision: AppliedRevision,
    ):
        """Test adding multiple revisions."""
        sample_plan.add_revisions([sample_applied_revision])
        sample_plan.add_revisions([sample_applied_revision, sample_applied_revision])

        assert sample_plan.revision_count == 3

    def test_revision_history_serialization_roundtrip(
        self,
        sample_plan: ImplementationPlan,
        sample_applied_revision: AppliedRevision,
    ):
        """Test revision history survives serialization."""
        sample_plan.add_revisions([sample_applied_revision])

        data = sample_plan.to_dict()
        restored = ImplementationPlan.from_dict(data)

        assert restored.revision_count == 1
        assert restored.revision_history[0].success is True
        assert (
            restored.revision_history[0].revision.revision_type == RevisionType.ADD_TASK
        )

    def test_backward_compatible_deserialization(self):
        """Test old plan format without revision_history loads correctly."""
        old_format = {
            "groups": [],
            "quick_wins": [],
            "summary": "Old plan",
            "generated_at": "2024-01-01T00:00:00",
        }

        plan = ImplementationPlan.from_dict(old_format)

        assert plan.revision_history == []
        assert plan.revision_count == 0
        assert plan.summary == "Old plan"

    def test_format_revision_history_empty(self):
        """Test formatting empty revision history."""
        plan = ImplementationPlan()
        output = plan.format_revision_history()

        assert "Plan Revision History" in output
        assert "No revisions" in output

    def test_format_revision_history_with_revisions(
        self,
        sample_plan: ImplementationPlan,
        sample_applied_revision: AppliedRevision,
    ):
        """Test formatting revision history with entries."""
        sample_plan.add_revisions([sample_applied_revision])
        output = sample_plan.format_revision_history()

        assert "Plan Revision History" in output
        assert "Total revisions" in output
        assert "1" in output
        assert "Add Task" in output
        assert "PLAN.TEST_RULE" in output
        assert "Success" in output

    def test_format_revision_history_failed_revision(
        self,
        sample_plan: ImplementationPlan,
        sample_revision: PlanRevision,
        sample_finding: PlanValidationFinding,
    ):
        """Test formatting shows failed revision status."""
        failed = AppliedRevision(
            revision=sample_revision,
            finding=sample_finding,
            success=False,
            error="Conflict detected",
        )
        sample_plan.add_revisions([failed])
        output = sample_plan.format_revision_history()

        assert "Failed" in output
        assert "Conflict detected" in output

    def test_format_revision_history_modify_task(
        self,
        sample_plan: ImplementationPlan,
        sample_finding: PlanValidationFinding,
    ):
        """Test formatting MODIFY_TASK revision type."""
        revision = PlanRevision(
            revision_type=RevisionType.MODIFY_TASK,
            rationale="Update task",
            target_task_id="TASK-001",
            modifications={"title": "New Title", "priority": 1},
        )
        applied = AppliedRevision(
            revision=revision,
            finding=sample_finding,
            success=True,
        )
        sample_plan.add_revisions([applied])
        output = sample_plan.format_revision_history()

        assert "Modify Task" in output
        assert "TASK-001" in output
        assert "title" in output
        assert "priority" in output

    def test_format_revision_history_remove_task(
        self,
        sample_plan: ImplementationPlan,
        sample_finding: PlanValidationFinding,
    ):
        """Test formatting REMOVE_TASK revision type."""
        revision = PlanRevision(
            revision_type=RevisionType.REMOVE_TASK,
            rationale="Remove obsolete task",
            target_task_id="TASK-001",
        )
        applied = AppliedRevision(
            revision=revision,
            finding=sample_finding,
            success=True,
        )
        sample_plan.add_revisions([applied])
        output = sample_plan.format_revision_history()

        assert "Remove Task" in output
        assert "Removed" in output
        assert "TASK-001" in output

    def test_format_revision_history_add_dependency(
        self,
        sample_plan: ImplementationPlan,
        sample_finding: PlanValidationFinding,
    ):
        """Test formatting ADD_DEPENDENCY revision type."""
        revision = PlanRevision(
            revision_type=RevisionType.ADD_DEPENDENCY,
            rationale="Add task dependency",
            dependency_additions=[("TASK-002", "TASK-001")],
        )
        applied = AppliedRevision(
            revision=revision,
            finding=sample_finding,
            success=True,
        )
        sample_plan.add_revisions([applied])
        output = sample_plan.format_revision_history()

        assert "Add Dependency" in output
        assert "TASK-002" in output
        assert "TASK-001" in output

    def test_to_dict_includes_revision_count(
        self,
        sample_plan: ImplementationPlan,
        sample_applied_revision: AppliedRevision,
    ):
        """Test to_dict includes revision count for convenience."""
        sample_plan.add_revisions([sample_applied_revision])
        data = sample_plan.to_dict()

        assert data["revision_count"] == 1
        assert len(data["revision_history"]) == 1
