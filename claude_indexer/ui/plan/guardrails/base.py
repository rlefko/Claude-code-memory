"""Base classes and types for plan validation guardrails.

This module provides the foundational abstractions for creating
plan validation rules including coverage, consistency, architecture,
and performance checks.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Import Severity and Evidence from the code quality rules module
# to maintain consistency across rule systems
from claude_indexer.rules.base import Evidence, Severity

if TYPE_CHECKING:
    from ..task import ImplementationPlan, Task
    from .config import PlanGuardrailConfig, RuleConfig


class RevisionType(Enum):
    """Types of revisions that can be applied to a plan."""

    ADD_TASK = "add_task"  # Add a new task to the plan
    MODIFY_TASK = "modify_task"  # Modify an existing task
    REMOVE_TASK = "remove_task"  # Remove a task from the plan
    ADD_DEPENDENCY = "add_dependency"  # Add task dependency
    REORDER_TASKS = "reorder_tasks"  # Change task order/priority


@dataclass
class PlanRevision:
    """A suggested revision to an implementation plan.

    Represents a specific change that should be applied to the plan
    based on a validation finding.
    """

    revision_type: RevisionType
    rationale: str
    target_task_id: str | None = None  # Task being modified/removed
    new_task: "Task | None" = None  # For ADD_TASK revisions
    modifications: dict[str, Any] = field(
        default_factory=dict
    )  # Field changes for MODIFY_TASK
    dependency_additions: list[tuple[str, str]] = field(
        default_factory=list
    )  # (from_task_id, to_task_id) pairs

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "revision_type": self.revision_type.value,
            "rationale": self.rationale,
            "target_task_id": self.target_task_id,
            "modifications": self.modifications,
            "dependency_additions": [list(dep) for dep in self.dependency_additions],
        }
        if self.new_task is not None:
            result["new_task"] = self.new_task.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanRevision":
        """Create PlanRevision from dictionary."""
        from ..task import Task

        new_task = None
        if data.get("new_task"):
            new_task = Task.from_dict(data["new_task"])

        return cls(
            revision_type=RevisionType(data["revision_type"]),
            rationale=data["rationale"],
            target_task_id=data.get("target_task_id"),
            new_task=new_task,
            modifications=data.get("modifications", {}),
            dependency_additions=[
                tuple(dep) for dep in data.get("dependency_additions", [])
            ],
        )


@dataclass
class PlanValidationFinding:
    """A plan validation finding from a guardrail rule.

    Represents an issue detected during plan validation, with
    supporting evidence and optional auto-revision suggestion.
    """

    rule_id: str  # e.g., "PLAN.TEST_REQUIREMENT"
    severity: Severity
    summary: str
    affected_tasks: list[str] = field(default_factory=list)  # Task IDs
    suggestion: str | None = None  # Human-readable fix suggestion
    can_auto_revise: bool = False  # Whether auto-revision is available
    confidence: float = 1.0  # 0.0-1.0 confidence score
    evidence: list[Evidence] = field(default_factory=list)
    suggested_revision: PlanRevision | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "summary": self.summary,
            "affected_tasks": self.affected_tasks,
            "suggestion": self.suggestion,
            "can_auto_revise": self.can_auto_revise,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
            "created_at": self.created_at,
        }
        if self.suggested_revision is not None:
            result["suggested_revision"] = self.suggested_revision.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanValidationFinding":
        """Create PlanValidationFinding from dictionary."""
        suggested_revision = None
        if data.get("suggested_revision"):
            suggested_revision = PlanRevision.from_dict(data["suggested_revision"])

        return cls(
            rule_id=data["rule_id"],
            severity=Severity(data["severity"]),
            summary=data["summary"],
            affected_tasks=data.get("affected_tasks", []),
            suggestion=data.get("suggestion"),
            can_auto_revise=data.get("can_auto_revise", False),
            confidence=data.get("confidence", 1.0),
            evidence=[
                Evidence(
                    description=e["description"],
                    line_number=e.get("line_number"),
                    code_snippet=e.get("code_snippet"),
                    data=e.get("data", {}),
                )
                for e in data.get("evidence", [])
            ],
            suggested_revision=suggested_revision,
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


@dataclass
class PlanValidationContext:
    """Context passed to plan validation rules.

    Contains all the data rules need to validate an implementation plan,
    including the plan itself, memory access, and configuration.
    """

    plan: "ImplementationPlan"
    config: "PlanGuardrailConfig"
    project_path: Path = field(default_factory=Path.cwd)
    memory_client: Any = field(default=None, repr=False)  # Qdrant client
    collection_name: str | None = None
    source_requirements: str = ""  # Original requirements text

    def search_memory(
        self,
        query: str,
        limit: int = 5,
        entity_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Search semantic memory for similar code/patterns.

        Args:
            query: Search query string
            limit: Maximum number of results
            entity_types: Optional filter for entity types

        Returns:
            List of search results with score, name, type, etc.
        """
        if self.memory_client is None or self.collection_name is None:
            return []

        try:
            # Build search request
            results = self.memory_client.search(
                collection_name=self.collection_name,
                query_text=query,
                limit=limit,
            )
            return [
                {
                    "score": r.score,
                    "name": r.payload.get("name", ""),
                    "type": r.payload.get("entity_type", ""),
                    "file_path": r.payload.get("file_path", ""),
                    "content": r.payload.get("content", ""),
                }
                for r in results
            ]
        except Exception:
            return []

    def get_task_by_id(self, task_id: str) -> "Task | None":
        """Get a task by its ID.

        Args:
            task_id: Task identifier

        Returns:
            Task if found, None otherwise
        """
        for task in self.plan.all_tasks:
            if task.id == task_id:
                return task
        return None


