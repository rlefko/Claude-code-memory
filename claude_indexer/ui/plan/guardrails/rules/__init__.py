"""Plan validation rules for the guardrails framework.

This package contains the 5 core plan validation rules:
- PLAN.TEST_REQUIREMENT - Ensure features have test tasks
- PLAN.DOC_REQUIREMENT - Ensure user-facing changes have doc tasks
- PLAN.DUPLICATE_DETECTION - Detect tasks duplicating existing code
- PLAN.ARCHITECTURAL_CONSISTENCY - Verify tasks align with patterns
- PLAN.PERFORMANCE_PATTERN - Flag performance anti-patterns
"""

from claude_indexer.ui.plan.guardrails.rules.architectural_consistency import (
    ArchitecturalConsistencyRule,
)
from claude_indexer.ui.plan.guardrails.rules.doc_requirement import DocRequirementRule
from claude_indexer.ui.plan.guardrails.rules.duplicate_detection import (
    DuplicateDetectionRule,
)
from claude_indexer.ui.plan.guardrails.rules.performance_pattern import (
    PerformancePatternRule,
)
from claude_indexer.ui.plan.guardrails.rules.test_requirement import TestRequirementRule

__all__ = [
    "ArchitecturalConsistencyRule",
    "DocRequirementRule",
    "DuplicateDetectionRule",
    "PerformancePatternRule",
    "TestRequirementRule",
]
