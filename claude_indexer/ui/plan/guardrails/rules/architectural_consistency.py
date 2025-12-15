"""Architectural consistency check rule.

This rule verifies that tasks align with established project patterns
and file structure conventions.
"""

import re

from claude_indexer.rules.base import Evidence, Severity
from claude_indexer.ui.plan.guardrails.base import (
    PlanRevision,
    PlanValidationContext,
    PlanValidationFinding,
    PlanValidationRule,
    RevisionType,
)
from claude_indexer.ui.plan.task import Task


class ArchitecturalConsistencyRule(PlanValidationRule):
    """Verifies tasks align with project patterns and conventions.

    Checks file paths in evidence_links against established patterns
    and flags potential architectural violations.
    """

    # Common architectural patterns for file organization
    EXPECTED_PATTERNS: dict[str, list[re.Pattern]] = {
        "tests": [
            re.compile(r"^tests?/", re.IGNORECASE),
            re.compile(r"__tests__/", re.IGNORECASE),
            re.compile(r"\.test\.(py|js|ts|jsx|tsx)$", re.IGNORECASE),
            re.compile(r"_test\.(py|js|ts)$", re.IGNORECASE),
            re.compile(r"\.spec\.(js|ts|jsx|tsx)$", re.IGNORECASE),
        ],
        "components": [
            re.compile(r"^(src/)?components?/", re.IGNORECASE),
            re.compile(r"^(app|lib)/components?/", re.IGNORECASE),
        ],
        "utils": [
            re.compile(r"^(src/)?(utils?|helpers?|lib)/", re.IGNORECASE),
        ],
        "config": [
            re.compile(r"^(src/)?config/", re.IGNORECASE),
            re.compile(r"\.config\.(py|js|ts|json|yaml|yml)$", re.IGNORECASE),
        ],
        "api": [
            re.compile(r"^(src/)?(api|routes|endpoints)/", re.IGNORECASE),
            re.compile(r"^app/(api|routes)/", re.IGNORECASE),
        ],
        "models": [
            re.compile(r"^(src/)?(models?|entities|schemas?)/", re.IGNORECASE),
        ],
        "services": [
            re.compile(r"^(src/)?(services?|providers?)/", re.IGNORECASE),
        ],
    }

    # Keywords to detect what type of file the task is creating
    FILE_TYPE_KEYWORDS: dict[str, list[re.Pattern]] = {
        "tests": [
            re.compile(r"\b(test|spec|unittest|pytest)\b", re.IGNORECASE),
        ],
        "components": [
            re.compile(r"\b(component|widget|view|ui)\b", re.IGNORECASE),
        ],
        "utils": [
            re.compile(r"\b(util|helper|utility|helper)\b", re.IGNORECASE),
        ],
        "config": [
            re.compile(r"\b(config|configuration|setting)\b", re.IGNORECASE),
        ],
        "api": [
            re.compile(r"\b(api|endpoint|route|controller)\b", re.IGNORECASE),
        ],
        "models": [
            re.compile(r"\b(model|schema|entity)\b", re.IGNORECASE),
        ],
        "services": [
            re.compile(r"\b(service|provider|manager)\b", re.IGNORECASE),
        ],
    }

    @property
    def rule_id(self) -> str:
        return "PLAN.ARCHITECTURAL_CONSISTENCY"

    @property
    def name(self) -> str:
        return "Architectural Consistency Check"

    @property
    def category(self) -> str:
        return "architecture"

    @property
    def default_severity(self) -> Severity:
        return Severity.MEDIUM

    @property
    def description(self) -> str:
        return (
            "Verifies that tasks align with established project patterns "
            "and file structure conventions."
        )

    @property
    def is_fast(self) -> bool:
        return True

    def validate(self, context: PlanValidationContext) -> list[PlanValidationFinding]:
        """Check tasks for architectural consistency."""
        findings: list[PlanValidationFinding] = []

        for task in context.plan.all_tasks:
            # Check evidence links for file paths
            violations = self._check_file_paths(task)
            if violations:
                for violation in violations:
                    finding = self._create_finding(
                        summary=(
                            f"Task '{task.title}' may violate architectural pattern"
                        ),
                        affected_tasks=[task.id],
                        suggestion=violation["suggestion"],
                        evidence=[
                            Evidence(
                                description=violation["description"],
                                data={
                                    "file_path": violation["file_path"],
                                    "expected_pattern": violation["expected"],
                                    "file_type": violation["file_type"],
                                },
                            )
                        ],
                        confidence=0.85,
                        can_auto_revise=False,
                    )
                    findings.append(finding)

            # Check task description for potential violations
            desc_violations = self._check_task_description(task, context)
            if desc_violations:
                for violation in desc_violations:
                    finding = self._create_finding(
                        summary=(
                            f"Task '{task.title}' may have architectural concerns"
                        ),
                        affected_tasks=[task.id],
                        suggestion=violation["suggestion"],
                        evidence=[
                            Evidence(
                                description=violation["description"],
                                data={
                                    "concern": violation["concern"],
                                    "file_type": violation.get("file_type", "unknown"),
                                },
                            )
                        ],
                        confidence=0.75,
                        can_auto_revise=False,
                    )
                    findings.append(finding)

        return findings

    def suggest_revision(
        self,
        finding: PlanValidationFinding,
        context: PlanValidationContext,
    ) -> PlanRevision | None:
        """Suggest architectural improvements (typically requires manual review)."""
        if not finding.affected_tasks:
            return None

        task_id = finding.affected_tasks[0]
        task = context.get_task_by_id(task_id)
        if task is None:
            return None

        # Add architectural warning to task
        warning = "\n\n**Architectural Note:** " + (
            finding.suggestion or "Review file location for consistency."
        )

        new_description = task.description + warning

        return PlanRevision(
            revision_type=RevisionType.MODIFY_TASK,
            rationale="Adding architectural consistency warning",
            target_task_id=task_id,
            modifications={
                "description": new_description,
            },
        )

    def _check_file_paths(self, task: Task) -> list[dict]:
        """Check file paths in evidence links for violations."""
        violations = []

        for link in task.evidence_links:
            # Extract file path (may have :line_number suffix)
            file_path = link.split(":")[0]

            # Detect what type of file this should be based on task
            expected_type = self._detect_file_type(task)
            if expected_type is None:
                continue

            # Check if path matches expected pattern
            if not self._path_matches_pattern(file_path, expected_type):
                expected_pattern = self._get_expected_location(expected_type)
                violations.append(
                    {
                        "file_path": file_path,
                        "file_type": expected_type,
                        "expected": expected_pattern,
                        "description": (
                            f"File '{file_path}' doesn't follow {expected_type} pattern"
                        ),
                        "suggestion": (
                            f"Consider placing {expected_type} "
                            f"files in: {expected_pattern}"
                        ),
                    }
                )

        return violations

    def _check_task_description(
        self, task: Task, context: PlanValidationContext
    ) -> list[dict]:
        """Check task description for architectural concerns."""
        violations = []
        text = f"{task.title} {task.description}"

        # Check for multiple concerns in single task
        concerns_detected = []
        for file_type, patterns in self.FILE_TYPE_KEYWORDS.items():
            for pattern in patterns:
                if pattern.search(text):
                    concerns_detected.append(file_type)
                    break

        # Flag if task mixes multiple architectural concerns
        if len(concerns_detected) > 2:
            violations.append(
                {
                    "concern": "multiple_responsibilities",
                    "description": (
                        f"Task touches multiple areas: {', '.join(concerns_detected)}"
                    ),
                    "suggestion": (
                        "Consider splitting task into smaller, focused tasks"
                    ),
                }
            )

        return violations

    def _detect_file_type(self, task: Task) -> str | None:
        """Detect what type of file the task is working with."""
        text = f"{task.title} {task.description}"

        for file_type, patterns in self.FILE_TYPE_KEYWORDS.items():
            for pattern in patterns:
                if pattern.search(text):
                    return file_type

        return None

    def _path_matches_pattern(self, file_path: str, file_type: str) -> bool:
        """Check if file path matches expected patterns for file type."""
        patterns = self.EXPECTED_PATTERNS.get(file_type, [])
        return any(pattern.search(file_path) for pattern in patterns)

    def _get_expected_location(self, file_type: str) -> str:
        """Get human-readable expected location for file type."""
        locations = {
            "tests": "tests/ or __tests__/",
            "components": "src/components/ or components/",
            "utils": "src/utils/ or lib/",
            "config": "config/ or *.config.*",
            "api": "api/ or routes/ or app/api/",
            "models": "models/ or schemas/",
            "services": "services/ or providers/",
        }
        return locations.get(file_type, "appropriate directory")
