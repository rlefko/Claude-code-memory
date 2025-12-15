"""Plan validation guardrails for quality checks.

This package provides the core data model and infrastructure for
validating implementation plans against quality rules (coverage,
consistency, architecture, performance).

Classes:
    PlanValidationRule: Abstract base class for plan guardrail rules
    PlanValidationContext: Context passed to rules during validation
    PlanValidationFinding: Finding from a guardrail rule
    PlanRevision: Suggested revision to fix a finding
    RevisionType: Types of plan revisions
    PlanGuardrailConfig: Configuration for guardrails
    RuleConfig: Configuration for individual rules
"""

from .base import (
    Evidence,
    PlanRevision,
    PlanValidationContext,
    PlanValidationFinding,
    PlanValidationRule,
    RevisionType,
    Severity,
)
from .config import PlanGuardrailConfig, RuleConfig

__all__ = [
    # Enums
    "RevisionType",
    "Severity",
    # Data classes
    "Evidence",
    "PlanRevision",
    "PlanValidationContext",
    "PlanValidationFinding",
    # Base rule class
    "PlanValidationRule",
    # Configuration
    "PlanGuardrailConfig",
    "RuleConfig",
]
