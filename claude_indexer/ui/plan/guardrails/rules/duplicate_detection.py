"""Duplicate code detection rule.

This rule detects tasks that might duplicate existing functionality
in the codebase using semantic memory search.
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


class DuplicateDetectionRule(PlanValidationRule):
    """Detects tasks that might duplicate existing functionality.

    Uses semantic memory search to find existing code that may already
    implement what a task is proposing.
    """

    # Default similarity threshold for duplicate detection
    SIMILARITY_THRESHOLD = 0.70

    # Keywords indicating new code creation
    CREATION_KEYWORDS = re.compile(
        r"\b(implement|create|add|build|write|develop|introduce|new)\b",
        re.IGNORECASE,
    )

    # Entity types to search for potential duplicates
    SEARCH_ENTITY_TYPES = ["function", "class", "implementation_pattern"]

    @property
    def rule_id(self) -> str:
        return "PLAN.DUPLICATE_DETECTION"

    @property
    def name(self) -> str:
        return "Duplicate Code Detection"

    @property
    def category(self) -> str:
        return "consistency"

    @property
    def default_severity(self) -> Severity:
        return Severity.HIGH

    @property
    def description(self) -> str:
        return (
            "Detects tasks that might duplicate existing functionality "
            "using semantic code search."
        )

    @property
    def is_fast(self) -> bool:
        # This rule uses memory search, which may be slower
        return False

    def validate(self, context: PlanValidationContext) -> list[PlanValidationFinding]:
        """Check for potential duplicate functionality."""
        findings: list[PlanValidationFinding] = []

        # Skip if no memory client available
        if context.memory_client is None:
            return findings

        # Get threshold from config if available
        threshold = self.SIMILARITY_THRESHOLD
        rule_config = context.config.get_rule_config(self.rule_id)
        if rule_config and rule_config.threshold is not None:
            threshold = rule_config.threshold

        for task in context.plan.all_tasks:
            # Only check tasks that create new code
            if not self._is_creation_task(task):
                continue

            # Search for similar existing code
            similar_code = self._search_for_duplicates(task, context, threshold)

            if similar_code:
                # Create finding for potential duplicate
                evidence = [
                    Evidence(
                        description=f"Similar code found: {match['name']}",
                        data={
                            "name": match["name"],
                            "type": match["type"],
                            "file_path": match["file_path"],
                            "score": match["score"],
                        },
                    )
                    for match in similar_code[:3]  # Limit to top 3 matches
                ]

                # Confidence based on similarity score
                max_score = max(m["score"] for m in similar_code)
                confidence = min(0.95, max_score)

                finding = self._create_finding(
                    summary=(
                        f"Task '{task.title}' may duplicate existing code: "
                        f"{similar_code[0]['name']}"
                    ),
                    affected_tasks=[task.id],
                    suggestion=(
                        f"Review existing {similar_code[0]['type']} "
                        f"'{similar_code[0]['name']}' before implementing"
                    ),
                    evidence=evidence,
                    confidence=confidence,
                    can_auto_revise=True,
                )
                findings.append(finding)

        return findings

    def suggest_revision(
        self,
        finding: PlanValidationFinding,
        context: PlanValidationContext,
    ) -> PlanRevision | None:
        """Suggest modifying task to reference existing code."""
        if not finding.affected_tasks:
            return None

        task_id = finding.affected_tasks[0]
        task = context.get_task_by_id(task_id)
        if task is None:
            return None

        # Extract existing code reference from evidence
        existing_code = None
        if finding.evidence:
            data = finding.evidence[0].data
            existing_code = data.get("name", "existing code")
            file_path = data.get("file_path", "")

        # Create modification to add note about existing code
        note = (
            f"\n\n**Note:** Review existing implementation '{existing_code}'"
            f"{f' in {file_path}' if file_path else ''} before proceeding. "
            "Consider extending or reusing existing code."
        )

        new_description = task.description + note
        new_criteria = list(task.acceptance_criteria) + [
            f"Verified no duplication with existing '{existing_code}'"
        ]

        return PlanRevision(
            revision_type=RevisionType.MODIFY_TASK,
            rationale=f"Potential duplicate of existing code detected: {existing_code}",
            target_task_id=task_id,
            modifications={
                "description": new_description,
                "acceptance_criteria": new_criteria,
            },
        )

    def _is_creation_task(self, task: Task) -> bool:
        """Check if task creates new code."""
        text = f"{task.title} {task.description}"
        return bool(self.CREATION_KEYWORDS.search(text))

    def _search_for_duplicates(
        self,
        task: Task,
        context: PlanValidationContext,
        threshold: float,
    ) -> list[dict]:
        """Search memory for similar existing code."""
        # Build search query from task
        query = f"{task.title} {task.description[:200]}"

        # Search for similar code
        results = context.search_memory(
            query=query,
            limit=5,
            entity_types=self.SEARCH_ENTITY_TYPES,
        )

        # Filter by similarity threshold
        duplicates = []
        for result in results:
            score = result.get("score", 0)
            if score >= threshold:
                duplicates.append(result)

        return duplicates
