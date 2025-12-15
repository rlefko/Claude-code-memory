"""Test requirement detection rule.

This rule ensures that feature/implementation tasks have corresponding
test tasks in the plan.
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


class TestRequirementRule(PlanValidationRule):
    """Ensures new features have corresponding test tasks.

    Detects feature/implementation tasks that don't have a test task
    in the plan and suggests adding one.
    """

    # Keywords indicating a feature/implementation task
    FEATURE_KEYWORDS = re.compile(
        r"\b(implement|add|create|build|develop|introduce|design|write)\b",
        re.IGNORECASE,
    )

    # Keywords indicating a test task
    TEST_KEYWORDS = re.compile(
        r"\b(tests?|specs?|unittest|pytest|jest|mocha|vitest|coverage|"
        r"testing|integration\s*tests?|unit\s*tests?|e2e)\b",
        re.IGNORECASE,
    )

    # Patterns indicating trivial tasks that don't need tests
    TRIVIAL_PATTERNS = re.compile(
        r"\b(fix\s+(typo|comment|readme|doc|whitespace|spacing|indent)|"
        r"rename\s+\w+|move\s+\w+|delete\s+(comment|readme|unused)|"
        r"update\s+(readme|comment|doc)|clean\s*up)\b",
        re.IGNORECASE,
    )

    # Tags that indicate test tasks
    TEST_TAGS = frozenset(
        ["test", "testing", "tests", "unit-test", "e2e", "integration-test", "qa"]
    )

    @property
    def rule_id(self) -> str:
        return "PLAN.TEST_REQUIREMENT"

    @property
    def name(self) -> str:
        return "Test Requirement Detection"

    @property
    def category(self) -> str:
        return "coverage"

    @property
    def default_severity(self) -> Severity:
        return Severity.MEDIUM

    @property
    def description(self) -> str:
        return (
            "Ensures that feature/implementation tasks have corresponding "
            "test tasks in the plan."
        )

    @property
    def is_fast(self) -> bool:
        return True

    def validate(self, context: PlanValidationContext) -> list[PlanValidationFinding]:
        """Check that feature tasks have corresponding test tasks."""
        findings: list[PlanValidationFinding] = []

        # Gather all test tasks in the plan
        test_task_ids = self._get_test_task_ids(context.plan.all_tasks)

        for task in context.plan.all_tasks:
            # Skip if task is already a test task
            if task.id in test_task_ids:
                continue

            # Skip trivial tasks
            if self._is_trivial_task(task):
                continue

            # Check if this is a feature task
            if not self._is_feature_task(task):
                continue

            # Check if task has a test dependency or related test task
            if self._has_test_coverage(task, test_task_ids, context.plan.all_tasks):
                continue

            # Create finding for task without test coverage
            finding = self._create_finding(
                summary=f"Feature task '{task.title}' lacks test coverage",
                affected_tasks=[task.id],
                suggestion=f"Add a test task for '{task.title}'",
                evidence=[
                    Evidence(
                        description="Task appears to implement new functionality",
                        data={
                            "task_id": task.id,
                            "task_title": task.title,
                            "detected_keywords": self._extract_feature_keywords(task),
                        },
                    )
                ],
                confidence=0.9,
                can_auto_revise=True,
            )
            findings.append(finding)

        return findings

    def suggest_revision(
        self,
        finding: PlanValidationFinding,
        context: PlanValidationContext,
    ) -> PlanRevision | None:
        """Suggest adding a test task for the feature."""
        if not finding.affected_tasks:
            return None

        task_id = finding.affected_tasks[0]
        feature_task = context.get_task_by_id(task_id)
        if feature_task is None:
            return None

        # Generate test task ID
        test_task_id = f"TASK-TST-{task_id.split('-')[-1]}"

        # Create test task
        test_task = Task(
            id=test_task_id,
            title=f"Add tests for {feature_task.title}",
            description=(
                f"Write tests to verify '{feature_task.title}' works correctly."
            ),
            scope=feature_task.scope,
            priority=feature_task.priority + 1,  # Slightly lower priority
            estimated_effort="low",
            impact=feature_task.impact * 0.8,
            acceptance_criteria=[
                "Unit tests cover main functionality",
                "Tests pass in CI",
                "Code coverage for new code >= 80%",
            ],
            evidence_links=[],
            related_critique_ids=[],
            dependencies=[feature_task.id],
            tags=["testing", "quality"],
        )

        return PlanRevision(
            revision_type=RevisionType.ADD_TASK,
            rationale=f"Feature task '{feature_task.title}' needs test coverage",
            new_task=test_task,
        )

    def _is_feature_task(self, task: Task) -> bool:
        """Check if task is a feature/implementation task."""
        text = f"{task.title} {task.description}"
        return bool(self.FEATURE_KEYWORDS.search(text))

    def _is_trivial_task(self, task: Task) -> bool:
        """Check if task is trivial and doesn't need tests."""
        text = f"{task.title} {task.description}"
        return bool(self.TRIVIAL_PATTERNS.search(text))

    def _is_test_task(self, task: Task) -> bool:
        """Check if task is a test-related task."""
        # Check title and description
        text = f"{task.title} {task.description}"
        if self.TEST_KEYWORDS.search(text):
            return True

        # Check tags
        task_tags = {tag.lower() for tag in task.tags}
        if task_tags & self.TEST_TAGS:
            return True

        return False

    def _get_test_task_ids(self, tasks: list[Task]) -> set[str]:
        """Get IDs of all test tasks in the plan."""
        return {task.id for task in tasks if self._is_test_task(task)}

    def _has_test_coverage(
        self, task: Task, test_task_ids: set[str], all_tasks: list[Task]
    ) -> bool:
        """Check if task has test coverage via dependencies or relations."""
        # Check if any test task depends on this task
        for other_task in all_tasks:
            if other_task.id in test_task_ids:
                if task.id in other_task.dependencies:
                    return True

        # Check if this task depends on a test task (unlikely but possible)
        if set(task.dependencies) & test_task_ids:
            return True

        return False

    def _extract_feature_keywords(self, task: Task) -> list[str]:
        """Extract detected feature keywords from task."""
        text = f"{task.title} {task.description}"
        matches = self.FEATURE_KEYWORDS.findall(text)
        return [m.lower() for m in matches]
