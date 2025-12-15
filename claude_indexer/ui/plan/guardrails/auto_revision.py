"""Auto-revision engine for plan guardrails.

This module provides the AutoRevisionEngine that automatically applies
revisions to implementation plans based on validation findings from
plan guardrail rules.
"""

import time
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from claude_indexer.rules.base import Severity

from .base import PlanRevision, PlanValidationFinding, PlanValidationRule, RevisionType

if TYPE_CHECKING:
    from claude_indexer.ui.plan.task import ImplementationPlan

    from .config import PlanGuardrailConfig


@dataclass
class AppliedRevision:
    """Record of a successfully applied revision.

    Tracks the revision that was applied, the finding it addressed,
    and when it was applied.
    """

    revision: PlanRevision
    finding: PlanValidationFinding
    success: bool
    error: str | None = None
    applied_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "revision": self.revision.to_dict(),
            "finding": self.finding.to_dict(),
            "success": self.success,
            "error": self.error,
            "applied_at": self.applied_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppliedRevision":
        """Create AppliedRevision from dictionary."""
        return cls(
            revision=PlanRevision.from_dict(data["revision"]),
            finding=PlanValidationFinding.from_dict(data["finding"]),
            success=data["success"],
            error=data.get("error"),
            applied_at=data.get("applied_at", datetime.now().isoformat()),
        )


@dataclass
class RevisedPlan:
    """Result of auto-revision process.

    Contains the original and revised plans, along with metadata
    about all revisions that were applied or skipped.
    """

    original_plan: "ImplementationPlan"
    revised_plan: "ImplementationPlan"
    revisions_applied: list[AppliedRevision] = field(default_factory=list)
    revisions_skipped: list[tuple[PlanRevision, str]] = field(default_factory=list)
    iterations_used: int = 0
    total_time_ms: float = 0.0

    @property
    def was_revised(self) -> bool:
        """Check if any revisions were applied."""
        return len(self.revisions_applied) > 0

    @property
    def revision_count(self) -> int:
        """Get the number of revisions applied."""
        return len(self.revisions_applied)

    @property
    def skipped_count(self) -> int:
        """Get the number of revisions skipped."""
        return len(self.revisions_skipped)

    def format_audit_trail(self) -> str:
        """Format a human-readable audit trail of all revisions.

        Returns:
            Markdown-formatted audit trail string.
        """
        lines = ["## Plan Revisions Applied", ""]

        if not self.revisions_applied and not self.revisions_skipped:
            lines.append("*No revisions were needed.*")
            return "\n".join(lines)

        # Applied revisions
        if self.revisions_applied:
            for i, applied in enumerate(self.revisions_applied, 1):
                rev = applied.revision
                finding = applied.finding

                lines.append(
                    f"### {i}. {rev.revision_type.value.replace('_', ' ').title()}"
                )
                lines.append(f"- **Rule**: {finding.rule_id}")
                lines.append(f"- **Reason**: {rev.rationale}")
                lines.append(f"- **Confidence**: {finding.confidence:.0%}")

                if rev.revision_type == RevisionType.ADD_TASK and rev.new_task:
                    lines.append(
                        f"- **Added**: Task '{rev.new_task.id}' - {rev.new_task.title}"
                    )
                elif rev.revision_type == RevisionType.MODIFY_TASK:
                    lines.append(f"- **Modified**: Task '{rev.target_task_id}'")
                    if rev.modifications:
                        lines.append(
                            f"- **Changes**: {', '.join(rev.modifications.keys())}"
                        )
                elif rev.revision_type == RevisionType.REMOVE_TASK:
                    lines.append(f"- **Removed**: Task '{rev.target_task_id}'")
                elif rev.revision_type == RevisionType.ADD_DEPENDENCY:
                    for from_id, to_id in rev.dependency_additions:
                        lines.append(f"- **Dependency**: {from_id} → {to_id}")

                lines.append("")

        # Skipped revisions
        if self.revisions_skipped:
            lines.append("### Skipped Revisions")
            lines.append("")
            for rev, reason in self.revisions_skipped:
                lines.append(f"- {rev.revision_type.value}: {reason}")
            lines.append("")

        # Summary
        lines.append("---")
        lines.append(
            f"*Applied {self.revision_count} revision(s), "
            f"skipped {self.skipped_count}, "
            f"in {self.iterations_used} iteration(s) "
            f"({self.total_time_ms:.1f}ms)*"
        )

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "original_plan": self.original_plan.to_dict(),
            "revised_plan": self.revised_plan.to_dict(),
            "revisions_applied": [r.to_dict() for r in self.revisions_applied],
            "revisions_skipped": [
                (r.to_dict(), reason) for r, reason in self.revisions_skipped
            ],
            "iterations_used": self.iterations_used,
            "total_time_ms": self.total_time_ms,
            "was_revised": self.was_revised,
            "revision_count": self.revision_count,
            "skipped_count": self.skipped_count,
        }


