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
    PlanGuardrailEngine: Engine for orchestrating rule validation
    PlanGuardrailEngineConfig: Configuration for the engine
    PlanGuardrailResult: Aggregated validation results
    AutoRevisionEngine: Engine for applying auto-revisions to plans
    AppliedRevision: Record of applied revision
    RevisedPlan: Result of auto-revision process

Rules:
    TestRequirementRule: Ensures features have test tasks
    DocRequirementRule: Ensures user-facing changes have doc tasks
    DuplicateDetectionRule: Detects tasks duplicating existing code
    ArchitecturalConsistencyRule: Verifies tasks align with patterns
    PerformancePatternRule: Flags performance anti-patterns
"""

from .auto_revision import (
    AppliedRevision,
    AutoRevisionEngine,
    RevisedPlan,
    create_auto_revision_engine,
)
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
from .engine import (
    PlanGuardrailEngine,
    PlanGuardrailEngineConfig,
    PlanGuardrailResult,
    RuleExecutionResult,
    create_guardrail_engine,
)
from .rules import (
    ArchitecturalConsistencyRule,
    DocRequirementRule,
    DuplicateDetectionRule,
    PerformancePatternRule,
    TestRequirementRule,
)

__all__ = [
    # Enums
    "RevisionType",
    "Severity",
    # Data classes
    "AppliedRevision",
    "Evidence",
    "PlanRevision",
    "PlanValidationContext",
    "PlanValidationFinding",
    "RevisedPlan",
    "RuleExecutionResult",
    "PlanGuardrailResult",
    # Base rule class
    "PlanValidationRule",
    # Engines
    "AutoRevisionEngine",
    "PlanGuardrailEngine",
    "PlanGuardrailEngineConfig",
    "create_auto_revision_engine",
    "create_guardrail_engine",
    # Configuration
    "PlanGuardrailConfig",
    "RuleConfig",
    # Rules
    "ArchitecturalConsistencyRule",
    "DocRequirementRule",
    "DuplicateDetectionRule",
    "PerformancePatternRule",
    "TestRequirementRule",
]
