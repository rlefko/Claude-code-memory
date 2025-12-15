"""Performance pattern detection rule.

This rule flags potential performance anti-patterns in implementation
tasks based on keyword analysis of task descriptions.
"""

import re
from dataclasses import dataclass

from claude_indexer.rules.base import Evidence, Severity
from claude_indexer.ui.plan.guardrails.base import (
    PlanRevision,
    PlanValidationContext,
    PlanValidationFinding,
    PlanValidationRule,
    RevisionType,
)
from claude_indexer.ui.plan.task import Task


@dataclass
class AntiPattern:
    """Performance anti-pattern definition."""

    name: str
    description: str
    patterns: list[re.Pattern]
    suggestion: str
    confidence: float = 0.7


class PerformancePatternRule(PlanValidationRule):
    """Flags potential performance anti-patterns in tasks.

    Scans task descriptions for common performance anti-patterns
    like N+1 queries, missing caching, and blocking operations.
    """

    # Performance anti-patterns to detect
    ANTI_PATTERNS: list[AntiPattern] = [
        AntiPattern(
            name="N+1 Query",
            description="Potential N+1 query pattern detected",
            patterns=[
                re.compile(
                    r"\b(for\s+each|loop|iterate)\b.*\b(query|database|db|fetch|api)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(query|database|db|fetch|api)\b.*\b(for\s+each|loop|iterate)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(individual|separate|one\s+by\s+one)\b.*"
                    r"\b(requests?|query|calls?)\b",
                    re.IGNORECASE,
                ),
            ],
            suggestion=(
                "Consider batching database queries or API calls. "
                "Use eager loading, prefetch, or batch endpoints."
            ),
            confidence=0.75,
        ),
        AntiPattern(
            name="Missing Cache",
            description="Potential missing caching opportunity",
            patterns=[
                re.compile(
                    r"\b(no\s+cache|without\s+caching|every\s+(request|time))\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(always\s+fetch|always\s+query|repeated\s+call)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(expensive|slow|heavy)\b.*\b(operation|query|call)\b",
                    re.IGNORECASE,
                ),
            ],
            suggestion=(
                "Consider adding caching for expensive operations. "
                "Use memoization, Redis, or in-memory caching."
            ),
            confidence=0.70,
        ),
        AntiPattern(
            name="Blocking Operation",
            description="Potential blocking/synchronous operation",
            patterns=[
                re.compile(
                    r"\b(synchronous|blocking|sync)\b.*\b(external|api|http|network)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(wait\s+for|await\s+all|sequential)\b.*\b(request|call)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(no\s+timeout|without\s+timeout)\b",
                    re.IGNORECASE,
                ),
            ],
            suggestion=(
                "Consider async operations with proper timeouts. "
                "Use background jobs for long-running tasks."
            ),
            confidence=0.70,
        ),
        AntiPattern(
            name="Unbounded Data",
            description="Potential unbounded data loading",
            patterns=[
                re.compile(
                    r"\b(all|entire|full|complete)\b.*\b(data|records|rows|list)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(no\s+limit|unlimited|without\s+pagination)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(load\s+all|fetch\s+all|get\s+all)\b",
                    re.IGNORECASE,
                ),
            ],
            suggestion=(
                "Consider pagination or limit data loading. "
                "Implement lazy loading or virtualization for large datasets."
            ),
            confidence=0.65,
        ),
        AntiPattern(
            name="Memory Intensive",
            description="Potential memory-intensive operation",
            patterns=[
                re.compile(
                    r"\b(large|massive|huge)\b.*\b(array|list|collection|object)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(in\s+memory|memory\s+intensive|memory\s+heavy)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(accumulate|collect|gather)\b.*\b(all|everything)\b",
                    re.IGNORECASE,
                ),
            ],
            suggestion=(
                "Consider streaming or chunked processing. "
                "Use generators or iterators for large datasets."
            ),
            confidence=0.60,
        ),
        AntiPattern(
            name="Complex Algorithm",
            description="Potential algorithmic complexity concern",
            patterns=[
                re.compile(
                    r"\b(nested\s+loop|double\s+loop|triple\s+loop)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"(O\(n\^2\)|O\(n\s*\*\s*n\)|\bquadratic\b)",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(brute\s+force|exhaustive|all\s+combinations)\b",
                    re.IGNORECASE,
                ),
            ],
            suggestion=(
                "Review algorithmic complexity. Consider optimized "
                "algorithms, indexes, or data structure changes."
            ),
            confidence=0.80,
        ),
    ]

    @property
    def rule_id(self) -> str:
        return "PLAN.PERFORMANCE_PATTERN"

    @property
    def name(self) -> str:
        return "Performance Pattern Detection"

    @property
    def category(self) -> str:
        return "performance"

    @property
    def default_severity(self) -> Severity:
        return Severity.LOW

    @property
    def description(self) -> str:
        return (
            "Flags potential performance anti-patterns in implementation "
            "tasks based on keyword analysis."
        )

    @property
    def is_fast(self) -> bool:
        return True

    def validate(self, context: PlanValidationContext) -> list[PlanValidationFinding]:
        """Scan tasks for performance anti-patterns."""
        findings: list[PlanValidationFinding] = []

        for task in context.plan.all_tasks:
            detected_patterns = self._detect_anti_patterns(task)

            for anti_pattern in detected_patterns:
                finding = self._create_finding(
                    summary=(
                        f"Task '{task.title}' may have performance concern: "
                        f"{anti_pattern.name}"
                    ),
                    affected_tasks=[task.id],
                    suggestion=anti_pattern.suggestion,
                    evidence=[
                        Evidence(
                            description=anti_pattern.description,
                            data={
                                "pattern_name": anti_pattern.name,
                                "task_id": task.id,
                            },
                        )
                    ],
                    confidence=anti_pattern.confidence,
                    can_auto_revise=True,
                )
                findings.append(finding)

        return findings

    def suggest_revision(
        self,
        finding: PlanValidationFinding,
        context: PlanValidationContext,
    ) -> PlanRevision | None:
        """Suggest adding performance consideration to task."""
        if not finding.affected_tasks:
            return None

        task_id = finding.affected_tasks[0]
        task = context.get_task_by_id(task_id)
        if task is None:
            return None

        # Get pattern name from evidence
        pattern_name = "Performance"
        if finding.evidence:
            pattern_name = finding.evidence[0].data.get("pattern_name", "Performance")

        # Add performance note to task
        note = (
            f"\n\n**Performance Note ({pattern_name}):** "
            f"{finding.suggestion or 'Review for potential performance issues.'}"
        )

        new_description = task.description + note

        # Add acceptance criteria for performance
        new_criteria = list(task.acceptance_criteria) + [
            f"Performance consideration addressed: {pattern_name}"
        ]

        return PlanRevision(
            revision_type=RevisionType.MODIFY_TASK,
            rationale=f"Adding performance consideration: {pattern_name}",
            target_task_id=task_id,
            modifications={
                "description": new_description,
                "acceptance_criteria": new_criteria,
            },
        )

    def _detect_anti_patterns(self, task: Task) -> list[AntiPattern]:
        """Detect performance anti-patterns in task."""
        text = f"{task.title} {task.description}"
        detected = []

        for anti_pattern in self.ANTI_PATTERNS:
            for pattern in anti_pattern.patterns:
                if pattern.search(text):
                    detected.append(anti_pattern)
                    break  # Only detect each anti-pattern once per task

        return detected
