"""Revision history management for implementation plans.

This module provides snapshot tracking and rollback capability for
implementation plans, allowing users to restore previous versions
and persist plans to disk.

Classes:
    PlanSnapshot: Snapshot of a plan at a point in time
    RevisionHistoryManager: Manager for plan snapshots and versioning
    PlanPersistence: Save/load plans and history to JSON files
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..task import ImplementationPlan


@dataclass
class PlanSnapshot:
    """Snapshot of an implementation plan at a point in time.

    Stores a complete serialized copy of the plan state
    for rollback capability. The revision_history is excluded
    from the snapshot to avoid bloat.
    """

    version: int
    snapshot: dict[str, Any]  # Serialized plan (without revision_history)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    description: str = ""
    revision_count_at_snapshot: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "snapshot": self.snapshot,
            "created_at": self.created_at,
            "description": self.description,
            "revision_count_at_snapshot": self.revision_count_at_snapshot,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanSnapshot":
        """Create PlanSnapshot from dictionary."""
        return cls(
            version=data["version"],
            snapshot=data["snapshot"],
            created_at=data.get("created_at", datetime.now().isoformat()),
            description=data.get("description", ""),
            revision_count_at_snapshot=data.get("revision_count_at_snapshot", 0),
        )


@dataclass
class RevisionHistoryManager:
    """Manager for plan snapshots and version history.

    Tracks snapshots of a plan at various points in time,
    enabling rollback to previous versions.
    """

    snapshots: list[PlanSnapshot] = field(default_factory=list)
    _next_version: int = field(default=1, repr=False)

    def create_snapshot(
        self,
        plan: "ImplementationPlan",
        description: str = "",
    ) -> PlanSnapshot:
        """Create a snapshot of the current plan state.

        Args:
            plan: Implementation plan to snapshot.
            description: Optional description of this snapshot.

        Returns:
            The created PlanSnapshot.
        """
        # Serialize plan without revision_history to avoid bloat
        plan_dict = plan.to_dict()
        plan_dict.pop("revision_history", None)
        plan_dict.pop("revision_count", None)

        snapshot = PlanSnapshot(
            version=self._next_version,
            snapshot=plan_dict,
            description=description,
            revision_count_at_snapshot=plan.revision_count,
        )

        self.snapshots.append(snapshot)
        self._next_version += 1

        return snapshot

    def rollback_to_version(
        self,
        plan: "ImplementationPlan",
        version: int,
        preserve_history: bool = True,
    ) -> "ImplementationPlan":
        """Restore a plan to a previous snapshot version.

        Args:
            plan: Current plan (used for revision history if preserved).
            version: Version number to restore to.
            preserve_history: If True, keeps full revision history.
                            If False, truncates history to snapshot point.

        Returns:
            Restored ImplementationPlan.

        Raises:
            ValueError: If version not found.
        """
        from ..task import ImplementationPlan

        snapshot = self.get_snapshot(version)
        if snapshot is None:
            raise ValueError(f"Version {version} not found in history")

        # Restore plan from snapshot
        restored_plan = ImplementationPlan.from_dict(snapshot.snapshot)

        # Handle revision history
        if preserve_history:
            # Keep full history
            restored_plan.revision_history = plan.revision_history.copy()
        else:
            # Truncate history to snapshot point
            restored_plan.revision_history = plan.revision_history[
                : snapshot.revision_count_at_snapshot
            ]

        return restored_plan

    def get_snapshot(self, version: int) -> PlanSnapshot | None:
        """Get a specific snapshot by version number.

        Args:
            version: Version number to retrieve.

        Returns:
            PlanSnapshot if found, None otherwise.
        """
        for snapshot in self.snapshots:
            if snapshot.version == version:
                return snapshot
        return None

    def get_latest_snapshot(self) -> PlanSnapshot | None:
        """Get the most recent snapshot.

        Returns:
            Most recent PlanSnapshot or None if no snapshots exist.
        """
        if not self.snapshots:
            return None
        return self.snapshots[-1]

    def list_versions(self) -> list[tuple[int, str, str]]:
        """List all available versions.

        Returns:
            List of (version, created_at, description) tuples.
        """
        return [(s.version, s.created_at, s.description) for s in self.snapshots]

    @property
    def version_count(self) -> int:
        """Number of snapshots stored."""
        return len(self.snapshots)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "snapshots": [s.to_dict() for s in self.snapshots],
            "next_version": self._next_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RevisionHistoryManager":
        """Create RevisionHistoryManager from dictionary."""
        manager = cls(
            snapshots=[PlanSnapshot.from_dict(s) for s in data.get("snapshots", [])],
        )
        manager._next_version = data.get("next_version", len(manager.snapshots) + 1)
        return manager


class PlanPersistence:
    """Persistence layer for implementation plans and revision history.

    Saves and loads plans and their associated history managers
    as JSON files in a configurable directory.
    """

    PLAN_SUFFIX = "_plan.json"
    HISTORY_SUFFIX = "_history.json"

    def __init__(self, storage_dir: Path | str):
        """Initialize persistence with storage directory.

        Args:
            storage_dir: Directory to store plan files.
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _plan_path(self, name: str) -> Path:
        """Get file path for a plan."""
        safe_name = name.replace("/", "_").replace("\\", "_")
        return self.storage_dir / f"{safe_name}{self.PLAN_SUFFIX}"

    def _history_path(self, name: str) -> Path:
        """Get file path for a history manager."""
        safe_name = name.replace("/", "_").replace("\\", "_")
        return self.storage_dir / f"{safe_name}{self.HISTORY_SUFFIX}"

    def save_plan(
        self,
        plan: "ImplementationPlan",
        name: str,
    ) -> Path:
        """Save an implementation plan to disk.

        Args:
            plan: Plan to save.
            name: Name/identifier for the plan.

        Returns:
            Path where plan was saved.
        """
        path = self._plan_path(name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(plan.to_dict(), f, indent=2)
        return path

    def load_plan(self, name: str) -> "ImplementationPlan | None":
        """Load an implementation plan from disk.

        Args:
            name: Name/identifier of the plan.

        Returns:
            Loaded ImplementationPlan or None if not found.
        """
        from ..task import ImplementationPlan

        path = self._plan_path(name)
        if not path.exists():
            return None

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        return ImplementationPlan.from_dict(data)

    def save_history_manager(
        self,
        manager: RevisionHistoryManager,
        plan_name: str,
    ) -> Path:
        """Save a revision history manager to disk.

        Args:
            manager: History manager to save.
            plan_name: Associated plan name.

        Returns:
            Path where history was saved.
        """
        path = self._history_path(plan_name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manager.to_dict(), f, indent=2)
        return path

    def load_history_manager(self, plan_name: str) -> RevisionHistoryManager | None:
        """Load a revision history manager from disk.

        Args:
            plan_name: Associated plan name.

        Returns:
            Loaded RevisionHistoryManager or None if not found.
        """
        path = self._history_path(plan_name)
        if not path.exists():
            return None

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        return RevisionHistoryManager.from_dict(data)

    def delete_plan(self, name: str) -> bool:
        """Delete a plan and its history from disk.

        Args:
            name: Name/identifier of the plan.

        Returns:
            True if files were deleted, False if not found.
        """
        plan_path = self._plan_path(name)
        history_path = self._history_path(name)

        deleted = False
        if plan_path.exists():
            plan_path.unlink()
            deleted = True
        if history_path.exists():
            history_path.unlink()
            deleted = True

        return deleted

    def list_plans(self) -> list[str]:
        """List all saved plan names.

        Returns:
            List of plan names (without suffixes).
        """
        plans = []
        for path in self.storage_dir.glob(f"*{self.PLAN_SUFFIX}"):
            name = path.name[: -len(self.PLAN_SUFFIX)]
            plans.append(name)
        return sorted(plans)

    def plan_exists(self, name: str) -> bool:
        """Check if a plan exists.

        Args:
            name: Name/identifier of the plan.

        Returns:
            True if plan file exists.
        """
        return self._plan_path(name).exists()


__all__ = [
    "PlanPersistence",
    "PlanSnapshot",
    "RevisionHistoryManager",
]
