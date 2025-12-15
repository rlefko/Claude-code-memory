"""Documentation requirement detection rule.

This rule ensures that user-facing changes have corresponding
documentation tasks in the plan.
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


class DocRequirementRule(PlanValidationRule):
    """Ensures user-facing changes have documentation tasks.

    Detects tasks that modify user-visible functionality without
    a corresponding documentation task in the plan.
    """

    # Keywords indicating user-facing changes
    USER_FACING_KEYWORDS = re.compile(
        r"\b(api|user|interface|config|cli|command|endpoint|route|"
        r"ui|ux|frontend|dashboard|setting|option|flag|parameter|"
        r"public|external|exposed|visible|accessible)\b",
        re.IGNORECASE,
    )

    # Keywords indicating changes that need documentation
    DOC_NEEDED_ACTIONS = re.compile(
        r"\b(add|create|change|modify|update|remove|deprecate|"
        r"rename|introduce|implement|new)\b",
        re.IGNORECASE,
    )

    # Keywords indicating documentation tasks
    DOC_KEYWORDS = re.compile(
        r"\b(doc|documentation|readme|docs|guide|tutorial|"
        r"api\s*doc|reference|changelog|release\s*note|"
        r"comment|jsdoc|docstring|help\s*text)\b",
        re.IGNORECASE,
    )

    # Tags that indicate documentation tasks
    DOC_TAGS = frozenset(
        ["docs", "documentation", "readme", "doc", "wiki", "guide", "api-docs"]
    )

    @property
    def rule_id(self) -> str:
        return "PLAN.DOC_REQUIREMENT"

    @property
    def name(self) -> str:
        return "Documentation Requirement Detection"

    @property
    def category(self) -> str:
        return "coverage"

    @property
    def default_severity(self) -> Severity:
        return Severity.LOW

    @property
    def description(self) -> str:
        return (
            "Ensures that user-facing changes have corresponding "
            "documentation tasks in the plan."
        )

    @property
    def is_fast(self) -> bool:
        return True

    def validate(self, context: PlanValidationContext) -> list[PlanValidationFinding]:
        """Check that user-facing tasks have documentation tasks."""
        findings: list[PlanValidationFinding] = []

        # Gather all doc tasks in the plan
        doc_task_ids = self._get_doc_task_ids(context.plan.all_tasks)

        # If plan already has doc tasks, we might be covered
        has_doc_tasks = len(doc_task_ids) > 0

        for task in context.plan.all_tasks:
            # Skip if task is already a doc task
            if task.id in doc_task_ids:
                continue

            # Check if this is a user-facing task
            if not self._is_user_facing_task(task):
                continue

            # Check if task has doc coverage
            if has_doc_tasks and self._has_doc_coverage(
                task, doc_task_ids, context.plan.all_tasks
            ):
                continue

            # Create finding for task without doc coverage
            detected_keywords = self._extract_user_facing_keywords(task)
            finding = self._create_finding(
                summary=f"User-facing task '{task.title}' lacks documentation",
                affected_tasks=[task.id],
                suggestion=f"Add documentation task for '{task.title}'",
                evidence=[
                    Evidence(
                        description="Task modifies user-visible functionality",
                        data={
                            "task_id": task.id,
                            "task_title": task.title,
                            "detected_keywords": detected_keywords,
                        },
                    )
                ],
                confidence=0.8,
                can_auto_revise=True,
            )
            findings.append(finding)

        return findings

    def suggest_revision(
        self,
        finding: PlanValidationFinding,
        context: PlanValidationContext,
    ) -> PlanRevision | None:
        """Suggest adding a documentation task."""
        if not finding.affected_tasks:
            return None

        task_id = finding.affected_tasks[0]
        user_task = context.get_task_by_id(task_id)
        if user_task is None:
            return None

        # Generate doc task ID
        doc_task_id = f"TASK-DOC-{task_id.split('-')[-1]}"

        # Create documentation task
        doc_task = Task(
            id=doc_task_id,
            title=f"Update documentation for {user_task.title}",
            description=(
                f"Update relevant documentation to reflect changes from "
                f"'{user_task.title}'. Include usage examples if applicable."
            ),
            scope=user_task.scope,
            priority=user_task.priority + 1,  # Slightly lower priority
            estimated_effort="low",
            impact=user_task.impact * 0.6,
            acceptance_criteria=[
                "Documentation updated in relevant files",
                "Usage examples added where applicable",
                "API changes documented if any",
            ],
            evidence_links=[],
            related_critique_ids=[],
            dependencies=[user_task.id],
            tags=["documentation", "docs"],
        )

        return PlanRevision(
            revision_type=RevisionType.ADD_TASK,
            rationale=(
                f"User-facing task '{user_task.title}' needs documentation update"
            ),
            new_task=doc_task,
        )

    def _is_user_facing_task(self, task: Task) -> bool:
        """Check if task affects user-visible functionality."""
        text = f"{task.title} {task.description}"

        # Must have user-facing keywords
        if not self.USER_FACING_KEYWORDS.search(text):
            return False

        # Must have action keywords indicating a change
        if not self.DOC_NEEDED_ACTIONS.search(text):
            return False

        return True

    def _is_doc_task(self, task: Task) -> bool:
        """Check if task is a documentation task."""
        # Check title and description
        text = f"{task.title} {task.description}"
        if self.DOC_KEYWORDS.search(text):
            return True

        # Check tags
        task_tags = {tag.lower() for tag in task.tags}
        if task_tags & self.DOC_TAGS:
            return True

        return False

    def _get_doc_task_ids(self, tasks: list[Task]) -> set[str]:
        """Get IDs of all documentation tasks in the plan."""
        return {task.id for task in tasks if self._is_doc_task(task)}

    def _has_doc_coverage(
        self, task: Task, doc_task_ids: set[str], all_tasks: list[Task]
    ) -> bool:
        """Check if task has documentation coverage."""
        # Check if any doc task depends on this task
        for other_task in all_tasks:
            if other_task.id in doc_task_ids:
                if task.id in other_task.dependencies:
                    return True

        # Check if this task depends on a doc task
        if set(task.dependencies) & doc_task_ids:
            return True

        return False

    def _extract_user_facing_keywords(self, task: Task) -> list[str]:
        """Extract detected user-facing keywords from task."""
        text = f"{task.title} {task.description}"
        matches = self.USER_FACING_KEYWORDS.findall(text)
        return list({m.lower() for m in matches})
