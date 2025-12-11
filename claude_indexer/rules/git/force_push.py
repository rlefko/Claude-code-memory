"""
Git safety rules for detecting dangerous operations.

Detects force push, hard reset, and other potentially destructive
git commands that could cause data loss.
"""

import re
from typing import TYPE_CHECKING

from ..base import BaseRule, Evidence, Finding, RuleContext, Severity, Trigger

if TYPE_CHECKING:
    pass


class ForcePushRule(BaseRule):
    """Detect git push --force commands."""

    FORCE_PUSH_PATTERNS = [
        r"git\s+push\s+.*--force\b",
        r"git\s+push\s+.*-f\b",
        r"git\s+push\s+--force-with-lease\b",  # Slightly safer but still risky
    ]

    @property
    def rule_id(self) -> str:
        return "GIT.FORCE_PUSH"

    @property
    def name(self) -> str:
        return "Force Push Detection"

    @property
    def category(self) -> str:
        return "git"

    @property
    def default_severity(self) -> Severity:
        return Severity.CRITICAL

    @property
    def triggers(self) -> list[Trigger]:
        return [Trigger.ON_WRITE, Trigger.ON_STOP, Trigger.ON_COMMIT]

    @property
    def supported_languages(self) -> list[str] | None:
        # Only applies to shell scripts and bash
        return ["bash", "shell", "sh"]

    @property
    def description(self) -> str:
        return (
            "Detects git push --force commands which can overwrite remote "
            "history and cause data loss for other developers."
        )

    @property
    def is_fast(self) -> bool:
        return True

    def check(self, context: RuleContext) -> list[Finding]:
        """Check for force push commands.

        Args:
            context: RuleContext with file content

        Returns:
            List of findings for force push commands
        """
        findings = []
        lines = context.lines

        for line_num, line in enumerate(lines, start=1):
            if not context.is_line_in_diff(line_num):
                continue

            # Skip comments
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            for pattern in self.FORCE_PUSH_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    # Check if it's targeting main/master
                    is_main_branch = bool(
                        re.search(r"\b(main|master)\b", line, re.IGNORECASE)
                    )

                    summary = "Force push command detected"
                    if is_main_branch:
                        summary = "DANGER: Force push to main/master branch"

                    findings.append(
                        self._create_finding(
                            summary=summary,
                            file_path=str(context.file_path),
                            line_number=line_num,
                            evidence=[
                                Evidence(
                                    description="Force push can overwrite remote history",
                                    line_number=line_num,
                                    code_snippet=line.strip(),
                                    data={"targets_main": is_main_branch},
                                )
                            ],
                            remediation_hints=[
                                "Use regular push instead: git push",
                                "If force is required, use --force-with-lease for safety",
                                "Never force push to shared branches like main/master",
                            ],
                        )
                    )
                    break

        return findings


class HardResetRule(BaseRule):
    """Detect git reset --hard commands."""

    HARD_RESET_PATTERNS = [
        r"git\s+reset\s+--hard\b",
        r"git\s+reset\s+.*--hard\b",
    ]

    @property
    def rule_id(self) -> str:
        return "GIT.HARD_RESET"

    @property
    def name(self) -> str:
        return "Hard Reset Detection"

    @property
    def category(self) -> str:
        return "git"

    @property
    def default_severity(self) -> Severity:
        return Severity.CRITICAL

    @property
    def description(self) -> str:
        return (
            "Detects git reset --hard commands which discard all uncommitted "
            "changes and can cause irreversible data loss."
        )

    @property
    def is_fast(self) -> bool:
        return True

    def check(self, context: RuleContext) -> list[Finding]:
        """Check for hard reset commands.

        Args:
            context: RuleContext with file content

        Returns:
            List of findings for hard reset commands
        """
        findings = []
        lines = context.lines

        for line_num, line in enumerate(lines, start=1):
            if not context.is_line_in_diff(line_num):
                continue

            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            for pattern in self.HARD_RESET_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append(
                        self._create_finding(
                            summary="Hard reset command detected",
                            file_path=str(context.file_path),
                            line_number=line_num,
                            evidence=[
                                Evidence(
                                    description="Hard reset discards uncommitted changes",
                                    line_number=line_num,
                                    code_snippet=line.strip(),
                                )
                            ],
                            remediation_hints=[
                                "Use soft reset to preserve changes: git reset --soft",
                                "Stash changes first: git stash",
                                "Ensure all changes are committed before reset",
                            ],
                        )
                    )
                    break

        return findings


class DestructiveOpsRule(BaseRule):
    """Detect destructive file operations."""

    DESTRUCTIVE_PATTERNS = [
        (r"rm\s+-rf\s+/(?!tmp)", "rm -rf / (root directory)"),
        (r"rm\s+-rf\s+~", "rm -rf ~ (home directory)"),
        (r"rm\s+-rf\s+\*", "rm -rf * (current directory contents)"),
        (r"rm\s+-rf\s+\.\*", "rm -rf .* (hidden files)"),
        (r">\s*/dev/sd[a-z]", "overwrite block device"),
        (r"dd\s+.*of=/dev/sd[a-z]", "dd to block device"),
        (r"mkfs\.", "format filesystem"),
    ]

    @property
    def rule_id(self) -> str:
        return "GIT.DESTRUCTIVE_OPS"

    @property
    def name(self) -> str:
        return "Destructive Operations Detection"

    @property
    def category(self) -> str:
        return "git"

    @property
    def default_severity(self) -> Severity:
        return Severity.CRITICAL

    @property
    def description(self) -> str:
        return (
            "Detects potentially destructive file operations like rm -rf /, "
            "dd to block devices, and filesystem formatting commands."
        )

    @property
    def is_fast(self) -> bool:
        return True

    def check(self, context: RuleContext) -> list[Finding]:
        """Check for destructive operations.

        Args:
            context: RuleContext with file content

        Returns:
            List of findings for destructive operations
        """
        findings = []
        lines = context.lines

        for line_num, line in enumerate(lines, start=1):
            if not context.is_line_in_diff(line_num):
                continue

            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            for pattern, description in self.DESTRUCTIVE_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append(
                        self._create_finding(
                            summary=f"Dangerous operation: {description}",
                            file_path=str(context.file_path),
                            line_number=line_num,
                            evidence=[
                                Evidence(
                                    description=f"Potentially destructive: {description}",
                                    line_number=line_num,
                                    code_snippet=line.strip(),
                                )
                            ],
                            remediation_hints=[
                                "Review this command carefully before execution",
                                "Consider using safer alternatives",
                                "Add confirmation prompts for destructive operations",
                            ],
                        )
                    )
                    break

        return findings
