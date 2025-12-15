"""
Plan QA verification for generated implementation plans.

This module provides lightweight pattern-based verification of plan text
to ensure quality standards are met before user approval.

Checks include:
- Missing test tasks for code changes
- Missing documentation tasks for user-facing changes
- New code creation without duplicate/reuse checks
- Architecture concerns (performance anti-patterns)

Performance target: <50ms verification latency

Milestone 12.1: Plan QA Verifier
"""

import re
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlanQAResult:
    """Result from Plan QA verification.

    Aggregates all quality checks into a single result with
    actionable feedback for the user.

    Attributes:
        is_valid: True if plan passes all required checks
        missing_tests: Tasks identified as needing tests
        missing_docs: Tasks identified as needing documentation
        potential_duplicates: New code without explicit duplicate checks
        architecture_warnings: Architectural concerns detected
        suggestions: Actionable improvement suggestions
        verification_time_ms: Time taken for verification
    """

    is_valid: bool = True
    missing_tests: list[str] = field(default_factory=list)
    missing_docs: list[str] = field(default_factory=list)
    potential_duplicates: list[str] = field(default_factory=list)
    architecture_warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    verification_time_ms: float = 0.0

    def has_issues(self) -> bool:
        """Check if any quality issues were found.

        Returns:
            True if any issue list is non-empty
        """
        return bool(
            self.missing_tests
            or self.missing_docs
            or self.potential_duplicates
            or self.architecture_warnings
        )

    def format_feedback(self) -> str:
        """Format feedback for plan output (human-readable).

        Returns:
            Markdown-formatted feedback string
        """
        if not self.has_issues():
            return "\n[Plan QA: All quality checks passed]"

        lines = ["\n=== Plan QA Feedback ==="]

        if self.missing_tests:
            lines.append("\n[WARN] Missing Test Coverage:")
            for item in self.missing_tests:
                lines.append(f"  - {item}")

        if self.missing_docs:
            lines.append("\n[WARN] Missing Documentation:")
            for item in self.missing_docs:
                lines.append(f"  - {item}")

        if self.potential_duplicates:
            lines.append("\n[WARN] Potential Duplicates (no explicit reuse check):")
            for item in self.potential_duplicates:
                lines.append(f"  - {item}")

        if self.architecture_warnings:
            lines.append("\n[WARN] Architecture Concerns:")
            for item in self.architecture_warnings:
                lines.append(f"  - {item}")

        if self.suggestions:
            lines.append("\n[SUGGESTIONS]:")
            for suggestion in self.suggestions:
                lines.append(f"  - {suggestion}")

        lines.append("\n=== End Plan QA ===")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the result
        """
        return {
            "is_valid": self.is_valid,
            "has_issues": self.has_issues(),
            "missing_tests": self.missing_tests,
            "missing_docs": self.missing_docs,
            "potential_duplicates": self.potential_duplicates,
            "architecture_warnings": self.architecture_warnings,
            "suggestions": self.suggestions,
            "verification_time_ms": round(self.verification_time_ms, 2),
        }


@dataclass
class PlanQAConfig:
    """Configuration for Plan QA verification.

    Attributes:
        enabled: Whether QA verification is enabled
        check_tests: Verify test coverage
        check_docs: Verify documentation coverage
        check_duplicates: Check for duplicate verification
        check_architecture: Check architectural alignment
        fail_on_missing_tests: Mark plan as invalid if tests missing
        fail_on_missing_docs: Mark plan as invalid if docs missing
    """

    enabled: bool = True
    check_tests: bool = True
    check_docs: bool = True
    check_duplicates: bool = True
    check_architecture: bool = True
    fail_on_missing_tests: bool = False  # Warn only by default
    fail_on_missing_docs: bool = False  # Warn only by default

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation of the config
        """
        return {
            "enabled": self.enabled,
            "check_tests": self.check_tests,
            "check_docs": self.check_docs,
            "check_duplicates": self.check_duplicates,
            "check_architecture": self.check_architecture,
            "fail_on_missing_tests": self.fail_on_missing_tests,
            "fail_on_missing_docs": self.fail_on_missing_docs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanQAConfig":
        """Create from dictionary.

        Args:
            data: Dictionary with config values

        Returns:
            PlanQAConfig instance
        """
        return cls(
            enabled=data.get("enabled", True),
            check_tests=data.get("check_tests", True),
            check_docs=data.get("check_docs", True),
            check_duplicates=data.get("check_duplicates", True),
            check_architecture=data.get("check_architecture", True),
            fail_on_missing_tests=data.get("fail_on_missing_tests", False),
            fail_on_missing_docs=data.get("fail_on_missing_docs", False),
        )


class PlanQAVerifier:
    """Verifier for plan text quality.

    Performs pattern-based verification of plan text to detect:
    - Missing test tasks for code changes
    - Missing documentation tasks for user-facing changes
    - New code creation without explicit duplicate checks
    - Architecture concerns

    All checks are designed for <50ms total verification time.

    Example:
        verifier = PlanQAVerifier()
        result = verifier.verify_plan("1. Create AuthService class\\n2. Add unit tests")
        if result.has_issues():
            print(result.format_feedback())
    """

    # Patterns for detecting code changes in plan text
    # Flexible pattern that matches compound words like AuthService, UserService
    # Also handles special characters like backticks around names
    CODE_CHANGE_PATTERNS = re.compile(
        r"(add|create|implement|modify|update|build|develop|write|introduce)\s+"
        r"(?:(?:a|an|the|new|existing|custom)\s+)?"
        r"(?:[`'\"]?\w+[`'\"]?\s+){0,3}"  # Allow up to 3 words with optional quotes
        r"[`'\"]?"  # Optional opening quote/backtick
        r"(\w*(?:function|class|component|module|service|api|endpoint|method|handler|"
        r"controller|model|schema|validator|hook|feature|logic|algorithm))",
        re.IGNORECASE,
    )

    # Patterns for detecting test tasks
    TEST_TASK_PATTERNS = re.compile(
        r"(add|create|write|implement|include)\s+"
        r"(?:unit\s+|integration\s+|e2e\s+|end-to-end\s+)?"
        r"tests?|"
        r"test\s+(coverage|suite|file|cases?)|"
        r"(pytest|jest|mocha|vitest|unittest)\s+tests?|"
        r"\bspec\s+file|"
        r"testing\s+for|"
        r"verify\s+with\s+tests?",
        re.IGNORECASE,
    )

    # Patterns for detecting documentation tasks
    DOC_TASK_PATTERNS = re.compile(
        r"(update|add|create|write|include)\s+"
        r"(?:the\s+)?"  # Optional "the" between verb and docs
        r"(documentation|docs|readme|api\s*docs?|guide|docstring|"
        r"jsdoc|pydoc|comments?)|"
        r"document\s+the|"
        r"(changelog|release\s*notes?)|"
        r"update\s+the\s+readme",
        re.IGNORECASE,
    )

    # Patterns for user-facing changes
    USER_FACING_PATTERNS = re.compile(
        r"\b(api|cli|command|endpoint|route|ui|ux|frontend|dashboard|"
        r"config|setting|option|flag|parameter|public|external|visible|"
        r"user[\s-]?facing|customer|interface|button|form|page|screen)\b",
        re.IGNORECASE,
    )

    # Patterns indicating duplicate check was performed
    REUSE_CHECK_PATTERNS = re.compile(
        r"(verified|checked|reviewed|confirmed)\s+"
        r"(no\s+)?(existing|duplicate|similar)|"
        r"(extend|reuse|leverage|use\s+existing)\s+existing|"
        r"no\s+existing\s+(implementation|code|function|class)|"
        r"search_similar|read_graph|"
        r"checked\s+for\s+(duplicat|similar)|"
        r"will\s+(extend|reuse)|"
        r"based\s+on\s+existing",
        re.IGNORECASE,
    )

    # Patterns for architecture concerns
    # Note: Word boundaries don't work well with parentheses, so use lookahead
    ARCHITECTURE_CONCERN_PATTERNS = re.compile(
        r"(O\(n\^?2\)|O\(n\s*\*\s*m\)|nested\s+loop|"
        r"no\s+timeout|blocking\s+call|synchronous\s+http|"
        r"unbounded\s+(?:memory|array|list)|memory\s+leak|"
        r"n\+1\s+query|n\+1\s+problem|"
        r"global\s+state|circular\s+dependency)(?=\s|$|[.,;:])",
        re.IGNORECASE,
    )

    def __init__(self, config: PlanQAConfig | None = None):
        """Initialize the verifier.

        Args:
            config: Optional configuration
        """
        self.config = config or PlanQAConfig()

    def verify_plan(self, plan_text: str) -> PlanQAResult:
        """Verify a plan meets quality standards.

        Args:
            plan_text: The plan text to verify

        Returns:
            PlanQAResult with all findings and feedback
        """
        if not self.config.enabled:
            return PlanQAResult(is_valid=True)

        start_time = time.time()
        result = PlanQAResult()

        # Run all checks
        if self.config.check_tests:
            self._check_test_coverage(plan_text, result)

        if self.config.check_docs:
            self._check_doc_coverage(plan_text, result)

        if self.config.check_duplicates:
            self._check_duplicate_verification(plan_text, result)

        if self.config.check_architecture:
            self._check_architecture(plan_text, result)

        # Determine validity
        result.is_valid = self._determine_validity(result)

        # Add suggestions
        self._add_suggestions(result)

        result.verification_time_ms = (time.time() - start_time) * 1000
        return result

    def _check_test_coverage(self, plan_text: str, result: PlanQAResult) -> None:
        """Check for test coverage in plan.

        Args:
            plan_text: Plan text to check
            result: Result to populate
        """
        has_code_changes = self._needs_tests(plan_text)
        has_test_tasks = self._has_test_tasks(plan_text)

        if has_code_changes and not has_test_tasks:
            result.missing_tests.append(
                "Plan modifies/adds code but includes no test tasks"
            )

    def _check_doc_coverage(self, plan_text: str, result: PlanQAResult) -> None:
        """Check for documentation coverage in plan.

        Args:
            plan_text: Plan text to check
            result: Result to populate
        """
        is_user_facing = self._is_user_facing(plan_text)
        has_doc_tasks = self._has_doc_tasks(plan_text)

        if is_user_facing and not has_doc_tasks:
            result.missing_docs.append(
                "User-facing changes without documentation update task"
            )

    def _check_duplicate_verification(
        self, plan_text: str, result: PlanQAResult
    ) -> None:
        """Check for duplicate verification in plan.

        Args:
            plan_text: Plan text to check
            result: Result to populate
        """
        creates_new_code = self._creates_new_code(plan_text)
        mentions_reuse = self._mentions_reuse_check(plan_text)

        if creates_new_code and not mentions_reuse:
            result.potential_duplicates.append(
                "New code creation without explicit duplicate/reuse check"
            )

    def _check_architecture(self, plan_text: str, result: PlanQAResult) -> None:
        """Check for architecture concerns in plan.

        Args:
            plan_text: Plan text to check
            result: Result to populate
        """
        matches = self.ARCHITECTURE_CONCERN_PATTERNS.findall(plan_text)
        for match in matches[:3]:  # Limit to 3 warnings
            concern = match if isinstance(match, str) else match[0]
            result.architecture_warnings.append(
                f"Performance concern detected: {concern}"
            )

    def _determine_validity(self, result: PlanQAResult) -> bool:
        """Determine if plan is valid based on config and findings.

        Args:
            result: QA result with findings

        Returns:
            True if plan is valid
        """
        if self.config.fail_on_missing_tests and result.missing_tests:
            return False
        if self.config.fail_on_missing_docs and result.missing_docs:
            return False
        return True

    def _add_suggestions(self, result: PlanQAResult) -> None:
        """Add actionable suggestions based on findings.

        Args:
            result: Result to add suggestions to
        """
        if result.missing_tests:
            result.suggestions.append(
                "Add unit/integration test task to verify code changes"
            )
        if result.missing_docs:
            result.suggestions.append(
                "Add documentation update task for user-facing changes"
            )
        if result.potential_duplicates:
            result.suggestions.append(
                "Use search_similar() to verify no duplicate code exists"
            )

    # Detection helper methods
    def _needs_tests(self, plan_text: str) -> bool:
        """Check if plan makes code changes that need tests.

        Args:
            plan_text: Plan text to check

        Returns:
            True if code changes detected
        """
        return bool(self.CODE_CHANGE_PATTERNS.search(plan_text))

    def _has_test_tasks(self, plan_text: str) -> bool:
        """Check if plan includes test tasks.

        Args:
            plan_text: Plan text to check

        Returns:
            True if test tasks detected
        """
        return bool(self.TEST_TASK_PATTERNS.search(plan_text))

    def _is_user_facing(self, plan_text: str) -> bool:
        """Check if plan affects user-visible functionality.

        Args:
            plan_text: Plan text to check

        Returns:
            True if user-facing changes detected
        """
        return bool(self.USER_FACING_PATTERNS.search(plan_text))

    def _has_doc_tasks(self, plan_text: str) -> bool:
        """Check if plan includes documentation tasks.

        Args:
            plan_text: Plan text to check

        Returns:
            True if doc tasks detected
        """
        return bool(self.DOC_TASK_PATTERNS.search(plan_text))

    def _creates_new_code(self, plan_text: str) -> bool:
        """Check if plan creates new code entities.

        Args:
            plan_text: Plan text to check

        Returns:
            True if new code creation detected
        """
        return bool(self.CODE_CHANGE_PATTERNS.search(plan_text))

    def _mentions_reuse_check(self, plan_text: str) -> bool:
        """Check if plan mentions checking for existing code.

        Args:
            plan_text: Plan text to check

        Returns:
            True if reuse check mentioned
        """
        return bool(self.REUSE_CHECK_PATTERNS.search(plan_text))


def verify_plan_qa(
    plan_text: str,
    config: PlanQAConfig | None = None,
) -> PlanQAResult:
    """Convenience function for plan QA verification.

    Args:
        plan_text: The plan text to verify
        config: Optional configuration

    Returns:
        PlanQAResult with verification outcome
    """
    verifier = PlanQAVerifier(config=config)
    return verifier.verify_plan(plan_text)


__all__ = [
    "PlanQAConfig",
    "PlanQAResult",
    "PlanQAVerifier",
    "verify_plan_qa",
]