class PlanValidationRule(ABC):
    """Abstract base class for plan validation rules.

    All plan guardrail rules must inherit from this class and implement
    the required abstract methods. Rules are responsible for:
    - Defining their unique identifier and category
    - Specifying default severity
    - Implementing validation logic
    - Optionally suggesting auto-revisions
    """

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Unique rule identifier.

        Format: PLAN.RULE_NAME (e.g., 'PLAN.TEST_REQUIREMENT')
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable rule name."""

    @property
    @abstractmethod
    def category(self) -> str:
        """Rule category: coverage, consistency, architecture, performance."""

    @property
    @abstractmethod
    def default_severity(self) -> Severity:
        """Default severity level for findings from this rule."""

    @property
    def description(self) -> str:
        """Detailed description of what this rule checks."""
        return f"Rule {self.rule_id}: {self.name}"

    @property
    def is_fast(self) -> bool:
        """Whether this rule is fast enough for synchronous checks (<100ms).

        Override and return False for rules that require expensive
        operations like semantic search or LLM calls.
        """
        return True

    @abstractmethod
    def validate(self, context: PlanValidationContext) -> list[PlanValidationFinding]:
        """Run the rule validation and return findings.

        Args:
            context: PlanValidationContext with plan, config, etc.

        Returns:
            List of PlanValidationFinding objects for any issues detected.
        """

    @abstractmethod
    def suggest_revision(
        self,
        finding: PlanValidationFinding,
        context: PlanValidationContext,
    ) -> PlanRevision | None:
        """Suggest a revision to fix a finding.

        Args:
            finding: The finding to fix
            context: PlanValidationContext for additional info

        Returns:
            PlanRevision if auto-fix is possible, None otherwise
        """

    def get_severity(self, config: "RuleConfig | None") -> Severity:
        """Get severity from config or use default.

        Args:
            config: Optional rule-specific configuration

        Returns:
            Severity level to use for findings
        """
        if config and config.severity:
            try:
                return Severity(config.severity.lower())
            except ValueError:
                pass
        return self.default_severity

    def _create_finding(
        self,
        summary: str,
        affected_tasks: list[str] | None = None,
        suggestion: str | None = None,
        evidence: list[Evidence] | None = None,
        config: "RuleConfig | None" = None,
        confidence: float = 1.0,
        can_auto_revise: bool = False,
        suggested_revision: PlanRevision | None = None,
    ) -> PlanValidationFinding:
        """Helper to create a PlanValidationFinding with this rule's ID and severity.

        Args:
            summary: Brief description of the issue
            affected_tasks: List of task IDs affected by this finding
            suggestion: Human-readable fix suggestion
            evidence: List of Evidence objects
            config: Rule configuration for severity override
            confidence: Confidence score (0.0-1.0)
            can_auto_revise: Whether auto-revision is available
            suggested_revision: Optional PlanRevision for auto-fix

        Returns:
            Populated PlanValidationFinding object
        """
        return PlanValidationFinding(
            rule_id=self.rule_id,
            severity=self.get_severity(config),
            summary=summary,
            affected_tasks=affected_tasks or [],
            suggestion=suggestion,
            can_auto_revise=can_auto_revise,
            confidence=confidence,
            evidence=evidence or [],
            suggested_revision=suggested_revision,
        )

    def __repr__(self) -> str:
        """String representation of the rule."""
        return f"<{self.__class__.__name__} {self.rule_id}>"


__all__ = [
    "Evidence",
    "PlanRevision",
    "PlanValidationContext",
    "PlanValidationFinding",
    "PlanValidationRule",
    "RevisionType",
    "Severity",
]