# Revision type application order (for proper sequencing)
REVISION_TYPE_ORDER = [
    RevisionType.ADD_TASK,  # Create new tasks first
    RevisionType.ADD_DEPENDENCY,  # Link tasks after all exist
    RevisionType.MODIFY_TASK,  # Update existing tasks
    RevisionType.REORDER_TASKS,  # Reorder after modifications
    RevisionType.REMOVE_TASK,  # Remove tasks last
]

# Severity order for sorting (higher severity = lower index = process first)
SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
}


class AutoRevisionEngine:
    """Engine for automatically applying plan revisions.

    Takes validation findings from the PlanGuardrailEngine and applies
    auto-revisions to the implementation plan. Handles conflicts,
    circular dependencies, and limits iterations to prevent infinite loops.
    """

    MAX_ITERATIONS = 3  # Prevent infinite loops

    def __init__(
        self,
        config: "PlanGuardrailConfig",
        rules: dict[str, PlanValidationRule] | None = None,
    ):
        """Initialize the auto-revision engine.

        Args:
            config: Plan guardrail configuration
            rules: Optional dict of rule_id -> rule instance for getting revisions
        """
        self.config = config
        self.rules = rules or {}

    def revise_plan(
        self,
        plan: "ImplementationPlan",
        findings: list[PlanValidationFinding],
    ) -> RevisedPlan:
        """Apply auto-revisions to a plan based on findings.

        Args:
            plan: The implementation plan to revise
            findings: List of validation findings to address

        Returns:
            RevisedPlan with original, revised plans and audit trail
        """
        start_time = time.time()
        current_plan = deepcopy(plan)
        all_applied: list[AppliedRevision] = []
        all_skipped: list[tuple[PlanRevision, str]] = []
        iterations_used = 0

        # Check if auto-revision is enabled
        if not self.config.auto_revise:
            return RevisedPlan(
                original_plan=plan,
                revised_plan=current_plan,
                revisions_applied=[],
                revisions_skipped=[],
                iterations_used=0,
                total_time_ms=(time.time() - start_time) * 1000,
            )

        # Filter to findings that can be auto-revised
        revisable_findings = [
            f
            for f in findings
            if f.can_auto_revise
            and f.suggested_revision is not None
            and self.config.should_auto_revise(f.rule_id, f.confidence)
        ]

        # Track which findings have been processed
        processed_finding_ids: set[str] = set()

        for iteration in range(self.MAX_ITERATIONS):
            # Check max revisions limit
            if len(all_applied) >= self.config.max_revisions_per_plan:
                break

            # Get applicable revisions for this iteration
            revisions_to_apply = self._get_applicable_revisions(
                revisable_findings, processed_finding_ids
            )

            if not revisions_to_apply:
                break  # No more revisions to apply

            # Count this as an iteration since we have revisions to process
            iterations_used = iteration + 1

            # Sort revisions by priority
            sorted_revisions = self._sort_revisions_by_priority(revisions_to_apply)

            # Apply revisions
            applied_this_iter = 0
            for revision, finding in sorted_revisions:
                # Check max revisions limit
                if len(all_applied) >= self.config.max_revisions_per_plan:
                    break

                # Check for conflicts
                conflict = self._check_conflicts(current_plan, revision)
                if conflict:
                    all_skipped.append((revision, conflict))
                    processed_finding_ids.add(self._finding_id(finding))
                    continue

                # Try to apply the revision
                new_plan, error = self._apply_revision(current_plan, revision)
                if error:
                    all_skipped.append((revision, error))
                    processed_finding_ids.add(self._finding_id(finding))
                    continue

                # Success!
                current_plan = new_plan
                all_applied.append(
                    AppliedRevision(
                        revision=revision,
                        finding=finding,
                        success=True,
                    )
                )
                processed_finding_ids.add(self._finding_id(finding))
                applied_this_iter += 1

            if applied_this_iter == 0:
                break  # No progress made, stop iterating

        # Resolve dependencies after all revisions
        current_plan = self._resolve_dependencies(current_plan)

        return RevisedPlan(
            original_plan=plan,
            revised_plan=current_plan,
            revisions_applied=all_applied,
            revisions_skipped=all_skipped,
            iterations_used=iterations_used,
            total_time_ms=(time.time() - start_time) * 1000,
        )

    def _finding_id(self, finding: PlanValidationFinding) -> str:
        """Generate a unique ID for a finding to track processing."""
        tasks = ",".join(finding.affected_tasks)
        return f"{finding.rule_id}:{tasks}:{finding.summary[:50]}"

    def _get_applicable_revisions(
        self,
        findings: list[PlanValidationFinding],
        processed: set[str],
    ) -> list[tuple[PlanRevision, PlanValidationFinding]]:
        """Get revisions that haven't been processed yet.

        Args:
            findings: All revisable findings
            processed: Set of finding IDs already processed

        Returns:
            List of (revision, finding) tuples to apply
        """
        result = []
        for finding in findings:
            if self._finding_id(finding) in processed:
                continue
            if finding.suggested_revision is not None:
                result.append((finding.suggested_revision, finding))
        return result

    def _sort_revisions_by_priority(
        self,
        revisions: list[tuple[PlanRevision, PlanValidationFinding]],
    ) -> list[tuple[PlanRevision, PlanValidationFinding]]:
        """Sort revisions by severity (highest first) then by type order.

        Args:
            revisions: List of (revision, finding) tuples

        Returns:
            Sorted list with highest priority revisions first
        """

        def sort_key(
            item: tuple[PlanRevision, PlanValidationFinding],
        ) -> tuple[int, int]:
            revision, finding = item
            severity_rank = SEVERITY_ORDER.get(finding.severity, 3)
            type_rank = (
                REVISION_TYPE_ORDER.index(revision.revision_type)
                if revision.revision_type in REVISION_TYPE_ORDER
                else len(REVISION_TYPE_ORDER)
            )
            return (severity_rank, type_rank)

        return sorted(revisions, key=sort_key)

    def _check_conflicts(
        self,
        plan: "ImplementationPlan",
        revision: PlanRevision,
    ) -> str | None:
        """Check if a revision would cause conflicts.

        Args:
            plan: Current plan state
            revision: Revision to check

        Returns:
            Conflict description if conflict exists, None otherwise
        """
        if revision.revision_type == RevisionType.ADD_TASK:
            if revision.new_task is None:
                return "ADD_TASK revision missing new_task"
            # Check if task ID already exists
            existing_ids = {t.id for t in plan.all_tasks}
            if revision.new_task.id in existing_ids:
                return f"Task ID '{revision.new_task.id}' already exists"

        elif revision.revision_type == RevisionType.MODIFY_TASK:
            if revision.target_task_id is None:
                return "MODIFY_TASK revision missing target_task_id"
            # Check if target task exists
            existing_ids = {t.id for t in plan.all_tasks}
            if revision.target_task_id not in existing_ids:
                return f"Target task '{revision.target_task_id}' does not exist"

        elif revision.revision_type == RevisionType.REMOVE_TASK:
            if revision.target_task_id is None:
                return "REMOVE_TASK revision missing target_task_id"
            # Check if target task exists
            existing_ids = {t.id for t in plan.all_tasks}
            if revision.target_task_id not in existing_ids:
                return f"Target task '{revision.target_task_id}' does not exist"

        elif revision.revision_type == RevisionType.ADD_DEPENDENCY:
            # Check for circular dependencies
            for from_id, to_id in revision.dependency_additions:
                if from_id == to_id:
                    return f"Self-dependency not allowed: {from_id}"
                if self._would_create_cycle(plan, from_id, to_id):
                    return f"Would create circular dependency: {from_id} -> {to_id}"
                # Check that both tasks exist
                existing_ids = {t.id for t in plan.all_tasks}
                if from_id not in existing_ids:
                    return f"Source task '{from_id}' does not exist"
                if to_id not in existing_ids:
                    return f"Target task '{to_id}' does not exist"

        elif revision.revision_type == RevisionType.REORDER_TASKS:
            if revision.target_task_id is None:
                return "REORDER_TASKS revision missing target_task_id"
            existing_ids = {t.id for t in plan.all_tasks}
            if revision.target_task_id not in existing_ids:
                return f"Target task '{revision.target_task_id}' does not exist"

        return None

    def _get_task_dependency_graph(
        self,
        plan: "ImplementationPlan",
    ) -> dict[str, set[str]]:
        """Build a dependency graph from the plan.

        Args:
            plan: Implementation plan

        Returns:
            Dict mapping task_id -> set of task IDs it depends on
        """
        graph: dict[str, set[str]] = defaultdict(set)
        for task in plan.all_tasks:
            graph[task.id]  # Ensure all tasks are in graph
            for dep_id in task.dependencies:
                graph[task.id].add(dep_id)
        return graph

    def _would_create_cycle(
        self,
        plan: "ImplementationPlan",
        from_id: str,
        to_id: str,
    ) -> bool:
        """Check if adding a dependency would create a cycle.

        Args:
            plan: Current plan
            from_id: Task that would gain the dependency
            to_id: Task that would be depended upon

        Returns:
            True if adding from_id -> to_id would create a cycle
        """
        # Build current graph
        graph = self._get_task_dependency_graph(plan)

        # Adding from_id -> to_id means from_id depends on to_id
        # A cycle exists if to_id can reach from_id through dependencies
        # i.e., if from_id is in the dependency chain of to_id

        # DFS from to_id to see if we can reach from_id
        visited: set[str] = set()
        stack = [to_id]

        while stack:
            current = stack.pop()
            if current == from_id:
                return True  # Found a cycle!
            if current in visited:
                continue
            visited.add(current)
            # Add all dependencies of current to stack
            stack.extend(graph.get(current, set()))

        return False

    def _apply_revision(
        self,
        plan: "ImplementationPlan",
        revision: PlanRevision,
    ) -> tuple["ImplementationPlan", str | None]:
        """Apply a single revision to the plan.

        Args:
            plan: Current plan (will be copied)
            revision: Revision to apply

        Returns:
            Tuple of (new_plan, error_message). error_message is None on success.
        """
        try:
            new_plan = deepcopy(plan)

            if revision.revision_type == RevisionType.ADD_TASK:
                new_plan = self._apply_add_task(new_plan, revision)
            elif revision.revision_type == RevisionType.MODIFY_TASK:
                new_plan = self._apply_modify_task(new_plan, revision)
            elif revision.revision_type == RevisionType.REMOVE_TASK:
                new_plan = self._apply_remove_task(new_plan, revision)
            elif revision.revision_type == RevisionType.ADD_DEPENDENCY:
                new_plan = self._apply_add_dependency(new_plan, revision)
            elif revision.revision_type == RevisionType.REORDER_TASKS:
                new_plan = self._apply_reorder_tasks(new_plan, revision)
            else:
                return plan, f"Unknown revision type: {revision.revision_type}"

            return new_plan, None

        except Exception as e:
            return plan, f"Error applying revision: {str(e)}"

    def _apply_add_task(
        self,
        plan: "ImplementationPlan",
        revision: PlanRevision,
    ) -> "ImplementationPlan":
        """Apply an ADD_TASK revision.

        Args:
            plan: Plan to modify (already copied)
            revision: Revision with new_task

        Returns:
            Modified plan
        """
        from claude_indexer.ui.plan.task import TaskGroup

        if revision.new_task is None:
            return plan

        new_task = revision.new_task
        target_scope = new_task.scope

        # Find or create the target group
        target_group = None
        for group in plan.groups:
            if group.scope == target_scope:
                target_group = group
                break

        if target_group is None:
            # Create a new group for this scope
            target_group = TaskGroup(
                scope=target_scope,
                description=f"Tasks for {target_scope}",
                tasks=[],
            )
            plan.groups.append(target_group)

        # Add the task to the group
        target_group.tasks.append(new_task)

        return plan

    def _apply_modify_task(
        self,
        plan: "ImplementationPlan",
        revision: PlanRevision,
    ) -> "ImplementationPlan":
        """Apply a MODIFY_TASK revision.

        Args:
            plan: Plan to modify (already copied)
            revision: Revision with target_task_id and modifications

        Returns:
            Modified plan
        """
        if revision.target_task_id is None:
            return plan

        # Find the task and modify it
        for group in plan.groups:
            for task in group.tasks:
                if task.id == revision.target_task_id:
                    # Apply modifications
                    for field_name, new_value in revision.modifications.items():
                        if hasattr(task, field_name):
                            setattr(task, field_name, new_value)
                    return plan

        return plan

    def _apply_remove_task(
        self,
        plan: "ImplementationPlan",
        revision: PlanRevision,
    ) -> "ImplementationPlan":
        """Apply a REMOVE_TASK revision.

        Args:
            plan: Plan to modify (already copied)
            revision: Revision with target_task_id

        Returns:
            Modified plan
        """
        if revision.target_task_id is None:
            return plan

        # Find and remove the task
        for group in plan.groups:
            for i, task in enumerate(group.tasks):
                if task.id == revision.target_task_id:
                    group.tasks.pop(i)
                    # Also remove from quick_wins if present
                    plan.quick_wins = [
                        t for t in plan.quick_wins if t.id != revision.target_task_id
                    ]
                    return plan

        return plan

    def _apply_add_dependency(
        self,
        plan: "ImplementationPlan",
        revision: PlanRevision,
    ) -> "ImplementationPlan":
        """Apply an ADD_DEPENDENCY revision.

        Args:
            plan: Plan to modify (already copied)
            revision: Revision with dependency_additions

        Returns:
            Modified plan
        """
        for from_id, to_id in revision.dependency_additions:
            # Find the source task and add the dependency
            for group in plan.groups:
                for task in group.tasks:
                    if task.id == from_id:
                        if to_id not in task.dependencies:
                            task.dependencies.append(to_id)

        return plan

    def _apply_reorder_tasks(
        self,
        plan: "ImplementationPlan",
        revision: PlanRevision,
    ) -> "ImplementationPlan":
        """Apply a REORDER_TASKS revision.

        Args:
            plan: Plan to modify (already copied)
            revision: Revision with target_task_id and modifications (priority)

        Returns:
            Modified plan
        """
        if revision.target_task_id is None:
            return plan

        # Get the new priority from modifications
        new_priority = revision.modifications.get("priority")
        if new_priority is None:
            return plan

        # Find the task and update its priority
        for group in plan.groups:
            for task in group.tasks:
                if task.id == revision.target_task_id:
                    task.priority = new_priority
                    return plan

        return plan

    def _resolve_dependencies(
        self,
        plan: "ImplementationPlan",
    ) -> "ImplementationPlan":
        """Resolve and clean up dependencies after revisions.

        Removes references to non-existent tasks and ensures
        dependency graph is valid.

        Args:
            plan: Plan to clean up

        Returns:
            Plan with resolved dependencies
        """
        existing_ids = {t.id for t in plan.all_tasks}

        for group in plan.groups:
            for task in group.tasks:
                # Remove dependencies to non-existent tasks
                task.dependencies = [
                    dep_id for dep_id in task.dependencies if dep_id in existing_ids
                ]

        return plan


def create_auto_revision_engine(
    config: "PlanGuardrailConfig",
    rules: dict[str, PlanValidationRule] | None = None,
) -> AutoRevisionEngine:
    """Factory function to create an auto-revision engine.

    Args:
        config: Plan guardrail configuration
        rules: Optional dict of rule instances

    Returns:
        Configured AutoRevisionEngine instance
    """
    return AutoRevisionEngine(config=config, rules=rules)


__all__ = [
    "AppliedRevision",
    "AutoRevisionEngine",
    "RevisedPlan",
    "create_auto_revision_engine",
]
