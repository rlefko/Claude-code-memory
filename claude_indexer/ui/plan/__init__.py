"""Plan generator for actionable UI implementation plans.

This module generates prioritized implementation plans from
critique reports, grouping tasks by scope and providing
acceptance criteria.

Includes guardrails subpackage for plan validation and
quality checks.
"""

from .generator import PlanGenerator
from .guardrails import (
    PlanGuardrailConfig,
    PlanPersistence,
    PlanRevision,
    PlanSnapshot,
    PlanValidationContext,
    PlanValidationFinding,
    PlanValidationRule,
    RevisionHistoryManager,
    RevisionType,
    RuleConfig,
)
from .prioritizer import TaskPrioritizer
from .task import ImplementationPlan, Task, TaskGroup

__all__ = [
    # Plan generation
    "ImplementationPlan",
    "PlanGenerator",
    "Task",
    "TaskGroup",
    "TaskPrioritizer",
    # Guardrails
    "PlanGuardrailConfig",
    "PlanRevision",
    "PlanValidationContext",
    "PlanValidationFinding",
    "PlanValidationRule",
    "RevisionType",
    "RuleConfig",
    # Revision history (Milestone 10.2)
    "PlanPersistence",
    "PlanSnapshot",
    "RevisionHistoryManager",
]
