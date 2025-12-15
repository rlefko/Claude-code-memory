"""Plan generator for actionable UI implementation plans.

This module generates prioritized implementation plans from
critique reports, grouping tasks by scope and providing
acceptance criteria.

Includes guardrails subpackage for plan validation and
quality checks.
"""

from .formatters import (
    CATEGORY_NAMES,
    SEVERITY_ICONS,
    ThoroughnessLevel,
    format_plan_findings_for_claude,
    format_plan_findings_for_display,
)
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
    # Formatters (Milestone 13.4)
    "ThoroughnessLevel",
    "format_plan_findings_for_display",
    "format_plan_findings_for_claude",
    "SEVERITY_ICONS",
    "CATEGORY_NAMES",
]
